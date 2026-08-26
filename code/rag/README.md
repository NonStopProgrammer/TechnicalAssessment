# RAG Pipeline

Implements `requirements/03-rag-pipeline-requirements.md` (RAG-1..RAG-7).

```
ingestion/    parse -> extract metadata -> register (RAG-1)
chunking/     clause-bounded chunking (RAG-2)
embeddings/   dense embedding provider abstraction (RAG-3.1)
vectorstore/  Qdrant collection schema + client (RAG-3.2/3.3, RAG-5)
retrieval/    hybrid search, re-rank, compression (RAG-4)
dags/         Apache Airflow DAGs (RAG-1.5, OBS-2.1) — syntax-checked only
corpus/       sample regulatory documents (RAG-1.6)
```

## Quickstart (from the `code/` directory, with `.venv` active)

```bash
python -m scripts.seed_corpus          # ingests rag/corpus/sample_documents/*
python -c "from rag.retrieval.pipeline import retrieve; \
r = retrieve('What are the Tier 1 capital requirements under Basel III?'); \
[print(c.chunk.citation_key, round(c.final_score, 3)) for c in r.chunks]"
```

## Provider matrix

| Component | MVP default (`.env`) | Production adapter | Requirement |
|---|---|---|---|
| Embeddings | `EMBEDDING_PROVIDER=local_hash` (hashed bag-of-words, no download) | `EMBEDDING_PROVIDER=tei` (BAAI/bge-large-en-v1.5 via HF TEI) | RAG-3.1 |
| Reranker | `RERANKER_PROVIDER=lexical` (token overlap) | `RERANKER_PROVIDER=cross_encoder` (BAAI/bge-reranker-large via TEI) | RAG-4.3 |
| Compression | `COMPRESSION_PROVIDER=passthrough` (truncation) | `COMPRESSION_PROVIDER=llmlingua` | RAG-4.4 |
| Vector store | Qdrant embedded (`QDRANT_URL` unset) | Qdrant server (docker-compose / EKS) | RAG-3.2 |

Every row is a config flag in `.env`, not a code change — see `rag/embeddings/base.py`,
`rag/retrieval/reranker.py`, `rag/retrieval/compression.py`.

## Known MVP limitations (see `requirements/11-non-goals-and-assumptions.md`)

- `local_hash` embeddings are a deterministic, dependency-free stand-in for a real semantic
  embedding model — good enough to demonstrate the pipeline's structure (chunking, hybrid
  fusion, re-ranking, filters, versioning) end-to-end, not a substitute for real MTEB-grade
  retrieval quality. Swapping to `tei` is a config change only.
- Point-in-time queries (`RAG-5.3`) filter on `effective_date`, which is correct for this
  corpus's single-amendment history but does not resolve the full version graph exactly for
  a document with 3+ historical versions — see `rag/vectorstore/qdrant_store.py::build_jurisdiction_filter`.
