# Source-to-Target Mapping (v1)

How each source field becomes a warehouse column. Every rule references the
discovery finding that justifies it. Implemented in Phase 3 (raw), and in
Phase 5 by dbt staging (`stg_`), intermediate (`int_`) and mart models.

## Global rules (all sources)

| Rule | Detail | Finding |
|---|---|---|
| G1 | Keep only countries in `data/reference/african_countries.csv` (ISO3) | ADR 0001 |
| G2 | ISO3 is the country key; read code columns as text with null detection off | F4, F-UN-3 |
| G3 | `TRIM()` all text fields | F3 |
| G4 | Percentages stored as **0–100** (not 0–1) | F-FX-3 |
| G5 | Counts stored as **absolute numbers** (not thousands) | F-UN-1 |
| G6 | Every value carries `source_id`, `source_release` and `is_projection` | F-IMF-3, F-IMF-5, F-UN-10 |
| G7 | Raw keeps null values as received; staging removes rows with no value | F11 |
| G8 | Every raw row carries `_batch_id`, `_ingested_at`, `_source_file` or `_source_url`, `_record_hash` | Lineage |

## Indicator concepts

Each warehouse indicator is a *concept*; sources map to it.

| indicator_code | Name | Unit | WB | IMF | UN WPP | Findex | Default source |
|---|---|---|---|---|---|---|---|
| `population_total` | Total population (mid-year) | persons | `SP.POP.TOTL` | | `TPopulation1July` ×1000 | | UN WPP |
| `gdp_current_usd` | GDP, current prices | USD | `NY.GDP.MKTP.CD` | | | | WB |
| `gdp_per_capita_current_usd` | GDP per capita, current prices | USD | `NY.GDP.PCAP.CD` | | | | WB |
| `gdp_real_growth_pct` | Real GDP growth | % | `NY.GDP.MKTP.KD.ZG` | `NGDP_RPCH` | | | IMF |
| `inflation_cpi_pct` | Consumer price inflation | % | `FP.CPI.TOTL.ZG` | `PCPIPCH` | | | IMF |
| `urban_population_pct` | Urban population share | % | `SP.URB.TOTL.IN.ZS` | | | | WB |
| `internet_users_pct` | Individuals using the internet | % | `IT.NET.USER.ZS` | | | | WB |
| `mobile_subscriptions_per_100` | Mobile cellular subscriptions | per 100 people | `IT.CEL.SETS.P2` | | | | WB |
| `fixed_broadband_per_100` | Fixed broadband subscriptions | per 100 people | `IT.NET.BBND.P2` | | | | WB |
| `account_ownership_pct` | Account ownership, age 15+ | % | `FX.OWN.TOTL.ZS` | | | `account.t.d` ×100 | Findex |
| `fi_account_pct` | Financial institution account, age 15+ | % | | | | `fiaccount.t.d` ×100 | Findex |
| `mobile_money_account_pct` | Mobile money account, age 15+ | % | | | | `mobileaccount.t.d` ×100 | Findex |
| `borrowed_any_pct` | Borrowed any money, age 15+ | % | | | | `borrow.any.t.d` ×100 | Findex |
| `median_age_years` | Median age | years | | | `MedianAgePop` | | UN WPP |
| `life_expectancy_years` | Life expectancy at birth | years | | | `LEx` | | UN WPP |
| `fertility_rate` | Total fertility rate | births per woman | | | `TFR` | | UN WPP |
| `population_growth_pct` | Population growth rate | % | | | `PopGrowthRate` | | UN WPP |

## Source mappings

### worldbank_countries → `stg_worldbank__countries`

| Source field | Target column | Type | Transformation | Finding |
|---|---|---|---|---|
| `id` | `country_iso3` | text(3) | upper, trim | F4 |
| `iso2Code` | `country_iso2` | text(2) | trim; never null-converted | F-UN-3 |
| `name` | `country_name_wb` | text | trim | F5 |
| `region.id` | `wb_region_code` | text | trim | |
| `region.value` | `wb_region_name` | text | trim | F3 |
| `incomeLevel.id` | `income_group_code` | text | trim | F14 |
| `incomeLevel.value` | `income_group_name` | text | trim | F14 |
| `lendingType.value` | `lending_type` | text | trim | |
| `capitalCity` | `capital_city` | text | trim | |
| `latitude`, `longitude` | `latitude`, `longitude` | numeric | cast from text | F6 |
| filter | | | exclude `region.value = 'Aggregates'` | F1 |

### worldbank_wdi → `stg_worldbank__indicator_values`

| Source field | Target column | Type | Transformation | Finding |
|---|---|---|---|---|
| `countryiso3code` | `country_iso3` | text(3) | trim; filter to reference list | F4, G1 |
| `indicator.id` | `source_indicator_code` | text | map to `indicator_code` via concept table | |
| `date` | `year` | integer | cast from text | F6 |
| `value` | `value` | numeric | drop nulls | F11 |
| `obs_status` | `observation_status` | text | empty string → null | |
| `country.id`, `decimal`, `unit` | — | — | dropped (redundant) | F4 |
| metadata `lastupdated` | `source_last_updated` | date | from response metadata | F12 |
| constant | `source_id` | text | `'worldbank_wdi'` | G6 |
| constant | `is_projection` | boolean | `false` | |

### imf_weo → `stg_imf__weo_values`

| Source field | Target column | Type | Transformation | Finding |
|---|---|---|---|---|
| area key | `country_iso3` | text(3) | filter to reference list (drops `AFQ`, `ADVEC`...) | F-IMF-4 |
| indicator key | `source_indicator_code` | text | map to concept | |
| year key | `year` | integer | cast from text | |
| value | `value` | numeric | none (already %) | F-IMF-7 |
| config `release` | `source_release` | text | e.g. `WEO-2026-10` | F-IMF-3 |
| derived | `is_projection` | boolean | `year >= release year` (provisional) | F-IMF-5 |

### un_wpp → `stg_un_wpp__demographic_indicators`

| Source field | Target column | Type | Transformation | Finding |
|---|---|---|---|---|
| `ISO3_code` | `country_iso3` | text(3) | filter to reference list | F-UN-4 |
| `LocID` | `un_location_id` | integer | | F-UN-7 |
| `Time` | `year` | integer | exclude 2101 | F-UN-8 |
| `Variant` | `projection_variant` | text | | F-UN-10 |
| `TPopulation1July` | `population_total` | numeric | ×1000 | F-UN-1, F-UN-9 |
| `TPopulationMale1July` | `population_male` | numeric | ×1000 | F-UN-1 |
| `TPopulationFemale1July` | `population_female` | numeric | ×1000 | F-UN-1 |
| `PopDensity` | `population_density_per_km2` | numeric | | |
| `MedianAgePop` | `median_age_years` | numeric | | |
| `LEx` | `life_expectancy_years` | numeric | | |
| `TFR` | `fertility_rate` | numeric | | |
| `PopGrowthRate` | `population_growth_pct` | numeric | | |
| `NetMigrations` | `net_migration` | numeric | ×1000 | F-UN-1 |
| `Notes` | `un_note_code` | text | | F-UN-13 |
| derived | `is_projection` | boolean | `year >= 2024` | F-UN-10 |

### findex → `stg_findex__values` (unpivoted to long format)

| Source field | Target column | Type | Transformation | Finding |
|---|---|---|---|---|
| `codewb` | `country_iso3` | text(3) | filter to reference list | F-FX-5 |
| `year` | `year` | integer | | |
| `group` | `demographic_group` | text | `all`, `gender`, `income`... | F-FX-4 |
| `group2` | `demographic_subgroup` | text | `all`, `men`, `women`... | F-FX-4 |
| `pop_adult` | `adult_population` | numeric | | |
| each indicator column | `source_indicator_code` | text | unpivot configured columns | |
| indicator value | `value` | numeric | ×100 (fraction → %) | F-FX-3 |
| derived | `survey_wave` | text | 2021 and 2022 → `2021` | F-FX-8 |
| excluded | `.s` columns | — | not loaded in v1 (different denominator) | F-FX-9 |