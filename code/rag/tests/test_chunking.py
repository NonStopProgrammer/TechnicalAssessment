from datetime import date

from rag.chunking.clause_chunker import chunk_document, split_into_clauses
from shared.enums import DocType, Framework, Jurisdiction
from shared.models.document import DocumentMetadata

SAMPLE_TEXT = """
## 6. Minimum Capital Requirements

### 6.1 Common Equity Tier 1 Ratio
Banks must maintain a CET1 ratio of at least 4.5% of risk-weighted assets.

### 6.2 Tier 1 Capital Ratio
Tier 1 capital must be at least 6.0% of risk-weighted assets.
"""


def _metadata(**overrides) -> DocumentMetadata:
    defaults = dict(
        doc_id="doc_test",
        title="Test Doc",
        framework=Framework.BASEL_III,
        jurisdiction=Jurisdiction.GLOBAL,
        doc_type=DocType.REGULATION,
        effective_date=date(2023, 1, 1),
        version="2023-01-01",
        checksum="abc123",
        source_uri="test://doc",
    )
    defaults.update(overrides)
    return DocumentMetadata(**defaults)


def test_split_into_clauses_detects_numbered_headings():
    sections = split_into_clauses(SAMPLE_TEXT)
    clause_ids = [s.clause_id for s in sections]

    assert "6" in clause_ids
    assert "6.1" in clause_ids
    assert "6.2" in clause_ids


def test_split_into_clauses_falls_back_to_whole_document_when_no_headings():
    sections = split_into_clauses("No numbered headings here, just prose.")
    assert len(sections) == 1
    assert sections[0].clause_id == "0"


def test_chunk_document_inherits_metadata_and_builds_citation_key():
    metadata = _metadata()
    chunks = chunk_document(SAMPLE_TEXT, metadata)

    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.doc_id == metadata.doc_id
        assert chunk.framework == metadata.framework
        assert chunk.version == metadata.version
        # RAG-6.1 citation key format is `{doc_id}#{clause_id}@{version}` —
        # distinct from chunk_id's `::` separator, which is an internal
        # identifier only (see shared/ids.py::citation_key).
        assert chunk.citation_key.startswith(f"{metadata.doc_id}#")
        assert chunk.citation_key.endswith(f"@{metadata.version}")


def test_chunk_document_never_spans_two_documents():
    """RAG-2.5: each call only ever sees one document's text."""
    metadata_a = _metadata(doc_id="doc_a")
    metadata_b = _metadata(doc_id="doc_b")

    chunks_a = chunk_document(SAMPLE_TEXT, metadata_a)
    chunks_b = chunk_document(SAMPLE_TEXT, metadata_b)

    assert all(c.doc_id == "doc_a" for c in chunks_a)
    assert all(c.doc_id == "doc_b" for c in chunks_b)


def test_large_clause_is_split_with_overlap():
    long_clause = "## 1. Long Clause\n" + ("This is a dense regulatory sentence. " * 200)
    metadata = _metadata()
    chunks = chunk_document(long_clause, metadata)

    assert len(chunks) > 1
    assert all(c.clause_id.startswith("1") for c in chunks)
