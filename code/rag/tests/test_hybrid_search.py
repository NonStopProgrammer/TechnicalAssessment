from types import SimpleNamespace

from rag.retrieval.hybrid_search import _rrf_fuse


def _point(pid: str, score: float) -> SimpleNamespace:
    return SimpleNamespace(
        id=pid,
        score=score,
        payload={
            "chunk_id": f"chunk_{pid}",
            "doc_id": "doc_1",
            "clause_id": "1.1",
            "section_path": "1 > 1.1",
            "text": "sample clause text",
            "framework": "basel_iii",
            "jurisdiction": "GLOBAL",
            "doc_type": "regulation",
            "effective_date": "2023-01-01",
            "version": "2023-01-01",
            "superseded_by": None,
        },
    )


def test_rrf_fuse_rewards_points_ranked_highly_in_both_lists():
    dense = [_point("a", 0.9), _point("b", 0.8), _point("c", 0.7)]
    sparse = [_point("b", 5.0), _point("a", 4.0), _point("d", 3.0)]

    fused = _rrf_fuse(dense, sparse)

    assert set(fused) == {"a", "b", "c", "d"}
    # "a" and "b" each appear near the top of both rankings, "c"/"d" appear in only one.
    assert fused["a"].fusion_score > fused["c"].fusion_score
    assert fused["b"].fusion_score > fused["d"].fusion_score


def test_rrf_fuse_preserves_individual_dense_and_sparse_scores():
    dense = [_point("a", 0.42)]
    sparse = [_point("a", 7.5)]

    fused = _rrf_fuse(dense, sparse)

    assert fused["a"].dense_score == 0.42
    assert fused["a"].sparse_score == 7.5


def test_rrf_fuse_handles_dense_only_hit():
    dense = [_point("a", 0.5)]
    fused = _rrf_fuse(dense, [])

    assert fused["a"].sparse_score == 0.0
    assert fused["a"].fusion_score > 0
