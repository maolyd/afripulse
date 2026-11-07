# ADR 0002: Dimensional Model (Star Schema) for the Analytical Layer

| Item | Detail |
|---|---|
| Status | Accepted |
| Date | 2026-11-07 |
| Design | [warehouse_erd.md](../architecture/warehouse_erd.md) |
| Supersedes | Key types in data dictionary v1 (integer surrogate keys → hash keys) |

## Context

AfriPulse has two very different jobs:

1. **Store data faithfully** as it arrives (raw layer, Phase 3): one table per
   source, the original record as JSONB, lineage columns, no interpretation.
2. **Answer analytical questions quickly and simply** for Tableau users:
   "mobile money volume by country and month", "GDP growth: IMF vs World Bank",
   "unredeemed loyalty points by customer segment".

A **normalised** design (third normal form, 3NF) stores each fact once and
splits data into many narrow related tables. It is ideal for *transactional*
systems (OLTP) that insert and update single records and must avoid update
anomalies. But analytical queries on it need many joins, and business users
find it hard to navigate.

A **dimensional** design (Kimball star schema) deliberately denormalises:
central **fact** tables hold measurements at a declared **grain**, and wide
**dimension** tables hold the descriptive attributes users filter and group by.
It is optimised for *reading* (OLAP): few joins, predictable query shapes,
and a model that matches how people ask questions.

## Decision

The `marts` schema is a **star schema**. Normalisation remains where it helps:
the raw layer (one table per source) and the reference data.

### 1. Five facts with explicit grains

| Fact | Grain | Type |
|---|---|---|
| `fact_economic_indicators` | country × year × indicator × source | Periodic snapshot |
| `fact_digital_adoption` | country × year | Periodic snapshot (derived, wide) |
| `fact_retail_transactions` | one purchase | Transaction |
| `fact_mobile_money` | one wallet transaction | Transaction |
| `fact_loyalty_transactions` | one loyalty event | Transaction |

The grain is declared *before* columns are chosen, and every fact is tested for
uniqueness at its grain in dbt.

### 2. Long economic fact, plus a wide derived fact

Discovery showed sources disagree (F-IMF-9) and new indicators will be added.
`fact_economic_indicators` is therefore **long** (one row per value, with
`indicator_key` and `source_key`): sources stay side by side and a new indicator
needs no schema change. `fact_digital_adoption` is a **wide** view of the
default-source values for dashboards that compare measures side by side. It is
derived from the long fact, so the two can never disagree.

### 3. Conformed dimensions

`dim_country` and `dim_date` are shared by every fact they apply to. This is
what allows real statistics and synthetic transactions to appear on the same
dashboard, joined through the same country.

### 4. No snowflaking

Facts carry `country_key` directly. `dim_customer` and `dim_merchant` keep the
country code as a plain *attribute*, not a foreign key to `dim_country`.
Chaining dimensions ("snowflaking") would add joins and confuse BI tools,
for very little storage saved.

### 5. Hash surrogate keys

Surrogate keys are the `md5` hash of the natural key
(`dbt_utils.generate_surrogate_key`), not auto-incremented integers. dbt
rebuilds tables from scratch, and an auto-increment would give the same customer
a different key on each rebuild, breaking any saved Tableau extract or
incremental fact. Hash keys are **deterministic**: same input, same key, every time.
Trade-off: 32-character text keys use more space than integers, which is
irrelevant at this data volume. `dim_date` keeps a readable integer key (`YYYYMMDD`).

### 6. Unknown members instead of null foreign keys

Every dimension has a row with key `'-1'` ("Not applicable / unknown"). A mobile
money cash-out has no merchant, so its `merchant_key` is `'-1'`, not null.
Inner joins then never drop rows silently, and dashboards show the "Not
applicable" bucket explicitly.

### 7. Role-playing dimension

`fact_mobile_money` uses `dim_customer` twice: as the sender (`customer_key`)
and as the recipient of P2P transfers (`counterparty_customer_key`).

### 8. Degenerate dimensions

Transaction identifiers (`txn_id`, `mm_txn_id`, `event_id`) stay on the fact
with no dimension table: they have no attributes of their own, but they are
needed for drill-down and to link a mobile money payment to its retail purchase.

### 9. Slowly changing dimensions

| Dimension | Strategy | Reason |
|---|---|---|
| `dim_country` (income group) | Type 1 (current value) in the dimension, **Type 2 history kept by a dbt snapshot** of the World Bank country data | Income groups are reclassified every July (F14); history is needed to analyse a country "as classified at the time" |
| `dim_customer`, `dim_merchant` | Type 1 | Synthetic attributes do not change in v1 |
| `dim_indicator`, `dim_source`, `dim_payment_method` | Type 1 | Reference data maintained in Git |

**Limitation:** a snapshot only records changes from the day it starts running.
Historical classifications before that date would require the World Bank's
historical income classification file (out of scope for v1).

### 10. Annual facts use `year`, transaction facts use `date_key`

Economic data is annual: joining it to a daily date dimension would invent a
false precision (which day of 2023 is "2023"?). Annual facts carry `year`;
transaction facts carry `date_key`. Both line up on `dim_date.year`.

## Alternatives considered

| Option | Rejected because |
|---|---|
| Query the raw/3NF layer directly from Tableau | Many joins, JSON parsing in every query, unit conversions repeated in every dashboard |
| One big wide table per subject (OBT) | Simple, but duplicates country and customer attributes in every row and makes conformed analysis across subjects hard |
| Data vault | Strong for many changing sources and full history, but heavy for a single-developer project; adds a layer without business value here |
| Integer surrogate keys | Not stable across dbt full rebuilds (see decision 5) |

## Consequences

- Dashboards query a small set of predictable tables with simple joins.
- Every fact has a declared, tested grain: duplicates fail the build.
- Measures are classified by additivity (see ERD), preventing wrong sums such
  as adding up loyalty balances over time.
- Raw data stays untouched; the star schema can be rebuilt from it at any time.
