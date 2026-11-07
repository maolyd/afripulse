# AfriPulse Data Quality Report

**Status: 🟠 AMBER**  
Generated: 2026-11-07 21:00 UTC  
Issues: 0 red, 1 amber

## Issues

| Severity | Area | Issue |
|---|---|---|
| 🟠 AMBER | coverage | mobile_subscriptions_per_100: only 39 of 54 countries in 2024 (Africa-wide averages may be biased, F15) |

## 1. Ingestion (latest run per source)

| Source | Status | Started (UTC) | Extracted | Loaded | Rejected | Seconds | Release |
|---|---|---|---:|---:|---:|---:|---|
| findex | skipped | 2026-11-07 14:18 | 0 | 0 | 0 | 0.083 | FINDEX2025 |
| imf_weo | skipped | 2026-11-07 14:18 | 0 | 0 | 0 | 0.779 | WEO-2026-10 |
| synthetic | skipped | 2026-11-07 14:18 | 0 | 0 | 0 | 0.135 | seed=20261107 v2 |
| un_wpp | skipped | 2026-11-07 14:18 | 0 | 0 | 0 | 0.192 | WPP2024 |
| worldbank_countries | success | 2026-11-07 14:18 | 296 | 0 | 0 | 0.328 |  |
| worldbank_wdi | success | 2026-11-07 14:18 | 14,040 | 0 | 0 | 4.916 | 2026-10-08 |

## 2. Pre-load validation

39 checks on each source's latest load, 0 failed.

## 3. dbt build and tests

Last `dbt build` at 2026-11-07T20:19: pass: 162, success: 32.

## 4. Source freshness

| Source | Status | Days since last load |
|---|---|---:|
| raw.findex_values | pass | 0.1 |
| raw.worldbank_countries | pass | 0.1 |
| raw.imf_weo_values | pass | 0.1 |
| raw.un_wpp_demographic_indicators | pass | 0.1 |
| raw.worldbank_indicator_values | pass | 0.1 |

## 5. Coverage (countries with data, latest year)

| Measure | Latest year | Countries (of 54) |
|---|---|---:|
| internet_users_pct | 2024 | 51 |
| mobile_subscriptions_per_100 | 2024 | 39 |
| mobile_money_account_pct | 2024 | 37 |

_Transaction-level data in AfriPulse is SYNTHETIC._
