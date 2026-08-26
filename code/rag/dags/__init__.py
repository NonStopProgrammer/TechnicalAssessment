"""Apache Airflow DAGs (RAG-1.5, OBS-2.1).

Not exercised by the MVP test suite — apache-airflow's dependency tree is
intentionally excluded from requirements.txt (see requirements-full.txt).
These DAGs are validated for syntax only (`python -m py_compile`) and are
written against the Airflow 2.x TaskFlow API so they are drop-in-deployable
onto a real Airflow instance; every task is a thin wrapper around a
function in `rag.ingestion.pipeline` / `eval.run_evaluation` that is
independently tested without Airflow.
"""
