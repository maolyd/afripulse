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