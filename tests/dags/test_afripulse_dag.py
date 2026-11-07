"""DAG integrity tests. Run with the AIRFLOW environment: `make airflow-test`.
(The folder is called tests/dags, not tests/airflow: a folder named "airflow"
would be mistaken for the airflow package itself.)

In the main project environment Airflow is not installed, so these tests are
skipped there (importorskip). Testing DAGs like this catches broken imports,
cycles and missing retries before the scheduler ever sees the file.
"""

from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

# Check for a real Airflow submodule: the project's own airflow/ folder would
# otherwise be imported as an (empty) "airflow" package and fool the check.
pytest.importorskip("airflow.sdk")

from airflow.models import DagBag  # noqa: E402

DAGS_FOLDER = Path(__file__).resolve().parents[2] / "airflow" / "dags"


@pytest.fixture(scope="module")
def dagbag():
    return DagBag(dag_folder=str(DAGS_FOLDER))


@pytest.fixture(scope="module")
def dag(dagbag):
    # Read the parsed DAG straight from the DagBag. (dagbag.get_dag() also queries
    # Airflow's metadata database, which these structure tests must not need.)
    return dagbag.dags["afripulse_pipeline"]


def test_dag_files_import_without_errors(dagbag):
    assert dagbag.import_errors == {}


def test_pipeline_has_every_step(dag):
    expected = {
        "ingest_worldbank_countries",
        "ingest_worldbank_wdi",
        "ingest_imf_weo",
        "ingest_un_wpp",
        "ingest_findex",
        "ingest_synthetic",
        "dbt_source_freshness",
        "dbt_build",
        "data_quality_report",
    }
    assert set(dag.task_ids) == expected


def test_synthetic_waits_for_every_real_source(dag):
    upstream = dag.get_task("ingest_synthetic").upstream_task_ids
    assert upstream == {
        t for t in dag.task_ids if t.startswith("ingest_") and t != "ingest_synthetic"
    }


def test_dbt_runs_last_after_freshness(dag):
    assert dag.get_task("dbt_build").upstream_task_ids == {"dbt_source_freshness"}
    assert dag.get_task("dbt_source_freshness").upstream_task_ids == {"ingest_synthetic"}


def test_ingestion_tasks_retry_with_backoff(dag):
    task = dag.get_task("ingest_imf_weo")
    assert task.retries == 2
    assert task.retry_delay == timedelta(minutes=10)
    assert task.retry_exponential_backoff


def test_one_run_at_a_time_and_no_backfill(dag):
    assert dag.max_active_runs == 1
    assert dag.catchup is False


def test_failure_callback_writes_an_alert(dag, tmp_path, monkeypatch):
    import afripulse_pipeline as module

    alert_log = tmp_path / "alerts.log"
    monkeypatch.setattr(module, "ALERT_LOG", alert_log)
    monkeypatch.setattr(module.shutil, "which", lambda _: None)  # no desktop popup in tests
    ti = Mock(dag_id="afripulse_pipeline", task_id="ingest_imf_weo", try_number=3)

    module.notify_failure({"task_instance": ti})

    assert (
        "AfriPulse task FAILED: afripulse_pipeline.ingest_imf_weo (try 3)" in alert_log.read_text()
    )


def test_quality_report_runs_last_even_after_failures(dag):
    task = dag.get_task("data_quality_report")
    others = set(dag.task_ids) - {"data_quality_report"}
    assert task.upstream_task_ids == others  # waits for every other task
    assert task.trigger_rule == "all_done"  # ...but runs whether they passed or failed
    assert task.retries == 0
