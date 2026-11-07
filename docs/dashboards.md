# AfriPulse Dashboards (Tableau Public)

Six dashboards built in Tableau Public (web authoring) from the CSV extracts
produced by `make export-tableau` (see `exports/tableau/MANIFEST.md`).
Each dashboard answers business questions, not just displays data.

## Global design rules

| Rule | Why |
|---|---|
| Every dashboard built on SYNTHETIC files carries a visible banner: **"Synthetic data, calibrated to real statistics. Not real transactions."** | Project rule: never present synthetic data as real |
| Africa-wide percentages are **population-weighted** and show **coverage** ("51 of 54 countries") | Simple averages overweight small countries; missing countries bias results (F15) |
| Values show their **year** ("as of 2022") when countries' latest years differ | Publication lags differ by country (F9) |
| Projections are drawn **dashed** or in a lighter colour | Forecasts are not history (F-IMF-5) |
| Survey measures (Findex) show survey years only, never interpolated | F7 |
| Missing data shows as "No data", never 0 | F8 |

## Shared calculated fields (Tableau)

Create these once per data source that needs them.

| Name | Formula | Notes |
|---|---|---|
| `Pop-weighted internet %` | `SUM([Internet Users Pct] * [Population Total]) / SUM(IF NOT ISNULL([Internet Users Pct]) THEN [Population Total] END)` | Weights only countries that have a value |
| `Pop-weighted mobile money %` | `SUM([Mobile Money Account Pct] * [Population Total]) / SUM(IF NOT ISNULL([Mobile Money Account Pct]) THEN [Population Total] END)` | Survey years only |
| `Coverage (countries)` | `COUNTD(IF NOT ISNULL([Internet Users Pct]) THEN [Country Iso3] END)` | Duplicate per measure as needed |
| `Coverage label` | `STR([Coverage (countries)]) + " of 54 countries"` | Show under every Africa-wide KPI |
| `Is latest year` | `[Year] = { FIXED : MAX(IF NOT ISNULL([Internet Users Pct]) THEN [Year] END) }` | Level-of-detail (LOD) expression |

---

## 1. African Digital Economy Overview

**Questions:** How large and how connected is Africa's economy, and where is it growing?
**Data:** `real_country_year.csv` (REAL)

| KPI (latest year) | Formula |
|---|---|
| Population | `SUM([Population Total])` |
| GDP (US$ bn) | `SUM([Gdp Billions Usd])` |
| Internet use | `Pop-weighted internet %` + coverage label |
| Mobile money accounts | `Pop-weighted mobile money %` + coverage label |

**Views:** filled map of internet use by country (`Country Name`, geographic role *Country/Region*); line of pop-weighted internet % by year (2000–latest); bar of GDP by `Au Region`.
**Filters:** Year, AU region, income group.
**Decision supported:** which regions combine large populations with low connectivity (growth opportunity).

## 2. Country Comparison

**Questions:** How do selected countries compare, and do the IMF and World Bank agree?
**Data:** `real_country_year.csv` + `real_indicator_sources.csv` (REAL)

**Views:**
- Scatter: GDP per capita (x, log scale) vs internet use (y), size = population, colour = AU region.
- Side-by-side bars for 2–5 chosen countries (parameter or filter) across key indicators.
- Line: real GDP growth by source (`Source Provider` on colour), `Value Type` = Projection dashed; mark points where `Sources Disagree` = true.

**Decision supported:** benchmarking a market against peers; knowing when a number is contested.

## 3. Mobile and Internet Adoption

**Questions:** How fast is Africa getting online, and where is the gap between mobile access and internet use?
**Data:** `real_country_year.csv` (REAL)

| Measure | Formula |
|---|---|
| Mobile–internet gap (points) | `AVG([Mobile Subscriptions Per 100]) - AVG([Internet Users Pct])` |
| Internet growth since 2015 (points) | `{ FIXED [Country Iso3] : MAX(IF [Year] = [Latest internet year] THEN [Internet Users Pct] END) } - { FIXED [Country Iso3] : MAX(IF [Year] = 2015 THEN [Internet Users Pct] END) }` |

**Views:** trends of internet %, mobile subscriptions and fixed broadband; country ranking table with an "as of" year column (`Latest Internet Year`); highlight table of the gap.
**Decision supported:** where mobile-first digital services can reach users who are not yet online.

## 4. Mobile Money and Digital Payments

**Questions:** Who uses mobile money (real surveys), and what does wallet activity look like (synthetic)?
**Data:** `real_country_year.csv` (REAL, Findex survey years) + `SYNTHETIC_mobile_money_transactions.csv` (SYNTHETIC: banner required)

| KPI (synthetic) | Formula |
|---|---|
| Value moved (US$) | `SUM(IF [Status] = "completed" THEN [Amount Usd] END)` |
| Transactions | `COUNT([Mm Txn Id])` |
| Average transaction (US$) | `[Value moved] / COUNT(IF [Status] = "completed" THEN [Mm Txn Id] END)` |
| Failure rate | `COUNT(IF [Status] = "failed" THEN [Mm Txn Id] END) / COUNT([Mm Txn Id])` |
| Fee revenue (US$) | `SUM(IF [Status] = "completed" THEN [Fee Usd] END)` |

**Views:** real account ownership vs mobile money account % by country (bar, latest survey year); synthetic monthly value by `Txn Type` (stacked area); value by country.
**Decision supported:** which transaction types drive volume and fees; where mobile money is already mainstream (real data).

## 5. Retail and Consumer Transactions (SYNTHETIC)

**Questions:** When, where and how do customers buy?
**Data:** `SYNTHETIC_retail_transactions.csv` (banner required)

| KPI | Formula |
|---|---|
| Sales (US$) | `SUM([Amount Usd])` |
| Transactions | `COUNTD([Txn Id])` |
| Average basket (US$) | `SUM([Amount Usd]) / COUNTD([Txn Id])` |
| Digital payment share | `SUM(IF [Is Digital Payment] THEN [Amount Usd] END) / SUM([Amount Usd])` |
| Month-end uplift | `AVG(IF [Is Month End Window] THEN [Daily sales] END) / AVG(IF NOT [Is Month End Window] THEN [Daily sales] END) - 1` (with `[Daily sales]` = `{ FIXED [Txn Date] : SUM([Amount Usd]) }`) |

**Views:** monthly sales line (December peak); 100 % stacked bar of payment method by country; sales by merchant category; heatmap day-of-week × age band.
**Decision supported:** staffing and promotions around month-end and December; which payment methods to accept per market.

## 6. Customer Loyalty Analytics (SYNTHETIC)

**Questions:** Is the loyalty programme engaging customers, and what does it cost?
**Data:** `SYNTHETIC_loyalty_customers.csv` (banner required)

| KPI | Formula |
|---|---|
| Members | `COUNTD([Customer Id])` |
| Points earned | `SUM([Points Earned])` |
| Redemption rate | `SUM([Points Redeemed]) / SUM([Points Earned])` |
| Breakage (unredeemed share) | `1 - [Redemption rate]` |
| Outstanding points (liability) | `SUM([Balance Now])` (latest balance per customer, already resolved: never sum balances over time) |
| Never-redeemed members | `COUNTD(IF [Never Redeemed] THEN [Customer Id] END) / [Members]` |
| Spend per member (US$) | `SUM([Spend Usd]) / [Members]` |

**Views:** members by `Engagement Status` (Active / Lapsing / Dormant); spend per member by engagement status; outstanding points by country; never-redeemed share by age band.
**Decision supported:** target lapsing members before they go dormant; size the points liability.

---

## Publishing checklist

- [ ] Workbook title starts with "AfriPulse": e.g. "AfriPulse: African Digital Economy Overview"
- [ ] Synthetic dashboards show the banner text above
- [ ] Every Africa-wide KPI shows its coverage label
- [ ] Source credit in a footer: World Bank (CC BY 4.0), IMF, UN DESA (CC BY 3.0 IGO), Global Findex (CC BY 4.0)
- [ ] Screenshot saved to `tableau/screenshots/` and link added to the README
