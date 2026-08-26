"""RAG-1.5: fetch -> parse -> clean -> chunk -> embed -> upsert ->
impact-scan-trigger, as an auditable, retryable Airflow DAG.

Requires `apache-airflow` (see requirements-full.txt) to actually run;
not part of the MVP's runtime path (scripts/seed_corpus.py calls the same
underlying functions directly for local/CI use). Kept here, syntax-checked,
as the production orchestration target the architecture doc describes.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException

DOCUMENT_SOURCE_DIR = "/opt/airflow/data/incoming_regulations"

default_args = {
    "owner": "platform-team",
    "retries": 3,  # RAG-7.2: retry with backoff before paging
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
}


@dag(
    dag_id="regulatory_document_ingestion",
    schedule="@hourly",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["rag", "ingestion", "RAG-1.5"],
)
def regulatory_document_ingestion() -> None:
    @task
    def discover_new_files() -> list[str]:
        from pathlib import Path

        source = Path(DOCUMENT_SOURCE_DIR)
        if not source.exists():
            return []
        return [str(p) for p in sorted(source.iterdir()) if p.is_file()]

    @task
    def ingest_one(file_path: str) -> dict:
        from rag.ingestion.pipeline import ingest_file

        outcome = ingest_file(file_path)
        if outcome.status == "quarantined":
            # RAG-7.1: quarantine is logged, not fatal to the DAG run —
            # only escalate if the embedding/vector-store layer itself
            # failed (raised as an exception, caught below), not a bad file.
            return {"doc_id": outcome.doc_id, "status": outcome.status, "reason": outcome.reason}
        return {"doc_id": outcome.doc_id, "status": outcome.status, "chunks": outcome.chunks_indexed}

    @task
    def summarize(results: list[dict]) -> None:
        ingested = [r for r in results if r["status"] == "ingested"]
        quarantined = [r for r in results if r["status"] == "quarantined"]
        if not results:
            return
        # RAG-7.2: a systemic embedding/vector-store outage should look
        # different from "no new files" or "some files were bad" — paged,
        # not silently logged, if every attempted file failed.
        if quarantined and len(quarantined) == len(results):
            raise AirflowException(f"all {len(results)} files failed ingestion — check embedding/vector store health")

    file_paths = discover_new_files()
    results = ingest_one.expand(file_path=file_paths)
    summarize(results)


regulatory_document_ingestion()
