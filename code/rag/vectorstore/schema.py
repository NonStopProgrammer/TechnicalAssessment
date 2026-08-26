"""RAG-3.3: one collection per region, partitioned logically by `framework`/
`jurisdiction` payload fields — a cross-framework query (FR-2.2) is a single
filtered query, not a fan-out across N collections.
"""

from qdrant_client import models

from rag.embeddings.base import EMBEDDING_DIMENSION

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "text-sparse"


def collection_name(jurisdiction: str) -> str:
    """SEC-1.1 region pinning: a distinct collection (deployable to a
    distinct regional Qdrant instance) per jurisdiction.
    """
    return f"regulations_{jurisdiction.lower()}"


def vectors_config() -> dict[str, models.VectorParams]:
    return {
        DENSE_VECTOR_NAME: models.VectorParams(size=EMBEDDING_DIMENSION, distance=models.Distance.COSINE)
    }


def sparse_vectors_config() -> dict[str, models.SparseVectorParams]:
    return {SPARSE_VECTOR_NAME: models.SparseVectorParams()}


def payload_index_fields() -> list[tuple[str, models.PayloadSchemaType]]:
    """RAG-4.5: filters applied *before* fusion need payload indexes to stay
    fast as the corpus grows past the initial 5-document prototype.
    """
    return [
        ("framework", models.PayloadSchemaType.KEYWORD),
        ("jurisdiction", models.PayloadSchemaType.KEYWORD),
        ("doc_type", models.PayloadSchemaType.KEYWORD),
        ("doc_id", models.PayloadSchemaType.KEYWORD),
        ("superseded_by", models.PayloadSchemaType.KEYWORD),
        ("effective_date", models.PayloadSchemaType.DATETIME),
    ]
