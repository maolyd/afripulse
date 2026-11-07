"""
# AfriPulse daily pipeline

Ingests every source into the warehouse, then builds and tests it with dbt.

```
ingest_worldbank_countries ┐
ingest_worldbank_wdi       │
ingest_imf_weo             ├─> ingest_synthetic ─> dbt_source_freshness ─> dbt_build
ingest_un_wpp              │   (calibrated from
ingest_findex              ┘    the real sources)                              │
                                                                               v
                                                (always runs) data_quality_report
```

**How it runs:** Airflow only *orchestrates*. Every task runs the project's own
commands (the ingestion CLI and the Makefile's dbt targets) with the project's
own virtual environment. Airflow and dbt need conflicting library versions, so
they live in separate environments (`.venv-airflow` and `.venv`).

**Two layers of retries:**
1. Inside a task, the HTTP client retries brief failures (2, 4, 8, 16 seconds).
2. If the whole task still fails, Airflow retries it later (10, then 20 minutes),
   which covers longer outages.

**Data quality report:** the last task runs even if earlier tasks failed
(trigger rule `all_done`), because that is exactly when a report is needed. It
fails (and alerts) when the overall data quality status is RED.

**Idempotent:** every step can be re-run safely. Unchanged sources are skipped,
and dbt builds incrementally.
"""

import logging
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

# airflow/dags/afripulse_pipeline.py -> parents[2] is the project folder.
PROJECT_DIR = Path(__file__).resolve().parents[2]
PYTHON = PROJECT_DIR / ".venv" / "bin" / "python"
ALERT_LOG = PROJECT_DIR / "logs" / "alerts.log"

REAL_SOURCES = ["worldbank_countries", "worldbank_wdi", "imf_weo", "un_wpp", "findex"]

logger = logging.getLogger(__name__)


def notify_failure(context) -> None:
    """Called by Airflow when a task fails for good (after all retries).

    Records the failure in logs/alerts.log and, on macOS, shows a desktop
    notification. In a company this would send an email or a Slack message.
    """
    ti = context["task_instance"]
    message = f"AfriPulse task FAILED: {ti.dag_id}.{ti.task_id} (try {ti.try_number})"
    logger.error(message)
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ALERT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")
    if shutil.which("osascript"):  # macOS only
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "AfriPulse"'],
            check=False,
        )


def ingest(source_id: str) -> str:
    return f"cd '{PROJECT_DIR}' && '{PYTHON}' -m afripulse.orchestration.cli ingest {source_id}"


def make(target: str) -> str:
    return f"cd '{PROJECT_DIR}' && make {target}"


default_args = {
    "owner": "afripulse",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,  # 10 minutes, then 20
    "max_retry_delay": timedelta(hours=1),
    "execution_timeout": timedelta(minutes=30),
    "on_failure_callback": notify_failure,
}

with DAG(
    dag_id="afripulse_pipeline",
    description="Ingest all AfriPulse sources, then build and test the dbt warehouse",
    doc_md=__doc__,
    schedule="30 5 * * *",  # every day at 05:30
    start_date=datetime(2026, 11, 1),
    catchup=False,  # do not back-fill missed days: each run loads everything current
    max_active_runs=1,  # never two pipeline runs at once
    max_active_tasks=2,  # gentle on a 2015 MacBook
    default_args=default_args,
    tags=["afripulse", "ingestion", "dbt"],
) as dag:
    ingest_real_sources = [
        BashOperator(task_id=f"ingest_{source_id}", bash_command=ingest(source_id))
        for source_id in REAL_SOURCES
    ]

    ingest_synthetic = BashOperator(
        task_id="ingest_synthetic",
        bash_command=ingest("synthetic"),
        doc_md="Runs after the real sources, because it is calibrated from them.",
    )

    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=make("dbt-freshness"),
        retries=0,  # stale data will not fix itself in 10 minutes
        doc_md="Fails if a raw source has not been ingested for 30 days.",
    )

    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=make("dbt-build"),
        execution_timeout=timedelta(minutes=45),
        doc_md="Builds staging, intermediate and marts, and runs every dbt test.",
    )

    data_quality_report = BashOperator(
        task_id="data_quality_report",
        bash_command=(
            f"cd '{PROJECT_DIR}' && '{PYTHON}' -m afripulse.orchestration.cli quality-report"
        ),
        trigger_rule="all_done",  # run after everything else, whatever happened
        retries=0,  # a RED status is a finding, not a temporary failure
        doc_md="Combines ingestion, validation, dbt tests, freshness and coverage. "
        "Fails when the status is RED.",
    )

    ingest_real_sources >> ingest_synthetic >> dbt_source_freshness >> dbt_build
    [*ingest_real_sources, ingest_synthetic, dbt_source_freshness, dbt_build] >> (
        data_quality_report
    )
