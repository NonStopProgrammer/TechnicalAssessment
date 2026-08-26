"""One-shot local setup: creates tables, ingests the sample regulatory
corpus (RAG-1.6), and seeds the demo transactions (AGENT-1.3).

    python -m scripts.seed_corpus     # from the code/ directory

Idempotent (RAG-1.4) — safe to run repeatedly; `backend/main.py` also runs
this automatically on startup, so this script is mainly useful for
exercising `rag`/`agentic` directly without starting the API.
"""

from agentic.tools.get_transaction_details import seed_transactions
from rag.ingestion.pipeline import ingest_directory
from shared.config import get_settings
from shared.db.base import init_db


def main() -> None:
    init_db()
    settings = get_settings()
    corpus_dir = settings.code_root / "rag" / "corpus" / "sample_documents"

    print(f"Ingesting corpus from {corpus_dir} ...")
    outcomes = ingest_directory(corpus_dir)
    for outcome in outcomes:
        print(f"  {outcome.doc_id}: {outcome.status} ({outcome.chunks_indexed} chunks)")

    count = seed_transactions()
    print(f"Seeded {count} demo transaction(s).")


if __name__ == "__main__":
    main()
