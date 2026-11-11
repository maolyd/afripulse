# AfriPulse Tableau Public dashboards

| # | Dashboard | Link | Screenshot |
|---|---|---|---|
| 1 | African Digital Economy Overview | https://public.tableau.com/app/profile/mawuli.dogbey/viz/AfriPulseAfricanDigitalEconomyOverview/Dashboard1 | screenshots/01_overview.png |

## 2. Country Comparison

- **Link:** (https://public.tableau.com/app/profile/mawuli.dogbey/viz/AfriPulseAfricanDigitalEconomyOverview/CountryComparison)
- **Screenshot:** [screenshots/02_country_comparison.png](screenshots/02_country_comparison.png)
- **Data:** `real_country_year.csv`, `real_indicator_sources.csv` (REAL)
- **Findings:**
  - Senegal and The Gambia are as connected as Botswana at a quarter of its income.
  - Kenya and Ghana reach near-universal account ownership through mobile money (87% and 78%).
  - IMF and World Bank GDP growth differ by more than 2 points in 99 country-years across
    26 countries; Burundi (9 years), Sierra Leone, Sudan and Uganda (7) are the most contested.
    Kenya's sources agree.
- **Technique note:** the top-10 chart uses context filters so Top N is computed after the
  indicator, disagreement and projection filters (Tableau order of operations).


  ## 3. Mobile & Internet Adoption

- **Link:** (https://public.tableau.com/app/profile/mawuli.dogbey/viz/AfriPulseAfricanDigitalEconomyOverview/MobileInternetAdoption)
- **Screenshot:** [screenshots/03_mobile_internet_adoption.png](screenshots/03_mobile_internet_adoption.png)
- **Data:** `real_country_year.csv` (REAL)
- **Findings:**
    - Coverage: mobile subscriptions for 2024 come from 39 of 54 countries (publication lag, F15);
    the data quality report flags this as AMBER. The 2024 value is population-weighted over
    reporting countries only.
  - 2005 to 2024 (population-weighted): mobile subscriptions 15 → 96 per 100, internet use 4% → 41%,
    fixed broadband 0 → about 3 per 100. Africa went online by mobile.
  - Largest gaps between mobile access and internet use: Zambia (83 points), Uganda (74), Burkina Faso (72).
  - Sudan (2017), South Sudan (2019) and Eritrea (2020) have no recent internet data.
- **Technique notes:**
  - Raw subscriptions ranked South Africa near the top despite 78% internet use (multi-SIM
    ownership), so the gap caps subscriptions at 100.
  - Latest value and growth since 2015 use FIXED level-of-detail expressions, aggregated with AVG
    (not SUM) because the value repeats on every year row.

    ## 4. Mobile Money & Digital Payments

- **Link:** (https://public.tableau.com/app/profile/mawuli.dogbey/viz/AfriPulseAfricanDigitalEconomyOverview/MobileMoneyPayments)
- **Screenshot:** [screenshots/04_mobile_money_payments.png](screenshots/04_mobile_money_payments.png)
- **Data:** `real_country_year.csv` (REAL, Global Findex) + `SYNTHETIC_mobile_money_transactions.csv`
  (SYNTHETIC, labelled with a banner on the dashboard)
- **Findings:**
  - Real (Findex): in Kenya, Ghana, Uganda and Senegal mobile money accounts nearly equal all
    accounts; in South Africa, Egypt and Nigeria accounts are mostly bank-based.
  - Synthetic: 251,139 wallet transactions moving $5.19m (average $20.99, fee revenue $29,846).
    P2P transfers move the most value, with December peaks.
  - The synthetic value ranking by country follows the real Findex adoption ranking, which is
    evidence the generator's calibration works.
- **Data check:** the failure rate is 1.6%, not the configured 2%, because purchase-linked merchant
  payments never fail (`generators.py`, line 338): a deliberate consistency rule.

  ## 5. Retail & Consumer Transactions (SYNTHETIC)

- **Link:** https://public.tableau.com/views/AfriPulseAfricanDigitalEconomyOverview/RetailConsumer?:language=en-US&:sid=&:redirect=auth&:display_count=n&:origin=viz_share_link
- **Screenshot:** [screenshots/05_retail_consumer.png](screenshots/05_retail_consumer.png)
- **Data:** `SYNTHETIC_retail_transactions.csv` (SYNTHETIC, banner on the dashboard)
- **KPIs:** $3,663,091 sales, 211,037 purchases, $17 average basket, DIGITAL-SHARE% digital payments,
  +31% month-end uplift.
- **Validated against the generator code:** month-end uplift 31% (code: x1.3); Saturday 16.5-17.2%
  of each age band's sales (expected 17.0%), Sunday 11.6-12.9% (expected 12.1%); December peaks;
  211,037 purchases explained by customer sign-up dates (expected about 209,000).
- **Modelling note:** the real Findex mobile money share sets both wallet ownership and usage
  frequency, so country differences are amplified (Tanzania: 53% real adoption, 22% of synthetic sales).

  ## 6. Customer Loyalty Analytics (SYNTHETIC)

- **Link:** (https://public.tableau.com/views/AfriPulseAfricanDigitalEconomyOverview/CustomerLoyalty?:language=en-US&:sid=&:redirect=auth&:display_count=n&:origin=viz_share_link)
- **Screenshot:** [screenshots/06_customer_loyalty.png](screenshots/06_customer_loyalty.png)
- **Data:** `SYNTHETIC_loyalty_customers.csv` (SYNTHETIC, banner on the dashboard)
- **KPIs:** 2,986 members, 21,703,438 points earned, 73.3% redemption rate, 26.7% breakage,
  5,797,938 outstanding points, $728.74 spend per member.
- **Reconciliation:** points earned - redeemed - held = 0, the same rule checked in Python
  (`invariants.py`) and dbt (`assert_loyalty_balances_reconcile`).
- **Engagement:** 2,775 active, 206 lapsing, 5 dormant; spend per member falls from $733 (active)
  to $563 (dormant).
- **Known limitation:** Egypt and Ghana out-spend South Africa per member because each country's
  small random merchant pool drives basket size as much as income does. A future generator version
  could stratify merchant categories by country.