"""These call the MCP tool functions directly (not over the wire) — the
`@mcp.tool()` decorator registers with the FastMCP server but leaves the
function itself callable, so this exercises the exact same code path a
real MCP client would trigger without needing a live stdio/SSE session.
"""

from pathlib import Path

import pytest

from fincompliance_mcp.server import (
    answer_compliance_question,
    get_transaction_details,
    screen_seeded_transaction,
    search_regulations,
)
from rag.ingestion.pipeline import ingest_directory
from shared.db.base import init_db

CORPUS_DIR = Path(__file__).resolve().parents[2] / "rag" / "corpus" / "sample_documents"


@pytest.fixture(scope="module", autouse=True)
def _setup():
    init_db()
    ingest_directory(CORPUS_DIR)
    from agentic.tools.get_transaction_details import seed_transactions

    seed_transactions()


def test_search_regulations_tool_returns_cited_chunks():
    result = search_regulations(query="Tier 1 capital ratio requirement", jurisdictions=["IN"])

    assert result["has_usable_context"]
    assert result["chunks"]
    assert "citation_key" in result["chunks"][0]


def test_answer_compliance_question_tool_declines_off_topic():
    result = answer_compliance_question(query="What's a good recipe for lasagna?")
    assert result["status"] == "off_topic"


def test_get_transaction_details_tool_returns_seeded_payload():
    payload = get_transaction_details("TXN-1001")
    assert payload["transaction_type"] == "cross_border_payment"


def test_screen_seeded_transaction_tool_returns_full_assessment():
    assessment = screen_seeded_transaction("TXN-1001")

    assert assessment["risk_rating"] in ("HIGH", "CRITICAL")
    assert assessment["citations"]
    assert assessment["provenance"]["prompt_template_id"] == "transaction_screening"
