# ADR 0001: Definition of "Africa" in AfriPulse

| Item | Detail |
|---|---|
| Status | Accepted |
| Date | 2026-11-07 |
| Reference data | `data/reference/african_countries.csv` |
| Built by | `scripts/reference/build_country_reference.py` |

## Context

Every source defines Africa differently, and none can be used directly:

- World Bank "Sub-Saharan Africa" excludes DJI, DZA, EGY, LBY, MAR, TUN.
- IMF, UN WPP and Findex mix aggregates (regions, income groups) with countries.
- UN WPP lists non-sovereign territories located in Africa (Mayotte, Réunion,
  Saint Helena) as separate locations.
- The African Union has 55 members, including the Sahrawi Arab Democratic
  Republic (Western Sahara, `ESH`). The World Bank and IMF do not list it.
  UN WPP 2024: TODO rows for ESH.

## Decision

AfriPulse covers the **54 African Union member states recognised as sovereign
by the United Nations**, held in a curated, version-controlled reference file.

1. **"Africa" is defined only by the reference file**, never by a source's own
   region field. All sources are filtered with `iso3 IN (reference list)`.
2. **ISO3 is the canonical country key.** ISO2 is kept for convenience only.
3. **Regions use the African Union's five regions** (Northern, Western,
   Central, Eastern, Southern). Source regions are kept as descriptive attributes.
4. **Excluded:** Western Sahara (absent from the World Bank, IMF and Findex, so no
   economic or digital data to analyse) and non-sovereign territories (Mayotte,
   Réunion, Saint Helena), whose economies belong to France and the United Kingdom.
5. **Display names** are curated for readability (e.g. "DR Congo"); the World
   Bank's official name is kept alongside for traceability.

## Alternatives considered

| Option | Rejected because |
|---|---|
| Use World Bank region `SSF` | Silently drops six countries, including Egypt, Algeria and Morocco |
| Include all 55 AU members | Western Sahara has no data in most sources; empty rows mislead |
| Include territories located in Africa | Mixes French/British economies into African totals; breaks consistency with WB/IMF |

## Consequences

- Africa-wide totals will match World Bank and IMF country coverage.
- Western Sahara is out of scope; this must be stated on dashboards.
- Any new source must be mapped to ISO3 before it can join the warehouse.
- Changing the definition requires a new ADR, not an ad-hoc filter.