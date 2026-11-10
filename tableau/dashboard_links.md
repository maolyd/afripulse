# AfriPulse Tableau Public dashboards

| # | Dashboard | Link | Screenshot |
|---|---|---|---|
| 1 | African Digital Economy Overview | https://public.tableau.com/app/profile/mawuli.dogbey/viz/AfriPulseAfricanDigitalEconomyOverview/Dashboard1 | screenshots/01_overview.png |

## 2. Country Comparison

- **Link:** PASTE-YOUR-SHARE-LINK-HERE
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
  - 2005 to 2024 (population-weighted): mobile subscriptions 15 → 96 per 100, internet use 4% → 41%,
    fixed broadband 0 → about 3 per 100. Africa went online by mobile.
  - Largest gaps between mobile access and internet use: Zambia (83 points), Uganda (74), Burkina Faso (72).
  - Sudan (2017), South Sudan (2019) and Eritrea (2020) have no recent internet data.
- **Technique notes:**
  - Raw subscriptions ranked South Africa near the top despite 78% internet use (multi-SIM
    ownership), so the gap caps subscriptions at 100.
  - Latest value and growth since 2015 use FIXED level-of-detail expressions, aggregated with AVG
    (not SUM) because the value repeats on every year row.