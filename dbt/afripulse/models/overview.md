{% docs __overview__ %}
# AfriPulse warehouse

African Digital Economy and Consumer Intelligence Data Platform.

**Layers**

| Schema | Built by | Contents |
|---|---|---|
| `raw`, `raw_synthetic` | Python ingestion (`make ingest`) | Source data as received, with lineage columns |
| `reference` | dbt seeds | Countries in scope (ADR 0001), indicator concepts, payment methods, sources |
| `staging` | dbt views | One model per source: renamed, typed, units standardised |
| `intermediate` | dbt views | All sources conformed into one indicator shape, with comparison flags |
| `snapshots` | dbt snapshot | Type 2 history of World Bank income groups |
| `marts` | dbt tables | Star schema for Tableau: 5 facts, 8 dimensions |

**Synthetic data:** every model whose name or description says SYNTHETIC holds
generated data calibrated to real statistics. It never describes real people,
merchants or transactions.

Use the **lineage graph** (bottom-right button) to follow any mart column back to
its raw source.
{% enddocs %}
