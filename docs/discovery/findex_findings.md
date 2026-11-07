# Discovery Findings: Global Findex Database 2025

| Item | Detail |
|---|---|
| Source | World Bank, Global Findex Database 2025 (survey data to 2024) |
| Download page | https://www.worldbank.org/en/publication/globalfindex |
| File | `GlobalFindexDatabase2025.xlsx` (downloaded as `Global Findex Database 2025.xlsx`; renamed to remove spaces) |
| Size / SHA-256 | 17.94 MB / `b6c991f8e46bcbd4b6423cc962d5b2fa030e3db99832b9016bb4f400f57c772f` |
| Sheets | `Notes`, `Data`, `Series Table`, `Updates` |
| Data shape | 8,577 rows × 466 columns |
| Waves | 2011, 2014, 2017, 2021, 2022, 2024 |
| Licence | CC BY 4.0. To be confirmed in Task 2.5. |
| Collected on | 2026-11-07 (manual download) |

## Findings and pipeline rules

| # | Finding | Evidence | Pipeline rule |
|---|---|---|---|
| F-FX-1 | Data is on the 2nd sheet; the 1st sheet is notes | Default read returned 1 row, 1 column | Always specify `sheet_name="Data"` |
| F-FX-2 | Two header rows: codes (row 0) and labels (row 1) | Raw top | Header = row 0, skip row 1; load labels into an indicator reference table |
| F-FX-3 | Values are fractions (0–1), not percentages | `account.t.d` ranges 0.004–1.0; WB API gives 29.3 | Standardise units in staging; record unit per indicator |
| F-FX-4 | Natural key is (codewb, year, group, group2) | 0 duplicates on this key | Primary key on all four columns; filter `group = 'all'` for headline figures |
| F-FX-5 | 684 aggregate rows (world, regions, income groups) | Rows with no region | Keep only countries in our reference list |
| F-FX-6 | 48 of 54 African countries covered; missing CPV, ERI, GNB, GNQ, STP, SYC | Coverage check (matches WB API) | Show "no survey data", never 0 |
| F-FX-7 | Financial-use questions asked only in low/middle-income economies | Notes sheet; Seychelles (HIC) absent | Document coverage by income group |
| F-FX-8 | 2022 is a partial wave (16 economies, 11 African) | Rows per year | Treat 2021/2022 as one survey wave |
| F-FX-9 | 175 `.s` columns are sub-sample measures (different denominator) | Series Table definitions | Never compare `.s` measures with all-adult measures |
| F-FX-10 | Publisher supplies indicator definitions (458 series) | `Series Table` sheet | Use as source for indicator descriptions in the data dictionary |
| F-FX-11 | Namibia's code is read correctly here (ISO3 `NAM`) | Coverage check | Still read code columns with `keep_default_na=False` |

## Mobile money account ownership, 2024 (top African economies)

| Country | Mobile money account | Any account |
|---|---|---|
| Kenya | 87.5% | 90.1% |
| Ghana | 78.3% | 81.2% |
| Zambia | 69.3% | 72.7% |
| Uganda | 67.7% | 72.8% |
| Senegal | 66.9% | 76.5% |
| Gabon | 61.6% | 68.2% |