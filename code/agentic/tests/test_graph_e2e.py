"""End-to-end: the full AGENT-1.7 skeleton against the assignment's 4
reference transaction scenarios plus one ambiguous-input case, run through
the same `run_screening` entry point the backend API and MCP server use.
Self-contained (ingests the corpus + seeds transactions itself) so it does
not depend on pytest's collection order across other test packages.
"""

from pathlib import Path

import pytest

from agentic.graph.build_graph import run_screening
from agentic.tools.get_transaction_details import get_transaction_details, seed_transactions
from rag.ingestion.pipeline import ingest_directory
from shared.db.base import init_db
from shared.enums import AssessmentStatus, RiskRating

CORPUS_DIR = Path(__file__).resolve().parents[2] / "rag" / "corpus" / "sample_documents"


@pytest.fixture(scope="module", autouse=True)
def _setup_corpus_and_transactions():
    init_db()
    ingest_directory(CORPUS_DIR)
    seed_transactions()


@pytest.mark.parametrize("transaction_id", ["TXN-1001", "TXN-1002", "TXN-1003", "TXN-1004", "TXN-1005"])
def test_screening_scenarios_complete_with_a_grounded_assessment(transaction_id):
    transaction = get_transaction_details(transaction_id)
    assessment = run_screening(transaction, request_id=f"test-{transaction_id}")

    assert assessment.status in (AssessmentStatus.COMPLETED, AssessmentStatus.NEEDS_REVIEW)
    assert assessment.risk_rating.severity >= RiskRating.MEDIUM.severity
    assert assessment.provenance is not None
    assert assessment.provenance.prompt_template_id == "transaction_screening"


def test_scenario_1_carries_rbi_citation_and_required_action():
    transaction = get_transaction_details("TXN-1001")
    assessment = run_screening(transaction, request_id="test-TXN-1001-detail")

    assert any(c.framework.value == "rbi" for c in assessment.citations)
    assert assessment.required_actions


def test_ambiguous_scenario_5_records_missing_facts_not_silent_compliance():
    transaction = get_transaction_details("TXN-1005")
    assessment = run_screening(transaction, request_id="test-TXN-1005-detail")

    assert assessment.missing_facts
    assert assessment.risk_rating.severity >= RiskRating.MEDIUM.severity


def test_assessment_provenance_references_retrieved_chunks():
    transaction = get_transaction_details("TXN-1002")
    assessment = run_screening(transaction, request_id="test-TXN-1002-provenance")

    assert len(assessment.provenance.retrieved_chunk_ids) > 0
