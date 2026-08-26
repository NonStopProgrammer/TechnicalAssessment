"""OBS-2.1: nightly RAGAS regression run against the fixed ground-truth set,
plus OBS-2.3's release gate (a metric dropping below its EVAL-2 floor fails
the run rather than just reporting it). See eval/run_evaluation.py, which
this DAG wraps the same way ingestion_dag.py wraps rag/ingestion/pipeline.py.
"""

from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException


@dag(
    dag_id="nightly_evaluation_regression",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["eval", "observability", "OBS-2.1"],
)
def nightly_evaluation_regression() -> None:
    @task
    def run_eval() -> dict:
        from eval.run_evaluation import run_full_evaluation

        report = run_full_evaluation()
        return report.to_summary_dict()

    @task
    def gate_on_floors(summary: dict) -> None:
        failing = summary.get("failing_metrics", [])
        if failing:
            # OBS-2.3: evaluation is a release gate, not a report generated
            # after the fact — this DAG failing blocks promotion.
            raise AirflowException(f"evaluation floors breached: {failing}")

    gate_on_floors(run_eval())


nightly_evaluation_regression()
