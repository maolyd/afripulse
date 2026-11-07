# Data Reliability

How AfriPulse keeps its data trustworthy: what is checked, where, what happens
when something goes wrong, and what to do about it.

## Quality checks at every stage

| Stage | Checks | Where results go | On failure |
|---|---|---|---|
| Extraction | HTTP retries (2/4/8/16 s), never retry 403/404; World Bank errors returned with HTTP 200 detected | `logs/afripulse.log` | Run fails, audited |
| Pre-load validation | Duplicate keys, minimum rows, country codes in reference list, year range, null rates per indicator, row-count drop vs last run, country coverage | `audit.validation_results` | **Error** blocks the load; **warning** recorded |
| Load | Primary keys, idempotent upsert, one transaction | `audit.ingestion_runs` | Nothing written |
| Synthetic generation | Invariant rules (unique keys, foreign keys, account ownership, time order, loyalty balances) | Python exception | Nothing loaded |
| Transformation | 194 dbt tests: unique/not-null keys, relationships, accepted values, ranges, grain, reconciliation | `dbt/afripulse/target/run_results.json` | `dbt build` fails |
| Freshness | Each raw source loaded within 7 days (warn) / 30 days (error) | `target/sources.json` | Pipeline stops before dbt build |
| Reporting | Everything above, plus coverage and synthetic labelling | `audit.dq_reports`, `reports/data_quality/latest.md` | Status RED, Airflow task fails, alert |

## Status levels

| Status | Meaning | Examples |
|---|---|---|
| 🟢 GREEN | All checks passed | Normal day |
| 🟠 AMBER | Data usable, worth a look | A validation warning, a source getting stale, low country coverage, a run that failed then recovered |
| 🔴 RED | Act now | A source's latest run failed, a dbt test failed, a source is stale, unlabelled synthetic rows |

## Failure scenarios and the tests that prove they are handled

| # | Scenario | Expected behaviour | Automated proof |
|---|---|---|---|
| 1 | API temporarily down (503, timeout) | Retried with backoff, then succeeds | `tests/unit/test_http_client.py::test_temporary_errors_are_retried_with_exponential_backoff` |
| 2 | API refuses access (403, CDN block) | Not retried; clear error with the CDN reference number | `test_http_client.py::test_permanent_errors_are_never_retried`, `test_permanent_error_keeps_body_excerpt_for_debugging` |
| 3 | API down for hours | Task retried by Airflow after 10 then 20 minutes; alert only after the last retry | `tests/dags/test_afripulse_dag.py::test_ingestion_tasks_retry_with_backoff`, `test_failure_callback_writes_an_alert` |
| 4 | Source returns far too few rows or an aggregate code | Load blocked, nothing written, checks stored | `tests/integration/test_validation_job.py::test_bad_batch_is_blocked_and_results_are_recorded` |
| 5 | Duplicate keys in a batch | Load rejected, nothing written | `tests/integration/test_loader.py::test_duplicate_keys_in_one_batch_are_rejected_and_nothing_is_written` |
| 6 | Same data loaded twice | No duplicates; nothing rewritten | `test_loader.py::test_second_identical_load_changes_nothing`, `test_worldbank_job.py::test_running_the_job_twice_is_idempotent_and_audited` |
| 7 | Manually downloaded file missing | Clear error naming the download page | `tests/unit/test_file_extractor.py::test_missing_file_gives_a_clear_message` |
| 8 | File columns renamed by the publisher | Load fails loudly | `test_file_extractor.py::test_missing_expected_columns_fail_loudly` |
| 9 | Synthetic generator bug | Invariant violation blocks the load | `tests/unit/test_synthetic_generators.py::test_invariants_catch_a_planted_error`, `test_invariants_catch_loyalty_balances_out_of_time_order` |
| 10 | Impossible values reach staging (e.g. 900%) | dbt `between` test fails the build | Demonstrated in Task 5.2 (`* 1000` experiment) |
| 11 | Loyalty points lost or invented | dbt reconciliation test fails | `assert_loyalty_balances_reconcile` (caught a real bug in Task 5.4) |
| 12 | Stale rows after synthetic regeneration | Incremental pre-hook removes them; count test proves it | `assert_synthetic_facts_match_staging` |
| 13 | A source stops being loaded | dbt freshness error, report RED | `tests/unit/test_quality_report.py::test_stale_source_is_red_and_warning_is_amber` |
| 14 | A dbt test fails | Report RED, named test, Airflow alert | `test_quality_report.py::test_failed_dbt_test_is_red_and_named` |

## Runbook: what to do when the report is RED

1. Open `reports/data_quality/latest.md` (or Airflow → `data_quality_report` → Logs).
2. Find the red issue's **area**:
   - **ingestion**: read the error. A network error? Re-run that source:
     `python -m afripulse.orchestration.cli ingest <source>`. A 403? See finding
     F-IMF-1; the provider may have changed its access rules.
   - **validation**: query the failed checks:
     `SELECT * FROM audit.validation_results WHERE NOT passed ORDER BY checked_at DESC;`
     Decide whether the source really changed (update the rule in `config/sources.yml`
     with a comment explaining why) or the data is wrong (do not load it).
   - **dbt**: run `make dbt-build`, then for the failing test:
     `dbt test --select <test_name> --store-failures` to see the offending rows.
   - **freshness**: the source has not loaded for 30 days. Check its Airflow task
     history; for manual files, download the new edition.
3. Fix the cause, re-run `make pipeline`, and confirm the report returns to GREEN or AMBER.
4. Never "fix" a test by loosening it without recording the evidence in a comment.

## Tracking quality over time

```sql
SELECT generated_at::date AS day, status, red_issues, amber_issues
FROM audit.dq_reports
ORDER BY generated_at DESC
LIMIT 30;
```

## Known limitations

- History of income classifications starts with the first snapshot (no back-fill).
- Coverage thresholds (45 countries; 35 for Findex mobile money) are judgement calls
  based on discovery findings F15 and F-FX-6.
- Alerts are local (log file and macOS notification); production would use email or Slack.
