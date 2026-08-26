"""ID, checksum, and citation-key helpers used across ingestion, retrieval,
and audit logging so the format is defined exactly once (RAG-1.4, RAG-6.1).
"""

import hashlib
import uuid
from datetime import date, datetime, timezone


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex}"


def new_doc_id(source_name: str) -> str:
    slug = "".join(c.lower() if c.isalnum() else "-" for c in source_name).strip("-")
    return f"doc_{slug[:60]}"


def checksum_of(content: bytes) -> str:
    """RAG-1.4: idempotent ingestion — re-ingesting identical bytes is a no-op."""
    return hashlib.sha256(content).hexdigest()


def citation_key(doc_id: str, clause_id: str, version: str) -> str:
    """RAG-6.1 stable citation key: `{doc_id}#{clause_id}@{version}`."""
    return f"{doc_id}#{clause_id}@{version}"


def parse_citation_key(key: str) -> tuple[str, str, str]:
    doc_part, _, version = key.rpartition("@")
    doc_id, _, clause_id = doc_part.partition("#")
    return doc_id, clause_id, version


def format_citation_display(doc_id: str, clause_id: str, version: str | date | datetime) -> str:
    """FR-1.3 human-readable rendering: `[DocID §Clause, v:YYYY-MM-DD]`."""
    if isinstance(version, (date, datetime)):
        version = version.strftime("%Y-%m-%d")
    return f"[{doc_id} §{clause_id}, v:{version}]"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
