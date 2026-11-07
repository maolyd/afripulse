# Discovery Findings: World Bank API

| Item | Detail |
|---|---|
| Source | World Bank World Development Indicators (WDI) API v2 |
| Base URL | `https://api.worldbank.org/v2` |
| Format | JSON (`?format=json`), paginated: `[metadata, records]` |
| Authentication | None required |
| Licence | CC BY 4.0 (attribution required) |
| Explored on | 2026-11-07 |
| Source last updated | 2026-10-08 |
| Script | `scripts/explore/explore_worldbank.py` |

## Summary

The API is reliable and complete for core demographic and economic indicators,
but its structure contains several traps that would cause **silent** errors
(wrong totals, missing countries, failed filters) if loaded naively.

## Findings and pipeline rules

| # | Finding | Evidence | Impact if ignored | Pipeline rule |
|---|---|---|---|---|
| F1 | `/country` mixes 217 economies with 79 aggregates (e.g. "Africa", "Sub-Saharan Africa") | 296 records returned | Totals double/triple-counted | Exclude aggregates (`region.value = 'Aggregates'`) |
| F2 | 6 African countries are outside the World Bank SSF region: DJI, DZA, EGY, LBY, MAR, TUN | Region = "Middle East, North Africa, Afghanistan & Pakistan" | Egypt, Algeria, Morocco silently missing from "Africa" | "Africa" is defined by our own reference list, never by WB region |
| F3 | Region names contain trailing whitespace | `"Sub-Saharan Africa "` | Equality filters return zero rows | `TRIM()` all text in staging |
| F4 | Two country code systems in one record | `country.id = "AO"`, `countryiso3code = "AGO"` | Join failures | ISO3 is the canonical country key |
| F5 | Official names differ from common names | `"Egypt, Arab Rep."` | Poor dashboard readability | `dim_country` holds official and display names |
| F6 | Years and coordinates are strings | `"date": "2025"`, `"longitude": "36.8126"` | Sorting/maths errors | Cast types in staging |
| F7 | Findex indicator (FX.OWN.TOTL.ZS) is 86.1% null | Data only in 2011, 2014, 2017, 2021, 2022, 2024 | False DQ failures, or misleading gap-filling | Per-indicator null thresholds; never impute silently |
| F8 | 6 countries never surveyed by Findex | CPV, ERI, GNB, GNQ, STP, SYC | Blank dashboard tiles misread as zero | Display "no survey data", never 0 |
| F9 | Publication lag: internet data ends 2024; GDP ends 2025 | Latest-year distribution | Mixed-year comparisons presented as same-year | Marts expose `latest_year`; dashboards show "as of" |
| F10 | Some countries lag years behind | See below | Stale values treated as current | Flag stale values in DQ checks |
| F11 | API returns one row per country-year, including nulls | 1404 = 54 × 26 | n/a | Expected-row-count check per indicator |
| F12 | `lastupdated` metadata available | `2026-10-08` | Unnecessary full reloads | Use for incremental loading (Phase 3) |
| F13 | Errors can return HTTP 200 with a `message` body | API behaviour | Errors treated as empty data | Explicitly check for `message` payloads |
| F14 | Income classifications change annually (July) | 24 LMC, 21 LIC, 8 UMC, 1 HIC | History rewritten on overwrite | dbt snapshot / SCD Type 2 (Phase 5) |

## Lagging countries (latest available year behind the newest)

| Indicator | Lagging countries |
|---|---|
| SP.POP.TOTL | None |
| NY.GDP.PCAP.CD | XXX (2015), YYY (2011) |
| IT.NET.USER.ZS | AAA (2020), BBB (2019), CCC (2017) |
| FX.OWN.TOTL.ZS | (survey-based; see F7, F8) |

## Indicator completeness (African countries, 2000–2025)

| Indicator | Rows | With value | Null % | Latest year (most countries) |
|---|---|---|---|---|
| SP.POP.TOTL | 1404 | 1404 | 0.0% | 2025 |
| NY.GDP.PCAP.CD | 1404 | 1372 | 2.3% | 2025 |
| IT.NET.USER.ZS | 1404 | 1297 | 7.6% | 2024 |AAA (2020), BBB (2019), CCC (2017) |
| FX.OWN.TOTL.ZS | 1404 | 195 | 86.1% | 2024 (survey waves) |

## Open questions

- Should raw storage keep null rows (faithful to source) or drop them? **Proposed:** keep them in `raw`, filter in `staging`.
- The African Union has 55 members; the World Bank covers 54 (no separate Western Sahara). Document this in `dim_country`.