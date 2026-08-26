"""RAG-4.1 sparse signal: Qdrant native sparse vectors carry a BM25/SPLADE-
style keyword signal in production. This MVP computes a hashed, log-scaled
term-frequency sparse vector instead of running a SPLADE model — structurally
the same "sparse term-id -> weight" representation Qdrant expects, just
without a learned model or corpus-level IDF behind the weights. Swap in a
real SPLADE encoder here without touching the retrieval/fusion code.
"""

import math
import re
import zlib
from dataclasses import dataclass

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)*")
SPARSE_VOCAB_SIZE = 2**18


@dataclass
class SparseVector:
    indices: list[int]
    values: list[float]


def vectorize_sparse(text: str) -> SparseVector:
    tokens = _TOKEN_PATTERN.findall(text.lower())
    term_frequency: dict[int, float] = {}
    for token in tokens:
        idx = zlib.crc32(token.encode("utf-8")) % SPARSE_VOCAB_SIZE
        term_frequency[idx] = term_frequency.get(idx, 0.0) + 1.0

    indices = list(term_frequency.keys())
    values = [1.0 + math.log(count) for count in term_frequency.values()]
    return SparseVector(indices=indices, values=values)
