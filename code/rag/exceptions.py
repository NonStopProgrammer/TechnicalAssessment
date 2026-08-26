"""RAG-7: error handling. Distinct exception types so callers (ingestion DAG,
retrieval pipeline, API layer) can react differently instead of catching a
bare Exception and losing the failure mode.
"""


class RagError(Exception):
    """Base class for all rag/ exceptions."""


class UnparseableDocumentError(RagError):
    """RAG-7.1: malformed/unparseable document — quarantine, don't fail the DAG."""

    def __init__(self, source_uri: str, reason: str):
        self.source_uri = source_uri
        self.reason = reason
        super().__init__(f"Could not parse '{source_uri}': {reason}")


class EmbeddingServiceUnavailableError(RagError):
    """RAG-7.2: retried with backoff by the caller; raised after exhaustion."""


class VectorStoreUnavailableError(RagError):
    """RAG-7.3: query-time circuit breaker triggers graceful degradation."""


class DuplicateIngestionSkipped(RagError):
    """RAG-1.4: not a failure — raised as a control-flow signal, caught by the
    ingestion pipeline to short-circuit and log a no-op.
    """

    def __init__(self, doc_id: str, checksum: str):
        self.doc_id = doc_id
        self.checksum = checksum
        super().__init__(f"'{doc_id}' with checksum {checksum[:12]}... already ingested")
