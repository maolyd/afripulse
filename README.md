# AfriPulse

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
- [ ] Phase 6: Pipeline automation
- [ ] Phase 7: Data quality
- [ ] Phase 8: Tableau dashboards
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