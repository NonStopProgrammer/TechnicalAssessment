# RAG Pipeline Requirements

Covers rubric item **1A.2 RAG Pipeline Design** and implementation target **2A**. See
`ADR-001-vector-database-selection.md` for the vector DB trade-off analysis and
`10-technology-stack.md` for the consolidated tool choices referenced below.

---

## RAG-1 — Document ingestion

| ID | Requirement | Detail |
|---|---|---|
| RAG-1.1 | Multi-format ingestion | PDF (native + scanned/OCR fallback), DOCX, HTML circulars. Parser: **Unstructured.io** (open source) — handles layout-aware extraction (tables, numbered clauses) better than raw `pdftotext`, which matters because regulatory citations must resolve to a specific clause. |
| RAG-1.2 | Source connectors | Manual upload (prototype) + scheduled pull connectors for RBI/regulator publication pages (production) |
| RAG-1.3 | Metadata extraction at ingest time | `framework` (Basel III / MiFID II / RBI), `jurisdiction`, `doc_type` (master direction / circular / amendment), `effective_date`, `version`, `supersedes_doc_id` |
| RAG-1.4 | Idempotent ingestion | Re-ingesting the same document (same checksum) is a no-op; ingesting a new version creates a new versioned record, does not overwrite |
| RAG-1.5 | Ingestion is orchestrated, not ad hoc | **Apache Airflow** DAG: fetch → parse → clean → chunk → embed → upsert → impact-scan trigger (`FR-3.1`). Auditable run history is a side effect we want (ties into `SEC-2`). |
| RAG-1.6 | Minimum prototype corpus | ≥5 documents spanning all 3 frameworks (assignment requirement for 2A), sourced from publicly available RBI circulars / Basel III excerpts |

## RAG-2 — Chunking strategy

| ID | Requirement | Detail |
|---|---|---|
| RAG-2.1 | Clause-bounded semantic chunking | Regulatory documents are numbered-clause structured. Primary split is on detected clause/section boundaries (regex over numbering patterns, e.g. `\d+\.\d+`, `Para \d+`), **not** a fixed character window blind to structure. |
| RAG-2.2 | Size fallback | Where a clause exceeds the target size, recursively split with `RecursiveCharacterTextSplitter` (LangChain) using paragraph → sentence boundaries. |
| RAG-2.3 | Target size & overlap | ~512 tokens per chunk, ~15% (≈75 token) overlap. **Justification:** 512 tokens is large enough to keep a clause's operative sentence and its qualifying conditions together (regulatory text is dense with cross-referencing sub-clauses), small enough to keep re-ranking and multi-chunk context assembly cheap. Overlap prevents a threshold number/date from being severed at a chunk boundary — a known failure mode for compliance text where "≥25%" losing its number is a materially wrong retrieval. |
| RAG-2.4 | Chunk-level metadata inheritance | Every chunk inherits parent document metadata (`RAG-1.3`) plus its own `clause_id`/`section_path`, so a citation can point to the exact clause, not just the document. |
| RAG-2.5 | No cross-document chunking | Chunks never span two source documents, even adjacent ones in a batch ingest. |

## RAG-3 — Embedding model & vector database

| ID | Requirement | Detail |
|---|---|---|
| RAG-3.1 | Embedding model | **BAAI/bge-large-en-v1.5** (1024-dim, open source, Apache 2.0, self-hosted via HuggingFace Text Embeddings Inference). Chosen for strong MTEB retrieval performance in its size class and clean self-hosting story. See `ADR-001` for the comparison. |
| RAG-3.2 | Vector database | **Qdrant** (open source, Apache 2.0, self-hosted on EKS). Native hybrid (dense + sparse) search, rich payload filtering (needed for jurisdiction/framework/version filters), snapshotting for version rollback. Full trade-off vs. Weaviate/Milvus/pgvector in `ADR-001-vector-database-selection.md`. |
| RAG-3.3 | Collection design | One Qdrant collection per (region), partitioned logically by `framework`/`jurisdiction` payload fields rather than physically separate collections — keeps cross-framework queries (needed for `FR-2.2`) a single query with a filter, not a fan-out. |
| RAG-3.4 | Index freshness SLA | New/updated document is queryable within 15 minutes of ingestion completing (batch upsert, not real-time streaming — regulatory documents are not high-frequency). |

## RAG-4 — Retrieval strategy

| ID | Requirement | Detail |
|---|---|---|
| RAG-4.1 | Hybrid search | Dense (bge embeddings, cosine) + sparse (BM25/SPLADE via Qdrant's native sparse vectors) retrieved in parallel, merged with **Reciprocal Rank Fusion (RRF)**. Rationale: regulatory queries mix semantic intent ("capital adequacy requirements") with exact-term anchors (defined terms, section numbers, statutory thresholds like "25%") that pure dense retrieval under-weights. |
| RAG-4.2 | Candidate set | Top 50 from hybrid fusion passed to re-ranking. |
| RAG-4.3 | Re-ranking | Cross-encoder **BAAI/bge-reranker-large**, self-hosted, reduces 50 → top 8 chunks by query-relevance. |
| RAG-4.4 | Contextual compression | **LLMLingua** (open source) applied to the top-8 chunks before prompt assembly, to control context-window/cost growth as the corpus grows — without dropping the sentence containing a cited threshold/number (compression is instructed to preserve numerals and defined terms verbatim). |
| RAG-4.5 | Metadata filters | Jurisdiction/framework/date filters are applied as hard Qdrant payload filters *before* fusion (not post-filtering after top-k), so a US-market query never surfaces RBI-only content diluting the candidate set. |
| RAG-4.6 | Relevance floor | If the top re-ranked result's score is below a calibrated threshold, treat as "no relevant context" → triggers `FR-1.5` graceful no-answer instead of forcing an LLM answer from weak context. |

## RAG-5 — Versioning & document updates in the vector store

| ID | Requirement | Detail |
|---|---|---|
| RAG-5.1 | Append, don't overwrite | A new version of a regulation is ingested as new chunks with `version`/`effective_date` payload fields; old chunks are marked `superseded_by=<new_doc_id>` rather than deleted. |
| RAG-5.2 | Default retrieval = latest effective version | Retrieval filters `effective_date <= now AND superseded_by IS NULL` by default. |
| RAG-5.3 | Point-in-time queries | `FR-1.4` "as of [date]" queries relax the filter to the version that was effective on the given date — this is why version metadata (not deletion) is mandatory. |
| RAG-5.4 | Registry of record | A Postgres `document_registry` table is the source of truth for the version graph (doc_id, version, supersedes, effective_date, checksum); Qdrant payloads are a denormalized projection of it, rebuildable from Postgres if the vector index needs to be reindexed (e.g., embedding model upgrade). |
| RAG-5.5 | Rollback | Qdrant collection snapshots taken pre-ingestion allow reverting a bad ingest without reprocessing the whole corpus. |

## RAG-6 — Citation & source attribution (cross-cutting with `FR-1.3`)

| ID | Requirement | Detail |
|---|---|---|
| RAG-6.1 | Every returned chunk carries a stable citation key | `{doc_id}#{clause_id}@{version}` |
| RAG-6.2 | Answer generation is instructed (system prompt, `LLM-3`) to cite only from the provided context chunks, by citation key | Enforced structurally, not just by instruction — see `LLM-4.4` citation-verifier guardrail, which rejects any citation key not present in the retrieved set. |

## RAG-7 — Error handling (rubric explicitly calls this out for 2A)

| ID | Requirement | Detail |
|---|---|---|
| RAG-7.1 | Ingestion failure | Malformed/unparseable document → quarantined with a logged reason, does not fail the whole DAG run |
| RAG-7.2 | Embedding service unavailable | Retry with backoff (3 attempts); ingestion DAG task fails loudly (paged) rather than silently skipping embedding |
| RAG-7.3 | Vector DB unavailable at query time | Circuit breaker → `FR-1.5`-style graceful degradation ("search temporarily unavailable"), never a raw 500 to a compliance officer |
| RAG-7.4 | Empty retrieval result | Distinguished from a relevance-floor miss (`RAG-4.6`) in logs, for `08-observability-requirements.md` drift detection |
