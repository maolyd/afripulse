# AfriPulse system overview

How data flows from public sources to the published dashboards. Every arrow is a
step that is automated, logged, and checked.

```mermaid
flowchart LR
    subgraph SRC["Sources"]
        WB["World Bank API<br/>countries + WDI"]
        IMF["IMF WEO<br/>release files"]
        UN["UN WPP<br/>manual file"]
        FX["Global Findex<br/>manual file"]
    end

    subgraph ING["Python ingestion"]
        EXT["Extractors<br/>retries 2/4/8/16 s"]
        VAL["Pre-load validation<br/>errors block the load"]
        LOAD["Idempotent upsert<br/>hash-based change detection"]
        GEN["Synthetic generator v2<br/>calibrated to real data"]
    end

    subgraph PG["PostgreSQL warehouse"]
        RAW[("raw<br/>JSONB + lineage")]
        RAWS[("raw_synthetic")]
        AUD[("audit<br/>runs, checks, DQ reports")]
    end

    subgraph DBT["dbt"]
        STG["staging<br/>clean + typed"]
        INT["intermediate<br/>sources compared"]
        MART["marts<br/>star schema, SCD2 snapshot"]
        RPT["reporting<br/>flat extracts"]
    end

    subgraph OUT["Outputs"]
        DQ["Data quality report<br/>GREEN / AMBER / RED"]
        CSV["CSV extracts"]
        TAB["Tableau Public<br/>6 dashboards"]
    end

    WB --> EXT
    IMF --> EXT
    UN --> EXT
    FX --> EXT
    EXT --> VAL --> LOAD --> RAW
    RAW -->|calibration| GEN --> RAWS
    RAW --> STG
    RAWS --> STG
    STG --> INT --> MART --> RPT --> CSV --> TAB
    VAL -. results .-> AUD
    LOAD -. run log .-> AUD
    AUD --> DQ
    MART -. dbt tests .-> DQ

    AF{{"Airflow 3<br/>daily 05:30, retries, alerts"}}
    AF -. orchestrates .-> ING
    AF -. orchestrates .-> DBT
    AF -. orchestrates .-> DQ
```

| Layer | Technology | Key design decision |
|---|---|---|
| Ingestion | Python, requests, tenacity, pandas | Raw payloads kept as JSONB, so a source change never loses data |
| Validation | Custom checks, `audit.validation_results` | Errors block a load before anything is written |
| Storage | PostgreSQL 16, least-privilege roles | Separate `raw`, `raw_synthetic` and `audit` schemas |
| Transformation | dbt Core 1.11 | Kimball star schema; incremental facts; SCD2 snapshot of income groups |
| Orchestration | Airflow 3 (separate virtual environment) | Airflow only orchestrates: tasks call the project's own CLI and Makefile |
| Quality | dbt tests, freshness, coverage | One GREEN / AMBER / RED status stored in `audit.dq_reports` |
| Reporting | CSV extracts, Tableau Public | Synthetic files and dashboards always carry a SYNTHETIC label |
| CI | GitHub Actions | Lint and unit tests on every push |

See also: [warehouse ERD](warehouse_erd.md) · [source catalogue](../source_catalogue.md) ·
[data reliability](../data_reliability.md)