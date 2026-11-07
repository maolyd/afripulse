"""Read the real statistics that calibrate the synthetic data.

For each focus country we take the latest available real value of:

    population            UN WPP 2024, mid-year (stored in thousands, x1000 here: F-UN-1)
    gdp_per_capita_usd    World Bank NY.GDP.PCAP.CD
    mobile_money_share    Findex mobileaccount.t.d, all adults (a fraction: F-FX-3)
    fi_account_share      Findex fiaccount.t.d, all adults

These are read from the RAW tables, because the dbt marts do not exist yet
(Phase 5). Anything missing falls back to config/synthetic.yml defaults, and
every value records where it came from, so the calibration is fully auditable.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)

METRICS = ("population", "gdp_per_capita_usd", "mobile_money_share", "fi_account_share")

_QUERIES = {
    "population": (
        "raw.un_wpp_demographic_indicators",
        """
        SELECT DISTINCT ON (payload->>'ISO3_code')
               payload->>'ISO3_code' AS iso3,
               (payload->>'TPopulation1July')::numeric * 1000 AS value,
               year
        FROM raw.un_wpp_demographic_indicators
        WHERE payload->>'ISO3_code' = ANY(:countries)
          AND year <= extract(year FROM current_date)
          AND payload->>'TPopulation1July' IS NOT NULL
        ORDER BY payload->>'ISO3_code', year DESC
        """,
    ),
    "gdp_per_capita_usd": (
        "raw.worldbank_indicator_values",
        """
        SELECT DISTINCT ON (country_iso3) country_iso3 AS iso3,
               (payload->>'value')::numeric AS value, year
        FROM raw.worldbank_indicator_values
        WHERE indicator_code = 'NY.GDP.PCAP.CD' AND country_iso3 = ANY(:countries)
          AND payload->>'value' IS NOT NULL
        ORDER BY country_iso3, year DESC
        """,
    ),
    "mobile_money_share": (
        "raw.findex_values",
        """
        SELECT DISTINCT ON (codewb) codewb AS iso3,
               (payload->>'mobileaccount.t.d')::numeric AS value, year
        FROM raw.findex_values
        WHERE demographic_group = 'all' AND codewb = ANY(:countries)
          AND payload->>'mobileaccount.t.d' IS NOT NULL
        ORDER BY codewb, year DESC
        """,
    ),
    "fi_account_share": (
        "raw.findex_values",
        """
        SELECT DISTINCT ON (codewb) codewb AS iso3,
               (payload->>'fiaccount.t.d')::numeric AS value, year
        FROM raw.findex_values
        WHERE demographic_group = 'all' AND codewb = ANY(:countries)
          AND payload->>'fiaccount.t.d' IS NOT NULL
        ORDER BY codewb, year DESC
        """,
    ),
}


@dataclass(frozen=True)
class CalibrationValue:
    country_iso3: str
    metric: str
    value: float
    source: str  # source table, or "default"
    source_year: int | None


Calibration = dict[str, dict[str, CalibrationValue]]  # country -> metric -> value


def load_calibration(
    engine: Engine, countries: Sequence[str], defaults: dict[str, float]
) -> Calibration:
    observed: dict[tuple[str, str], CalibrationValue] = {}
    with engine.connect() as conn:
        for metric, (table, query) in _QUERIES.items():
            try:
                rows = conn.execute(text(query), {"countries": list(countries)}).all()
            except Exception as error:  # e.g. the source was never loaded
                logger.warning("Calibration: cannot read %s from %s (%s)", metric, table, error)
                conn.rollback()
                continue
            for iso3, value, year in rows:
                observed[(iso3, metric)] = CalibrationValue(iso3, metric, float(value), table, year)

    calibration: Calibration = {}
    for iso3 in countries:
        calibration[iso3] = {}
        for metric in METRICS:
            found = observed.get((iso3, metric))
            if found is None:
                logger.warning("Calibration: no %s for %s, using default", metric, iso3)
                found = CalibrationValue(iso3, metric, float(defaults[metric]), "default", None)
            calibration[iso3][metric] = found
    return calibration
