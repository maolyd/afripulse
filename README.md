# AfriPulse
[![CI](https://github.com/maolyd/afripulse/actions/workflows/ci.yml/badge.svg)](https://github.com/maolyd/afripulse/actions/workflows/ci.yml)

**An African Digital Economy and Consumer Intelligence Data Platform.**

AfriPulse ingests public economic, demographic, connectivity and financial-inclusion
data for African countries, combines it with clearly labelled synthetic consumer
transaction data, and models it into an analytics-ready PostgreSQL data warehouse
using Python, dbt and Tableau.

> 🚧 Work in progress. Built phase by phase as a data engineering portfolio project.

## Tech Stack
Python 3.12 · PostgreSQL 16 · dbt Core · Apache Airflow (planned) · Tableau · Git/GitHub

## Project Status
- [x] Phase 1: Project foundation
- [x] Phase 2: Data discovery
- [x] Phase 3: Data ingestion
- [x] Phase 4: Data warehousing
- [x] Phase 5: dbt transformation
- [x] Phase 6: Pipeline automation
- [x] Phase 7: Data quality
- [x] Phase 8: Tableau dashboards
- [ ] Phase 9: Portfolio documentation

## Data Disclaimer
Public statistics come from sources such as the World Bank and IMF.
Transaction-level data (customers, merchants, payments, loyalty) is **synthetic**
and is never presented as real-world observations.

## Running the Pipeline

```bash
make db-setup      # create the database, schemas and tables (idempotent)
make ingest        # load every source; unchanged sources are skipped
make check         # lint + 123 automated tests
make coverage      # coverage report (minimum 80% enforced)
```

| Source | Type | Raw table | Incremental strategy |
|---|---|---|---|
| World Bank countries | REST API | `raw.worldbank_countries` | Row hash (unchanged rows skipped) |
| World Bank WDI (10 indicators) | REST API | `raw.worldbank_indicator_values` | Row hash |
| IMF World Economic Outlook | REST API | `raw.imf_weo_values` | New release detected from the API |
| UN World Population Prospects | CSV file | `raw.un_wpp_demographic_indicators` | File checksum (SHA-256) |
| Global Findex 2025 | Excel file | `raw.findex_values` | File checksum |
| **Synthetic** transactions | Generated | `raw_synthetic.*` | Fingerprint of settings + real calibration |

Every run is recorded in `audit.ingestion_runs`, and every pre-load validation
check in `audit.validation_results`. See [docs/synthetic_data.md](docs/synthetic_data.md)
for how the synthetic data is calibrated and labelled.


## Dashboards (Tableau Public)

Six dashboards, built in Tableau Public from the CSV extracts produced by `make export-tableau`.
Dashboards marked SYNTHETIC carry a visible banner: their data is generated, calibrated to real
statistics, and never describes real people or transactions.

| # | Dashboard | Data | Key finding |
|---|---|---|---|
| 1 | African Digital Economy Overview | REAL | 40.9% of Africans online in 2024 (51 of 54 countries reporting) |
| 2 | Country Comparison | REAL | IMF and World Bank GDP growth differ by >2 points in 99 country-years, mostly fragile states |
| 3 | Mobile & Internet Adoption | REAL | 96 mobile subscriptions per 100 people, but 41% online; fixed broadband about 3 per 100 |
| 4 | Mobile Money & Digital Payments | REAL + SYNTHETIC | Mobile-money-led (Kenya, Ghana) vs bank-led (South Africa, Egypt) inclusion |
| 5 | Retail & Consumer Transactions | SYNTHETIC | Month-end uplift 31%, validated against the generator's x1.3 setting |
| 6 | Customer Loyalty Analytics | SYNTHETIC | Points reconcile exactly; 26.7% breakage (5.8m points liability) |

**Live dashboards:** [Tableau Public workbook](https://public.tableau.com/app/profile/mawuli.dogbey/viz/AfriPulseAfricanDigitalEconomyOverview2024/Overview) · links, screenshots and findings
for each dashboard: [`tableau/dashboard_links.md`](tableau/dashboard_links.md)

![Overview dashboard](tableau/screenshots/01_overview.png)