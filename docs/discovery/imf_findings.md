# Discovery Findings: IMF DataMapper API

| Item | Detail |
|---|---|
| Source | IMF World Economic Outlook (WEO) via DataMapper API v1 |
| Base URL | `https://www.imf.org/external/datamapper/api/v1` |
| Format | JSON, nested: `values → indicator → area → year → value`; no pagination |
| Authentication | None, but protected by the Akamai CDN (see F-IMF-1) |
| Release explored | World Economic Outlook (October 2026) |
| Licence | IMF Copyright and Usage terms. To be confirmed in Task 2.5. |
| Explored on | 2026-11-07 |
| Script | `scripts/explore/explore_imf.py` |

## Summary

The IMF API covers all 54 African countries from 1980, including projections to
2031. It largely agrees with the World Bank (82% of country-years within 0.5 pp),
but it does not distinguish projections from actuals, and access depends on a
CDN bot filter.

## Findings and pipeline rules

| # | Finding | Evidence | Impact if ignored | Pipeline rule |
|---|---|---|---|---|
| F-IMF-1 | Akamai CDN returns HTTP 403 for unrecognised User-Agents (incl. `AfriPulse/0.1`) but allows standard tool identifiers (`python-requests/x.y`, `curl/x.y`) | Systematic curl tests, 2026-11-07 | Ingestion fails | Use the HTTP client's default User-Agent; treat 403 as non-retryable; log the Akamai reference number |
| F-IMF-2 | Access depends on a filter the IMF can change without notice | F-IMF-1 | Pipeline breaks unexpectedly | Monitor failures; keep the official bulk WEO file as fallback |
| F-IMF-3 | Every value belongs to a WEO release (vintage); past values are revised between releases | `source: World Economic Outlook (October 2026)` | Unexplained changes in dashboards | Store `source_release` (e.g. `WEO-2026-10`) on every row |
| F-IMF-4 | 32 of 229 areas are aggregates with IMF-specific codes | `ADVEC`, `AFQ`, `APQ`, ... | Double counting | Keep only countries in our reference list |
| F-IMF-5 | Projections (2026–2031) are indistinguishable from actuals | Kenya: `2029: 5, 2030: 5, 2031: 5` | Forecasts presented as history | Derive `is_projection`; preferably from the bulk WEO "Estimates Start After" field |
| F-IMF-6 | Coverage: all 54 countries, 1980–2031 | Output | n/a | Longer history than WB request window |
| F-IMF-7 | IMF values are rounded to 1 decimal place | `4.7` vs WB `3129.4766...` | Spurious small differences | Compare sources with a tolerance, not equality |
| F-IMF-8 | IMF and WB GDP growth agree within 0.5 pp for 82.1% of 521 country-years; mean gap 0.38 pp | Comparison section | n/a | Sources are broadly consistent |
| F-IMF-9 | Largest disagreements are in fragile states (SSD, SOM, SDN), plus ZWE and UGA | Top 10 disagreements, gaps up to 10.6 pp | Contested numbers shown as fact | Flag country-years where sources differ by > 2 pp as "low agreement" |

## Top disagreements (IMF vs World Bank real GDP growth, pp)

| Country | Year | IMF | WB | Gap | Likely cause (to verify) |
|---|---|---|---|---|---|
| SSD | 2015 | -0.20 | -10.79 | 10.59 | Conflict; estimation-based statistics |
| SOM | 2016 | -1.30 | 7.03 | 8.33 | Limited official statistics |
| SDN | 2023 | -23.50 | -29.43 | 5.93 | War; highly uncertain estimates |
| SOM | 2015 | 4.60 | 10.46 | 5.86 | Limited official statistics |
| SDN | 2024 | -19.30 | -13.96 | 5.34 | War; highly uncertain estimates |
| SOM | 2017 | 9.50 | 14.74 | 5.24 | Limited official statistics |
| ZWE | 2017 | 9.80 | 4.73 | 5.07 | Currency changes / rebasing |
| UGA | 2016 | 0.20 | 4.78 | 4.58 | Possibly fiscal vs calendar year basis |
| UGA | 2020 | -1.20 | 2.95 | 4.15 | Possibly fiscal vs calendar year basis |
| BDI | 2016 | -0.60 | 3.20 | 3.80 | Political crisis period |

## Design decisions supported by this discovery

1. **Keep both sources** in `fact_economic_indicators`, grain:
   country × year × indicator × source. Never average sources.
2. **Default source per indicator** (to confirm in Task 2.5): IMF for GDP growth
   and inflation; World Bank for population, internet and account ownership.
3. **Every IMF row carries** `source_release` and `is_projection`.

## Open questions

- Projection flag: rule of thumb (year >= release year) or official bulk WEO
  file ("Estimates Start After")? Decide in Task 2.5.
- Confirm Uganda's year basis in the WEO country notes.
- Confirm IMF licence and attribution requirements.