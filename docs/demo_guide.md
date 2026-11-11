# AfriPulse demo guide

A 5-minute live walkthrough for interviews, plus answers to likely questions.

## Before the demo (10 minutes beforehand)

1. Start PostgreSQL (Postgres.app).
2. In the project folder, with the virtual environment active:

   ```bash
   make pipeline          # fresh ingestion, dbt build and quality report
   make airflow-start     # Airflow UI on http://localhost:8080 (leave it running)
   ```

3. Open these tabs in the browser:
   - the GitHub repository (README)
   - the Tableau Public workbook (live dashboards)
   - the Airflow UI, DAG `afripulse_pipeline`, Graph view
4. Have a terminal ready in the project folder with `psql -d afripulse` open.

## The 30-second pitch

> "AfriPulse is an end-to-end data platform on Africa's digital economy. It ingests public
> data from the World Bank, IMF, UN and Global Findex, validates it before loading, models it
> into a star schema with dbt, orchestrates it daily with Airflow, scores every run GREEN,
> AMBER or RED, and publishes six Tableau dashboards. Public data has no transaction-level
> detail, so I also built a synthetic data generator calibrated to the real statistics, and
> every synthetic output is clearly labelled."

## The 5-minute route

| Minute | Show | Say |
|---|---|---|
| 0:00 | README on GitHub | The pitch; point at the CI badge and the findings table |
| 0:45 | `docs/architecture/system_overview.md` | Walk the diagram left to right: sources, ingestion, warehouse, dbt, outputs, Airflow on top |
| 1:30 | Airflow Graph view | Five ingestion tasks in parallel, then synthetic, freshness, dbt build; the quality report runs even if something fails (`all_done`) |
| 2:15 | `psql`: the audit tables (queries below) | Every run, every validation check and every quality status is stored and queryable |
| 3:00 | `docs/architecture/dbt_lineage.png` | Raw sources to staging, intermediate, star-schema marts and reporting models |
| 3:30 | Tableau: Country Comparison | IMF and World Bank disagree on GDP growth in 99 country-years; knowing when a number is contested |
| 4:15 | Tableau: Customer Loyalty | The points reconciliation shows 0, the same rule checked in Python, dbt and Tableau, and the dbt version caught a real bug |
| 4:45 | Close | "Happy to go deeper into any layer." |

### Audit queries for the demo

```sql
-- Latest quality status per run
SELECT generated_at::date AS day, status, red_issues, amber_issues
FROM audit.dq_reports ORDER BY generated_at DESC LIMIT 5;

-- Recent ingestion runs
SELECT * FROM audit.ingestion_runs ORDER BY 1 DESC LIMIT 5;

-- Any failed validation checks
SELECT * FROM audit.validation_results WHERE NOT passed ORDER BY checked_at DESC LIMIT 10;
```

## Likely questions and short answers

**Why keep raw data as JSONB?**
If a source adds or renames a field, nothing is lost: the full payload is stored, and staging
models decide what to use. Re-transforming never requires re-downloading.

**How do you make loads idempotent?**
Each row has a natural key and a hash. The upsert inserts new keys and rewrites a row only when
its hash changes, so running the same load twice changes nothing. A test proves it.

**How do you know when a source has changed?**
Each source uses its own signal: row hashes (World Bank), the release name (IMF WEO), a SHA-256
checksum of the file (UN WPP, Findex), and a fingerprint of settings and calibration (synthetic).

**What happens when an API is down?**
The HTTP client retries brief failures (2, 4, 8, 16 seconds) but never retries a 403 or 404.
If the task still fails, Airflow retries it after 10 and then 20 minutes, and alerts only after
the last retry. The quality report then shows the failed run as RED.

**Why a star schema?**
Dashboards ask the same questions by country, date, indicator and source. Conformed dimensions
make those questions simple and consistent, and facts stay narrow and additive where possible.

**What is the SCD2 snapshot for?**
World Bank income groups change over time. The dbt snapshot keeps each country's history with
valid-from and valid-to dates, so a 2015 analysis can use the 2015 classification.

**Why is the synthetic data trustworthy enough to show?**
It is deterministic (fixed seed), calibrated to real population, income and Findex statistics,
guarded by invariant checks, and validated in the dashboards against its own settings: for
example the month-end uplift measures 31% against a configured x1.3. It is always labelled
SYNTHETIC, and its limitations are documented.

**What would you change for production?**
Run PostgreSQL and Airflow as managed services, keep secrets in a secrets manager, send alerts to
Slack or email instead of a local log, add integration tests with a PostgreSQL service in CI,
and publish dashboards from a scheduled extract instead of manual CSV uploads.

**What was the hardest bug?**
See [`challenges_and_solutions.md`](challenges_and_solutions.md).