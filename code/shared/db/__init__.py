"""SQLAlchemy persistence layer: RAG-5.4 document registry, SEC-2.3/2.4 audit
log, seeded transactions (AGENT-1.3), and generated report records (FR-4).

Deliberately holds no raw regulatory document *text* and no un-redacted PII
(see SEC-2.3, LLM-4.3) — only metadata, registry rows, and audit entries.
That is what makes RDS/managed Postgres an acceptable trade-off here even
though the assignment's OSS constraint pushes everything else self-hosted
(see requirements/10-technology-stack.md, "Where a managed AWS service is
used despite being not OSS software").
"""
