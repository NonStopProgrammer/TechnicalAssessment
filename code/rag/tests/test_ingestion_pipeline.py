from pathlib import Path

import pytest

from rag.ingestion.pipeline import ingest_file
from rag.retrieval.pipeline import retrieve
from shared.db.base import init_db, session_scope
from shared.db.models import DocumentRegistry

CORPUS_DIR = Path(__file__).resolve().parents[1] / "corpus" / "sample_documents"


@pytest.fixture(scope="module", autouse=True)
def _init_database():
    init_db()


def test_ingest_file_registers_document_and_indexes_chunks():
    # This corpus is also ingested by other test modules' fixtures sharing
    # this session's DB/vector store (see conftest.py) — so `outcome.status`
    # here may legitimately be "ingested" or "skipped_duplicate" depending
    # on pytest's collection order. What must hold either way is the
    # *persisted* state, which is what this test actually checks.
    outcome = ingest_file(CORPUS_DIR / "rbi_kyc_master_direction.md")
    assert outcome.status in ("ingested", "skipped_duplicate")

    with session_scope() as db:
        row = db.get(DocumentRegistry, "rbi-kyc-master-direction")
        assert row is not None
        assert row.framework == "rbi"
        assert row.ingestion_status == "ingested"


def test_reingesting_identical_file_is_a_noop():
    # Regardless of whether this file was already ingested by an earlier
    # test module, a *second* call back-to-back with identical bytes must
    # always be a no-op — that invariant is RAG-1.4 itself and holds
    # independent of suite-wide ordering.
    ingest_file(CORPUS_DIR / "rbi_priority_sector_lending.md")
    second = ingest_file(CORPUS_DIR / "rbi_priority_sector_lending.md")

    assert second.status == "skipped_duplicate"


def test_retrieval_finds_relevant_chunk_after_ingestion():
    ingest_file(CORPUS_DIR / "mifid_ii_appropriateness.md")

    result = retrieve(
        "What is required before selling a complex product to a retail client?",
        jurisdictions=["EU"],
    )

    assert result.has_usable_context
    assert any(c.chunk.doc_id == "mifid-ii-investor-protection" for c in result.chunks)


def test_ingesting_amendment_marks_prior_version_superseded():
    # As above: whichever test module ingests the 2023 amendment *first*
    # in the session is the one that actually triggers the superseded-by
    # marking (see rag/ingestion/pipeline.py::ingest_file — a duplicate-
    # skip short-circuits before that marking step runs). What must hold
    # is the end state in the registry, checked below.
    ingest_file(CORPUS_DIR / "basel_iii_capital_adequacy_2019.md")
    outcome = ingest_file(CORPUS_DIR / "basel_iii_capital_adequacy_2023.md")

    assert outcome.status in ("ingested", "skipped_duplicate")
    with session_scope() as db:
        old = db.get(DocumentRegistry, "basel-iii-capital-adequacy-2019")
        assert old is not None
        assert old.superseded_by == "basel-iii-capital-adequacy-2023"
