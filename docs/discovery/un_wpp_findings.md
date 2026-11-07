# Discovery Findings: UN World Population Prospects 2024

| Item | Detail |
|---|---|
| Source | United Nations, Department of Economic and Social Affairs, Population Division: World Population Prospects 2024 |
| Download page | https://population.un.org/wpp/downloads |
| File | `WPP2024_Demographic_Indicators_Medium.csv` (published as `.csv.gz`; decompressed automatically by Safari) |
| Format | CSV, UTF-8, single header row, 67 columns, 84,360 rows |
| Size / SHA-256 | 40.82 MB / `9e552b141f9401bd88bd8dd3e433a37c1057cfc9f30a2ab657c4ead09869efb7` (of the decompressed file) |
| Variant | Medium (the UN's central projection scenario) |
| Time range | 1950–2101 (estimates to 2023, projections 2024–2100, per WPP 2024 documentation) |
| Licence | CC BY 3.0 IGO. To be confirmed in Task 2.5. |
| Collected on | 2026-11-07 (manual download) |
| Scripts | `scripts/explore/profile_file.py`, `scripts/explore/check_un_wpp.py` |

## Summary

A clean, complete file covering all 54 African countries for every year from
1950, with rich demographic detail. It is the **upstream source** of World Bank
population figures. Main risks: values in thousands, aggregates mixed with
countries, unlabelled projections, and a pandas default that silently erases
Namibia's ISO2 code.

## Findings and pipeline rules

| # | Finding | Evidence | Impact if ignored | Pipeline rule |
|---|---|---|---|---|
| F-UN-1 | Population and counts (births, deaths, migration) are in **thousands** | Angola 2025: 39,040.039 vs WB 39,040,039 | Values 1,000× too small | Multiply count columns by 1,000 in staging; document units per column |
| F-UN-2 | World Bank `SP.POP.TOTL` equals UN `TPopulation1July × 1000` exactly | Angola 2025 identical | Mistaking a copy for independent confirmation | Record UN WPP as upstream source of WB population; UN is primary for demographics |
| F-UN-3 | pandas reads Namibia's ISO2 code `"NA"` as a missing value | Default: `nan`; text read: `'NA'` | Namibia silently dropped from ISO2 joins | Read code columns with `dtype=str, keep_default_na=False`; key on ISO3 |
| F-UN-4 | 57% of rows are not countries (regions, income groups, ADB regions...) | 48,336 rows with no ISO3 | Double counting | Keep only countries in our reference list |
| F-UN-5 | 234 locations have no `LocTypeName` | Location types check | Type-based filters miss them | Do not rely on `LocTypeName`; use the reference list |
| F-UN-6 | Location names are not unique | 2 names map to 2 LocIDs each | Wrong merges on name joins | Join on codes only |
| F-UN-7 | `(LocID, Time)` is a unique natural key | 0 duplicate pairs | n/a | Primary key on `(loc_id, year)` in raw; dbt uniqueness test |
| F-UN-8 | Year 2101 holds only the 1 January population | All 555 null July values are in 2101 | Misleading nulls / partial year | Exclude 2101 from annual marts |
| F-UN-9 | Two population measures: 1 January and 1 July | Columns 13–14 | Inconsistent comparisons | Use `TPopulation1July` (mid-year, matches WB definition) |
| F-UN-10 | Projections are not labelled per row | `Variant = Medium` only | Forecasts presented as history | `is_projection = year >= 2024`; store `variant` on every row |
| F-UN-11 | pandas inferred IDs and codes as floats | `SortOrder`, `LocTypeID`, `ParentID` as `float64` (`1.0`) | Type errors, ugly keys | Declare explicit column types on ingestion |
| F-UN-12 | Structural nulls | `DoublingTime` 41% null (undefined when not growing) | False DQ failures | Per-column null thresholds |
| F-UN-13 | Footnotes are numeric codes; their text is not in the file | `Notes` = 1, 2, 3... | Coverage caveats lost | Map note codes to text from WPP documentation (reference table) |
| F-UN-14 | Geographically African non-sovereign territories are listed separately | MYT Mayotte, REU Réunion (France), SHN Saint Helena (UK) | Ambiguous "Africa" totals | Excluded from AfriPulse "Africa" (54 sovereign states); decision documented in Task 2.4 |
| F-UN-15 | Two African countries carry coverage footnotes | TZA (note 3), MUS (note 1) | Misread coverage | Confirm note texts in WPP documentation |
| F-UN-16 | Downloaded file was decompressed by the browser | `.csv` instead of `.csv.gz` | Checksum differs from published file | Pipeline downloads files itself and stores originals untouched |

## Coverage

| Check | Result |
|---|---|
| African countries present | 54 of 54 |
| African rows | 8,208 (= 54 countries × 152 years) |
| Fully duplicated rows | 0 |

## Open questions

- Does WPP include Western Sahara (ESH), the African Union's 55th member? Check in Task 2.4.
- Confirm the exact estimate/projection boundary year in the WPP 2024 methodology.
- Confirm units for every column (counts in thousands; rates per 1,000; density per km²).