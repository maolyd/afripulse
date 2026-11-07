# ADR 0003: Orchestration with Apache Airflow

| Item | Detail |
|---|---|
| Status | Accepted |
| Date | 2026-11-07 |
| DAG | [`airflow/dags/afripulse_pipeline.py`](../../airflow/dags/afripulse_pipeline.py) |
| Tests | [`tests/dags/test_afripulse_dag.py`](../../tests/dags/test_afripulse_dag.py) |

## Context

By Phase 5 the whole pipeline ran with one command, `make pipeline`
(ingest → freshness → dbt build). That is **Python/Make orchestration**: simple
and reliable, but it needs a person to run it, offers no schedule, no retry of a
whole step after a long outage, and no history of runs to monitor.

Constraints: a 2015 MacBook Pro (16 GB RAM), macOS Monterey, no Docker.

## Decision

Use **Apache Airflow 3.3.2**, installed natively, to schedule and monitor the
existing pipeline. Airflow *orchestrates*; it does not contain business logic.

1. **Separate virtual environment** (`.venv-airflow`). Airflow and dbt pin
   conflicting library versions; mixing them breaks one or the other. Airflow is
   installed with its official **constraints file** for a tested, reproducible set.
2. **Tasks call the project's own commands** (`python -m afripulse.orchestration.cli
   ingest <source>`, `make dbt-build`) through the project's `.venv`, with
   `BashOperator`. The same commands work by hand, in Make and in Airflow, so a
   failing task can be reproduced in a terminal exactly.
3. **One task per source.** A failing source fails (and retries) on its own; the
   others are unaffected and visible separately in the UI.
4. **Dependencies:** the five real sources run in parallel (max 2 at a time, to
   be gentle on the laptop) → synthetic generation (calibrated from them) →
   source freshness → `dbt build`.
5. **Two layers of retries:** the HTTP client retries brief failures within
   seconds (2, 4, 8, 16 s); Airflow retries a failed task after 10 then 20 minutes
   for longer outages. Freshness checks are not retried: stale data does not
   fix itself.
6. **Alerting:** `on_failure_callback` fires only after the final retry, writing
   to `logs/alerts.log` and showing a macOS notification. In production this
   would be email or Slack.
7. **Schedule:** daily at 05:30, `catchup=False` (each run loads everything
   current, so back-filling missed days adds nothing), `max_active_runs=1`.
8. **Local setup:** `airflow standalone` (API server, scheduler, DAG processor,
   triggerer) with a SQLite metadata database inside `airflow/` (git-ignored).

## Alternatives considered

| Option | Rejected because |
|---|---|
| cron / launchd only | Schedules, but no retries per step, dependencies, run history or UI |
| Airflow in Docker | Docker not available on this machine |
| Prefect / Dagster | Capable and lighter, but Airflow is the most requested orchestrator in job descriptions |
| dbt and ingestion as Python operators inside Airflow | Requires installing dbt and project dependencies into Airflow's environment: dependency conflicts |
| PostgreSQL as Airflow's metadata DB | Production choice, but SQLite is enough for a single local scheduler |

## Consequences

- The pipeline runs unattended and every run, task, retry and log is visible in the UI.
- Local limits (accepted): SQLite metadata DB and a single machine; the laptop must
  be on at 05:30 (missed runs are not back-filled, by design).
- DAG integrity is tested (`make airflow-test`): imports, dependencies, retries,
  schedule settings and the failure alert.
