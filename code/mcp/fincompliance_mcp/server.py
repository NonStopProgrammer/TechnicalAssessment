"""MCP tool surface. Every tool here is a thin wrapper around a function
that already exists in `agentic/` — this file adds MCP's schema/transport
concerns only, never a second implementation of the underlying logic.
"""

from mcp.server.fastmcp import FastMCP

from agentic.graph.build_graph import run_screening
from agentic.qa import answer_question
from agentic.tools.get_transaction_details import get_transaction_details as _get_seeded_transaction
from agentic.tools.search_regulations import search_regulations as _search_regulations
from shared.config import get_settings
from shared.ids import new_request_id
from shared.models.transaction import TransactionPayload

settings = get_settings()
mcp = FastMCP("finserv-compliance-assistant", host=settings.api_host, port=settings.mcp_port)


@mcp.tool()
def search_regulations(query: str, jurisdictions: list[str] | None = None, framework: str | None = None) -> dict:
    """Search the indexed regulatory corpus (Basel III / MiFID II / RBI)
    and return re-ranked, cited chunks. `jurisdictions` restricts results
    to IN/EU/US; `framework` restricts to basel_iii/mifid_ii/rbi.
    """
    result = _search_regulations(query=query, jurisdictions=jurisdictions, framework=framework)
    return {
        "has_usable_context": result.has_usable_context,
        "chunks": [
            {
                "citation_key": rc.chunk.citation_key,
                "framework": rc.chunk.framework.value,
                "jurisdiction": rc.chunk.jurisdiction.value,
                "text": rc.chunk.text,
                "score": round(rc.final_score, 4),
            }
            for rc in result.chunks
        ],
    }


@mcp.tool()
def answer_compliance_question(query: str, jurisdictions: list[str] | None = None, as_of: str | None = None) -> dict:
    """Answer a natural-language regulatory compliance question with cited,
    version-aware sources (FR-1). Returns "insufficient information in the
    indexed corpus" rather than guessing when the corpus doesn't cover it,
    and a fixed decline if the question is outside compliance/regulatory scope.
    """
    answer = answer_question(query=query, jurisdictions=jurisdictions, as_of=as_of)
    return {
        "answer": answer.answer,
        "status": answer.status,
        "citations": [c.display for c in answer.citations],
    }


@mcp.tool()
def get_transaction_details(transaction_id: str) -> dict:
    """Fetch a seeded transaction's full payload (mocked core-banking
    store standing in for a real integration — see AGENT-1.3).
    """
    payload = _get_seeded_transaction(transaction_id)
    return payload.model_dump(mode="json")


@mcp.tool()
def screen_transaction(transaction: dict) -> dict:
    """Run the full compliance assessment agent against a transaction
    payload and return a structured, cited, risk-rated assessment.
    Required fields: amount, currency, counterparty, jurisdictions,
    instrument_type, customer_type, transaction_type.
    """
    parsed = TransactionPayload.model_validate(transaction)
    assessment = run_screening(parsed, request_id=new_request_id())
    return assessment.model_dump(mode="json")


@mcp.tool()
def screen_seeded_transaction(transaction_id: str) -> dict:
    """Convenience tool: look up one of the seeded demo transactions
    (TXN-1001..TXN-1005) and screen it in a single call.
    """
    payload = _get_seeded_transaction(transaction_id)
    assessment = run_screening(payload, request_id=new_request_id())
    return assessment.model_dump(mode="json")


def main() -> None:
    mcp.run(transport=settings.mcp_transport)


if __name__ == "__main__":
    main()
