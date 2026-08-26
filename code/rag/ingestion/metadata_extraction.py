"""RAG-1.3: normalizes a parsed document's front-matter into a validated
DocumentMetadata record, computing the checksum RAG-1.4 idempotency relies on.
"""

from datetime import date

from rag.exceptions import UnparseableDocumentError
from rag.ingestion.parsers import ParsedDocument
from shared.enums import DocType, Framework, Jurisdiction
from shared.ids import checksum_of, new_doc_id
from shared.models.document import DocumentMetadata

_REQUIRED_FIELDS = ("title", "framework", "jurisdiction", "doc_type", "effective_date", "version")


def extract_metadata(parsed: ParsedDocument) -> DocumentMetadata:
    fm = parsed.front_matter
    missing = [f for f in _REQUIRED_FIELDS if f not in fm]
    if missing:
        raise UnparseableDocumentError(
            parsed.source_uri, f"missing required metadata field(s): {', '.join(missing)}"
        )

    effective_date = fm["effective_date"]
    if isinstance(effective_date, str):
        effective_date = date.fromisoformat(effective_date)

    doc_id = fm.get("doc_id") or new_doc_id(fm["title"])
    checksum = checksum_of(parsed.raw_text.encode("utf-8"))

    return DocumentMetadata(
        doc_id=doc_id,
        title=fm["title"],
        framework=Framework(fm["framework"]),
        jurisdiction=Jurisdiction(fm["jurisdiction"]),
        doc_type=DocType(fm["doc_type"]),
        effective_date=effective_date,
        version=str(fm["version"]),
        supersedes_doc_id=fm.get("supersedes_doc_id"),
        checksum=checksum,
        source_uri=parsed.source_uri,
    )
