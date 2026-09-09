package com.corp.framework.source.bigtable

import com.fasterxml.jackson.databind.node.ObjectNode
import com.fasterxml.jackson.databind.{JsonNode, ObjectMapper}
import com.google.cloud.spark.bigtable.repackaged.com.google.api.gax.core.CredentialsProvider
import com.google.cloud.spark.bigtable.repackaged.com.google.auth.Credentials
import com.google.cloud.spark.bigtable.repackaged.com.google.auth.oauth2.ServiceAccountCredentials
import com.google.cloud.spark.bigtable.repackaged.com.google.cloud.bigtable.data.v2.models.Filters
import com.google.cloud.spark.bigtable.repackaged.com.google.cloud.bigtable.data.v2.models.Filters.FILTERS
import com.google.cloud.spark.bigtable.repackaged.com.google.common.io.BaseEncoding
import org.apache.spark.SparkFiles
import org.apache.spark.internal.Logging
import org.apache.spark.sql.catalyst.expressions.Expression
import org.apache.spark.sql.catalyst.analysis.{UnresolvedAttribute, UnresolvedStar}
import org.apache.spark.sql.catalyst.plans.logical.{Filter => LogicalFilter}
import org.apache.spark.sql.{Column, DataFrame, SparkSession, functions => F}

import java.io.{File, FileInputStream}
import java.time.Instant
import java.util.Arrays
import scala.collection.JavaConverters._
import scala.io.Source
import scala.util.{Failure, Success, Try}

/*
 * ============================================================================
 *  Bigtable "SQL source" for the framework -- v2
 * ============================================================================
 *
 *  Contract, same as JDBC/Hive: declare a source, hand it a Spark SQL string,
 *  get a DataFrame.  The connector catalog plays the role of the table DDL.
 *
 *  v2 adds the three things you flagged:
 *
 *   A. COMPOUND ROW KEYS (mixed across your tables)
 *      The connector does NOT push predicates on compound row keys -- any
 *      WHERE on the key parts becomes a full table scan.  So we never let the
 *      connector see the key as compound.  Instead:
 *        1. read with a "flat" catalog where the row key is ONE string column;
 *        2. re-derive the logical key parts in the temp view with split /
 *           substring, so SQL can still say `WHERE cust_id = ... AND region = ...`;
 *        3. rewrite leading-part equality/range predicates back into a prefix
 *           or range predicate on the flat key column, and apply that as a
 *           DataFrame filter *before* registering the view -- which the
 *           connector then pushes as a real Bigtable row range.
 *      Tables with a single-column key skip all of this.
 *
 *   B. CELL TIMESTAMP / VERSION RANGES
 *      Expressed per query (not just per source) and compiled into the
 *      server-side RowFilter: timestamp().range() + limit().cellsPerColumn(n).
 *
 *   C. joinWithBigtable
 *      For "I have 2M keys in a Hive table, don't scan Bigtable" -- routes
 *      through the connector's join API instead of a scan, then registers the
 *      result as the temp view so the rest of the SQL is unchanged.
 *
 * ----------------------------------------------------------------------------
 *  HONEST CAVEATS -- read these before trusting the optimiser
 * ----------------------------------------------------------------------------
 *  1. Cell filters drop cells, not rows.  A row holding NONE of the projected
 *     qualifiers vanishes instead of returning nulls.  pushDownCellFilter=false
 *     if your tables are sparse and you depend on all-null rows.
 *  2. Compound-key prefix rewriting is only sound when the key encoding is
 *     order-preserving and the parts you filter on are a LEADING prefix.
 *     Fixed-width or separator-delimited string keys are fine.  Hash-prefixed
 *     or salted keys are NOT -- declare them as KeyEncoding.Opaque and no
 *     rewriting happens.
 *  3. The connector maps one cell to one column.  maxVersions > 1 does not
 *     give you an array of versions; it only changes WHICH cell wins inside a
 *     timestamp range.  Use the RDD API if you truly need version history.
 *  4. joinWithBigtable landed in recent connector releases and its exact
 *     signature has moved.  Verify against the version on your cluster; the
 *     call is isolated in BigtableJoinSupport so there is one place to fix.
 * ============================================================================
 */

// ---------------------------------------------------------------------------
// 1. Row key modelling
// ---------------------------------------------------------------------------

sealed trait KeyEncoding
object KeyEncoding {
  /** Parts joined by a literal separator, e.g. "CUST#0001|EU|2026". */
  final case class Delimited(separator: String) extends KeyEncoding
  /** Parts of fixed byte width, concatenated, no separator. */
  case object FixedWidth extends KeyEncoding
  /** Salted / hashed / non-order-preserving. Disables all prefix rewriting. */
  case object Opaque extends KeyEncoding
}

/** One logical component of a compound row key. */
final case class KeyPart(name: String, width: Option[Int] = None)

sealed trait RowKeyModel {
  def flatColumn: String
}
object RowKeyModel {
  /** Catalog already exposes a single row-key column. Nothing to do. */
  final case class Single(flatColumn: String) extends RowKeyModel

  /**
   * Key is logically several fields but is stored as one string.
   *
   * @param flatColumn the DataFrame column that IS the raw row key
   * @param parts      ordered logical components
   * @param encoding   how parts are laid out inside the key
   */
  final case class Compound(
      flatColumn: String,
      parts: Seq[KeyPart],
      encoding: KeyEncoding
  ) extends RowKeyModel {
    require(parts.nonEmpty, "Compound row key needs at least one part")
    encoding match {
      case KeyEncoding.FixedWidth =>
        require(parts.forall(_.width.isDefined), "FixedWidth keys require a width on every part")
      case _ => ()
    }
    def partNames: Seq[String] = parts.map(_.name)
    def rewritable: Boolean = encoding != KeyEncoding.Opaque
  }
}

// ---------------------------------------------------------------------------
// 2. Time / version selection
// ---------------------------------------------------------------------------

/**
 * Cell timestamp window and version limit.
 *
 * Bigtable timestamps are MICROseconds. Helpers convert for you.
 */
final case class CellWindow(
    startMicrosClosed: Option[Long] = None,
    endMicrosOpen: Option[Long] = None,
    maxVersions: Int = 1
) {
  require(maxVersions >= 1, "maxVersions must be >= 1")
  def isDefault: Boolean = startMicrosClosed.isEmpty && endMicrosOpen.isEmpty && maxVersions == 1
}

object CellWindow {
  val latest: CellWindow = CellWindow()

  def betweenMillis(startInclusive: Long, endExclusive: Long, maxVersions: Int = 1): CellWindow =
    CellWindow(Some(startInclusive * 1000L), Some(endExclusive * 1000L), maxVersions)

  def between(start: Instant, end: Instant, maxVersions: Int = 1): CellWindow =
    betweenMillis(start.toEpochMilli, end.toEpochMilli, maxVersions)

  def asOf(instant: Instant): CellWindow =
    CellWindow(None, Some(instant.toEpochMilli * 1000L), 1)

  def sinceMillis(startInclusive: Long, maxVersions: Int = 1): CellWindow =
    CellWindow(Some(startInclusive * 1000L), None, maxVersions)
}

// ---------------------------------------------------------------------------
// 3. Source declaration
// ---------------------------------------------------------------------------

sealed trait CatalogRef
object CatalogRef {
  final case class Resource(path: String) extends CatalogRef
  final case class LocalFile(path: String) extends CatalogRef
  final case class Inline(json: String) extends CatalogRef
}

/**
 * A key-lookup join instead of a scan: fetch only the row keys present in
 * `sourceDf.<keyColumn>`.
 */
final case class KeyLookup(sourceDf: DataFrame, keyColumn: String)

final case class BigtableTableSpec(
    name: String,
    projectId: String,
    instanceId: String,
    catalog: CatalogRef,
    rowKey: RowKeyModel,
    keyfilePath: Option[String] = None,
    appProfileId: Option[String] = None,
    cellWindow: CellWindow = CellWindow.latest,
    pushDownCellFilter: Boolean = true,
    exposeKeyParts: Boolean = true,
    keyLookup: Option[KeyLookup] = None,
    extraRowFilterB64: Option[String] = None,
    extraOptions: Map[String, String] = Map.empty
)

// ---------------------------------------------------------------------------
// 4. Catalog
// ---------------------------------------------------------------------------

final class BigtableCatalog(val root: ObjectNode) {

  def tableName: String =
    Option(root.get("table")).flatMap(t => Option(t.get("name"))).map(_.asText).getOrElse("<unknown>")

  def rowkeySpec: String = Option(root.get("rowkey")).map(_.asText).getOrElse("")

  private def obj(name: String): Option[ObjectNode] =
    Option(root.get(name)).collect { case o: ObjectNode => o }

  def columnNames: Set[String] = obj("columns").map(_.fieldNames.asScala.toSet).getOrElse(Set.empty)
  def regexColumnNames: Set[String] = obj("regexColumns").map(_.fieldNames.asScala.toSet).getOrElse(Set.empty)
  def allDfColumns: Set[String] = columnNames ++ regexColumnNames

  def rowkeyDfColumns: Set[String] =
    obj("columns")
      .map(_.fields.asScala
        .filter(e => Option(e.getValue.get("cf")).exists(_.asText == "rowkey"))
        .map(_.getKey).toSet)
      .getOrElse(Set.empty)

  /** True if the CATALOG itself declares a compound key (":" in rowkey spec). */
  def declaresCompoundKey: Boolean = rowkeySpec.contains(":") || rowkeyDfColumns.size > 1

  def cellColumns: Seq[(String, String)] =
    obj("columns").map(_.fields.asScala.toSeq.flatMap { e =>
      val cf = Option(e.getValue.get("cf")).map(_.asText).getOrElse("")
      val q  = Option(e.getValue.get("col")).map(_.asText).getOrElse(e.getKey)
      if (cf == "rowkey" || cf.isEmpty) None else Some(cf -> q)
    }).getOrElse(Seq.empty)

  def regexCellColumns: Seq[(String, String)] =
    obj("regexColumns").map(_.fields.asScala.toSeq.flatMap { e =>
      val cf = Option(e.getValue.get("cf")).map(_.asText).getOrElse("")
      val p  = Option(e.getValue.get("pattern")).map(_.asText).getOrElse("\\C*")
      if (cf.isEmpty) None else Some(cf -> p)
    }).getOrElse(Seq.empty)

  def prunedTo(keep: Set[String]): BigtableCatalog = {
    if (keep.isEmpty) return this
    val required = keep ++ rowkeyDfColumns
    val copy = root.deepCopy[ObjectNode]()
    Seq("columns", "regexColumns").foreach { section =>
      Option(copy.get(section)).collect { case o: ObjectNode => o }.foreach { node =>
        node.fieldNames.asScala.toList.foreach(f => if (!required.contains(f)) node.remove(f))
        if (node.size() == 0) copy.remove(section)
      }
    }
    new BigtableCatalog(copy)
  }

  def json: String = BigtableCatalog.mapper.writeValueAsString(root)
  override def toString: String = json
}

object BigtableCatalog {
  private[bigtable] val mapper = new ObjectMapper()

  def parse(json: String): BigtableCatalog = mapper.readTree(json) match {
    case o: ObjectNode => new BigtableCatalog(o)
    case _: JsonNode   => throw new IllegalArgumentException("Bigtable catalog must be a JSON object")
  }

  def load(ref: CatalogRef): BigtableCatalog = ref match {
    case CatalogRef.Inline(j) => parse(j)
    case CatalogRef.LocalFile(p) =>
      val src = Source.fromFile(resolveDistributedPath(p), "UTF-8")
      try parse(nonEmpty(src.mkString.trim, p)) finally src.close()
    case CatalogRef.Resource(p) =>
      val stream = Option(Thread.currentThread().getContextClassLoader.getResourceAsStream(p))
        .getOrElse(throw new IllegalStateException(s"Bigtable catalog resource not found: $p"))
      val src = Source.fromInputStream(stream, "UTF-8")
      try parse(nonEmpty(src.mkString.trim, p)) finally src.close()
  }

  private def nonEmpty(s: String, where: String): String = {
    require(s.nonEmpty, s"Bigtable catalog is empty: $where"); s
  }

  private[bigtable] def resolveDistributedPath(configured: String): String = {
    val f = new File(configured)
    if (f.exists()) configured
    else {
      val localized = Try(SparkFiles.get(f.getName)).toOption.orNull
      if (localized != null && new File(localized).exists()) localized else configured
    }
  }
}

// ---------------------------------------------------------------------------
// 5. Server-side RowFilter
// ---------------------------------------------------------------------------

object RowFilterBuilder extends Logging {

  def build(
      catalog: BigtableCatalog,
      window: CellWindow,
      includeColumnFilter: Boolean
  ): Option[String] = {

    val branches: Seq[Filters.Filter] =
      if (!includeColumnFilter) Seq.empty
      else
        catalog.cellColumns.groupBy(_._1).toSeq.map { case (cf, pairs) =>
          val quals = pairs.map(_._2).distinct
          val qf =
            if (quals.size == 1) FILTERS.qualifier().exactMatch(quals.head)
            else {
              val i = FILTERS.interleave()
              quals.foreach(q => i.filter(FILTERS.qualifier().exactMatch(q)))
              i
            }
          FILTERS.chain().filter(FILTERS.family().exactMatch(cf)).filter(qf)
        } ++ catalog.regexCellColumns.map { case (cf, pattern) =>
          FILTERS.chain()
            .filter(FILTERS.family().exactMatch(cf))
            .filter(FILTERS.qualifier().regex(pattern))
        }

    if (branches.isEmpty && window.isDefault) return None

    val chain = FILTERS.chain()

    if (branches.size == 1) chain.filter(branches.head)
    else if (branches.size > 1) {
      val i = FILTERS.interleave()
      branches.foreach(i.filter)
      chain.filter(i)
    }

    // Timestamp window before the version limit, so "latest within window" wins.
    if (window.startMicrosClosed.isDefined || window.endMicrosOpen.isDefined) {
      var r = FILTERS.timestamp().range()
      window.startMicrosClosed.foreach(s => r = r.startClosed(s))
      window.endMicrosOpen.foreach(e => r = r.endOpen(e))
      chain.filter(r)
    }
    chain.filter(FILTERS.limit().cellsPerColumn(window.maxVersions))

    Some(BaseEncoding.base64().encode(chain.toProto.toByteArray))
  }
}

// ---------------------------------------------------------------------------
// 6. SQL analysis: projection + compound-key predicate extraction
// ---------------------------------------------------------------------------

final case class KeyPrefixPredicate(
    equalityPrefix: String,
    lowerBoundInclusive: Option[String],
    upperBoundExclusive: Option[String]
) {
  def isEmpty: Boolean =
    equalityPrefix.isEmpty && lowerBoundInclusive.isEmpty && upperBoundExclusive.isEmpty
}

object SqlAnalyzer extends Logging {

  /** Referenced columns, or None when a `*` appears (keep everything). */
  def referencedColumns(spark: SparkSession, sql: String): Option[Set[String]] =
    parse(spark, sql).flatMap { plan =>
      val exprs = plan.flatMap(_.expressions)
      if (exprs.exists(_.exists(_.isInstanceOf[UnresolvedStar]))) None
      else {
        val names = exprs.flatMap(e => e.collect { case a: UnresolvedAttribute => a.nameParts.last }).toSet
        if (names.isEmpty) None else Some(names)
      }
    }

  /**
   * Pull top-level AND-ed literal predicates on the compound key parts and
   * turn them into a prefix / range predicate on the flat row-key column.
   *
   * Sound only for a LEADING run of equalities, optionally followed by ONE
   * ranged part. Anything under an OR or a NOT is ignored (left to Spark).
   */
  def keyPrefixFor(
      spark: SparkSession,
      sql: String,
      key: RowKeyModel.Compound
  ): Option[KeyPrefixPredicate] = {
    if (!key.rewritable) return None

    val conjuncts: Seq[Expression] = parse(spark, sql).toSeq.flatMap { plan =>
      plan.collect { case f: LogicalFilter => f.condition }.flatMap(splitConjuncts)
    }
    if (conjuncts.isEmpty) return None

    val eq = collection.mutable.Map.empty[String, String]
    val lo = collection.mutable.Map.empty[String, String]
    val hi = collection.mutable.Map.empty[String, String]

    conjuncts.foreach { c =>
      binary(c).foreach { case (op, col, lit) =>
        op match {
          case "="  => eq(col) = lit
          case ">=" => lo(col) = lit
          case ">"  => lo(col) = lit + "\u0000" // conservative: treat as >= next
          case "<"  => hi(col) = lit
          case "<=" => hi(col) = lit + "\uffff"
          case _    => ()
        }
      }
    }

    val sep = key.encoding match {
      case KeyEncoding.Delimited(s) => s
      case _                        => ""
    }

    // Longest leading run of equalities.
    val leading = key.partNames.takeWhile(eq.contains)
    if (leading.isEmpty && !key.partNames.headOption.exists(p => lo.contains(p) || hi.contains(p)))
      return None

    val prefixParts = leading.map { p => pad(eq(p), key, p) }
    val prefix = if (prefixParts.isEmpty) "" else prefixParts.mkString(sep) + sep

    // The one part immediately after the equality run may carry a range.
    val nextPart = key.partNames.drop(leading.size).headOption
    val lower = nextPart.flatMap(lo.get).map(v => prefix + pad(v, key, nextPart.get))
    val upper = nextPart.flatMap(hi.get).map(v => prefix + pad(v, key, nextPart.get))

    val pred = KeyPrefixPredicate(prefix, lower, upper)
    if (pred.isEmpty) None
    else {
      logInfo(s"Compound key rewrite -> prefix='${pred.equalityPrefix}' " +
        s"lo=${pred.lowerBoundInclusive.getOrElse("-")} hi=${pred.upperBoundExclusive.getOrElse("-")}")
      Some(pred)
    }
  }

  private def pad(value: String, key: RowKeyModel.Compound, partName: String): String =
    key.encoding match {
      case KeyEncoding.FixedWidth =>
        val w = key.parts.find(_.name == partName).flatMap(_.width).getOrElse(value.length)
        if (value.length >= w) value.take(w) else value + ("\u0000" * (w - value.length))
      case _ => value
    }

  private def splitConjuncts(e: Expression): Seq[Expression] =
    e.getClass.getSimpleName match {
      case "And" => e.children.flatMap(splitConjuncts)
      case _     => Seq(e)
    }

  /** (operator, columnName, stringLiteral) for simple attr-op-literal nodes. */
  private def binary(e: Expression): Option[(String, String, String)] = {
    val op = e.getClass.getSimpleName match {
      case "EqualTo"            => "="
      case "GreaterThan"        => ">"
      case "GreaterThanOrEqual" => ">="
      case "LessThan"           => "<"
      case "LessThanOrEqual"    => "<="
      case _                    => return None
    }
    e.children match {
      case Seq(a: UnresolvedAttribute, lit) if isLiteral(lit) =>
        Some((op, a.nameParts.last, literalString(lit)))
      case Seq(lit, a: UnresolvedAttribute) if isLiteral(lit) =>
        Some((flip(op), a.nameParts.last, literalString(lit)))
      case _ => None
    }
  }

  private def isLiteral(e: Expression): Boolean = e.getClass.getSimpleName == "Literal"
  private def literalString(e: Expression): String = Option(e.eval(null)).map(_.toString).getOrElse("")
  private def flip(op: String): String = op match {
    case ">" => "<"; case ">=" => "<="; case "<" => ">"; case "<=" => ">="; case o => o
  }

  private def parse(spark: SparkSession, sql: String) =
    Try(spark.sessionState.sqlParser.parsePlan(sql)) match {
      case Success(p) => Some(p)
      case Failure(e) =>
        logWarning(s"SQL not parseable for optimisation, falling back to plain scan: ${e.getMessage}")
        None
    }
}

// ---------------------------------------------------------------------------
// 7. joinWithBigtable
// ---------------------------------------------------------------------------

/**
 * Isolated so there is exactly ONE place to adjust if the connector's join
 * signature differs on your cluster's version.
 */
object BigtableJoinSupport extends Logging {

  def join(
      spark: SparkSession,
      lookup: KeyLookup,
      readerOptions: Map[String, String]
  ): DataFrame = {
    import com.google.cloud.spark.bigtable.join.BigtableJoinImplicit._
    logInfo(s"Key-lookup join on '${lookup.keyColumn}' " +
      s"(${lookup.sourceDf.rdd.getNumPartitions} source partitions)")
    // Sorting by the key column materially improves Bigtable read locality --
    // each partition then covers a contiguous key range.
    val sorted = lookup.sourceDf.sortWithinPartitions(F.col(lookup.keyColumn))
    sorted.joinWithBigtable(readerOptions, lookup.keyColumn)
  }
}

// ---------------------------------------------------------------------------
// 8. The source
// ---------------------------------------------------------------------------

object BigtableSqlSource extends Logging {

  private val Format = "com.google.cloud.spark.bigtable.BigtableDefaultSource"
  private val ProviderOption = "spark.bigtable.auth.credentials_provider"
  private val KeyfileArg = "spark.bigtable.auth.credentials_provider.args.keyfile"
  private val RowFiltersOption = "spark.bigtable.read.row.filters"

  def sql(spark: SparkSession, statement: String, specs: Seq[BigtableTableSpec]): DataFrame = {
    require(specs.nonEmpty, "At least one BigtableTableSpec must be declared")
    val referenced = SqlAnalyzer.referencedColumns(spark, statement)

    specs.foreach { spec =>
      val df = load(spark, spec, referenced, Some(statement))
      df.createOrReplaceTempView(spec.name)
      logInfo(s"Registered view '${spec.name}': ${df.schema.simpleString}")
    }

    logInfo(s"Executing Bigtable SQL:\n$statement")
    spark.sql(statement)
  }

  def load(
      spark: SparkSession,
      spec: BigtableTableSpec,
      referencedColumns: Option[Set[String]] = None,
      statement: Option[String] = None
  ): DataFrame = {

    val full = BigtableCatalog.load(spec.catalog)

    if (full.declaresCompoundKey) {
      logWarning(
        s"[${spec.name}] the CATALOG declares a compound row key. No row-key predicate will be " +
          "pushed down and every query becomes a full scan. Publish a flat single-column row-key " +
          "catalog and describe the parts with RowKeyModel.Compound instead.")
    }

    // -- projection pruning; key parts are derived, so keep the flat key col --
    val flatKeyCol = spec.rowKey.flatColumn
    val pruned = referencedColumns match {
      case Some(cols) =>
        val wanted = (cols + flatKeyCol).map(_.toLowerCase)
        val matched = full.allDfColumns.filter(c => wanted.contains(c.toLowerCase))
        if (matched.isEmpty) full
        else {
          val p = full.prunedTo(matched)
          logInfo(s"[${spec.name}] catalog pruned ${full.allDfColumns.size} -> ${p.allDfColumns.size}: " +
            p.allDfColumns.toSeq.sorted.mkString(", "))
          p
        }
      case None => full
    }

    val options = buildOptions(spec, pruned)

    // -- scan or key-lookup join --------------------------------------------
    var df = spec.keyLookup match {
      case Some(lookup) => BigtableJoinSupport.join(spark, lookup, options)
      case None =>
        var r = spark.read.format(Format)
        options.foreach { case (k, v) => r = r.option(k, v) }
        r.load()
    }

    // -- compound key: push a prefix/range, then expose the parts -----------
    spec.rowKey match {
      case ck: RowKeyModel.Compound if spec.keyLookup.isEmpty =>
        statement.flatMap(s => SqlAnalyzer.keyPrefixFor(spark, s, ck)).foreach { p =>
          df = df.filter(prefixCondition(flatKeyCol, p))
        }
        if (spec.exposeKeyParts) df = withKeyParts(df, ck)
      case ck: RowKeyModel.Compound =>
        if (spec.exposeKeyParts) df = withKeyParts(df, ck)
      case _ => ()
    }

    df
  }

  private def buildOptions(spec: BigtableTableSpec, catalog: BigtableCatalog): Map[String, String] = {
    val b = collection.mutable.LinkedHashMap[String, String](
      "catalog" -> catalog.json,
      "spark.bigtable.project.id" -> spec.projectId,
      "spark.bigtable.instance.id" -> spec.instanceId
    )
    spec.keyfilePath.foreach { kf =>
      b += ProviderOption -> classOf[ServiceAccountJsonCredentialsProvider].getName
      b += KeyfileArg -> kf
    }
    spec.appProfileId.foreach(id => b += "spark.bigtable.app_profile.id" -> id)

    val generated = RowFilterBuilder.build(catalog, spec.cellWindow, spec.pushDownCellFilter)
    val filter = spec.extraRowFilterB64.orElse(generated)
    if (spec.extraRowFilterB64.isDefined && generated.isDefined)
      logWarning(s"[${spec.name}] extraRowFilterB64 overrides the generated cell/time filter")
    filter.foreach(f => b += RowFiltersOption -> f)

    b ++= spec.extraOptions
    b.toMap
  }

  private def prefixCondition(flatCol: String, p: KeyPrefixPredicate): Column = {
    val c = F.col(flatCol)
    var cond: Column = F.lit(true)
    if (p.equalityPrefix.nonEmpty) cond = cond && c.startsWith(p.equalityPrefix)
    p.lowerBoundInclusive.foreach(v => cond = cond && (c >= F.lit(v)))
    p.upperBoundExclusive.foreach(v => cond = cond && (c < F.lit(v)))
    cond
  }

  /** Re-derive the logical key parts so SQL can filter/group on them. */
  private def withKeyParts(df: DataFrame, key: RowKeyModel.Compound): DataFrame = {
    val src = F.col(key.flatColumn)
    key.encoding match {
      case KeyEncoding.Delimited(sep) =>
        val split = F.split(src, java.util.regex.Pattern.quote(sep))
        key.parts.zipWithIndex.foldLeft(df) { case (acc, (part, i)) =>
          acc.withColumn(part.name, split.getItem(i))
        }
      case KeyEncoding.FixedWidth =>
        var offset = 1 // substring is 1-based
        key.parts.foldLeft(df) { case (acc, part) =>
          val w = part.width.get
          val out = acc.withColumn(part.name, F.substring(src, offset, w))
          offset += w
          out
        }
      case KeyEncoding.Opaque => df
    }
  }
}

// ---------------------------------------------------------------------------
// 9. Auth
// ---------------------------------------------------------------------------

class ServiceAccountJsonCredentialsProvider(args: Map[String, String])
    extends CredentialsProvider
    with Serializable {

  private val scopes = Arrays.asList(
    "https://www.googleapis.com/auth/bigtable.data",
    "https://www.googleapis.com/auth/cloud-platform"
  )

  override def getCredentials: Credentials = {
    val configured = args.getOrElse(
      "spark.bigtable.auth.credentials_provider.args.keyfile",
      throw new IllegalArgumentException(
        "Missing credential provider option: spark.bigtable.auth.credentials_provider.args.keyfile"))
    val stream = new FileInputStream(BigtableCatalog.resolveDistributedPath(configured))
    try ServiceAccountCredentials.fromStream(stream).createScoped(scopes)
    finally stream.close()
  }
}

// ---------------------------------------------------------------------------
// 10. Example driver
// ---------------------------------------------------------------------------

object BigtableSqlJob extends Logging {

  def main(args: Array[String]): Unit = {

    val spark = SparkSession.builder()
      .appName("Bigtable SQL Source")
      .master("yarn")
      .getOrCreate()

    val keyfile = "/apps/dat/etlcodicd/dev/tesla/certs/sa-sandbox-corp-cap-617d-cw.json"

    try {
      // ---- table A: single-column row key -------------------------------
      val simple = BigtableTableSpec(
        name = "ibb_csg_tbl",
        projectId = "sandbox-corp-cap-dev1-617d",
        instanceId = "cap-dev1-btinstance",
        catalog = CatalogRef.Resource("bigtable/ibb_csg_tbl_catalog.json"),
        rowKey = RowKeyModel.Single("rowkey"),
        keyfilePath = Some(keyfile)
      )

      BigtableSqlSource
        .sql(spark,
          """SELECT rowkey, features, insights
            |FROM ibb_csg_tbl
            |WHERE rowkey >= 'CUST#0001' AND rowkey < 'CUST#0500'
            |LIMIT 10""".stripMargin,
          Seq(simple))
        .show(10, truncate = false)

      // ---- table B: compound key, delimited, with a time window ----------
      val compound = BigtableTableSpec(
        name = "cust_events",
        projectId = "sandbox-corp-cap-dev1-617d",
        instanceId = "cap-dev1-btinstance",
        catalog = CatalogRef.Resource("bigtable/cust_events_catalog.json"),
        rowKey = RowKeyModel.Compound(
          flatColumn = "rowkey",
          parts = Seq(KeyPart("cust_id"), KeyPart("region"), KeyPart("event_day")),
          encoding = KeyEncoding.Delimited("|")
        ),
        keyfilePath = Some(keyfile),
        // only cells written in the last 30 days, latest version each
        cellWindow = CellWindow.sinceMillis(System.currentTimeMillis() - 30L * 86400000L)
      )

      // cust_id = ... AND region = ... is a LEADING equality run, so this
      // becomes a Bigtable row-range scan rather than a full table scan.
      BigtableSqlSource
        .sql(spark,
          """SELECT cust_id, region, event_day, features
            |FROM cust_events
            |WHERE cust_id = 'CUST#0001' AND region = 'EU' AND event_day >= '2026-08-01'""".stripMargin,
          Seq(compound))
        .show(20, truncate = false)

      // ---- table C: key-lookup join instead of a scan --------------------
      val driverKeys = spark.table("hive_db.customer_batch").select("cust_key")
      val lookupSpec = simple.copy(
        name = "ibb_csg_lookup",
        keyLookup = Some(KeyLookup(driverKeys, "cust_key"))
      )

      BigtableSqlSource
        .sql(spark, "SELECT cust_key, features FROM ibb_csg_lookup", Seq(lookupSpec))
        .show(20, truncate = false)

    } finally {
      spark.stop()
      logInfo("Spark session stopped")
    }
  }
}
