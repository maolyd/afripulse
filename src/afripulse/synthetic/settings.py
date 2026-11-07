"""Typed access to config/synthetic.yml."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from afripulse.config import PROJECT_ROOT

SYNTHETIC_CONFIG_PATH = PROJECT_ROOT / "config" / "synthetic.yml"


@dataclass(frozen=True)
class SyntheticSettings:
    seed: int
    generator_version: int
    start: date
    end: date
    countries: tuple[str, ...]
    customers: int
    min_customers_per_country: int
    merchants_per_1000_customers: float
    retail_txns_per_customer_month: float
    mobile_money_txns_per_user_month: float
    failed_mobile_money_rate: float
    loyalty: dict[str, float]
    calibration_defaults: dict[str, float]
    raw: dict[str, Any]  # the original mapping, for fingerprinting

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SyntheticSettings":
        return cls(
            seed=int(data["seed"]),
            generator_version=int(data["generator_version"]),
            start=_as_date(data["period"]["start"]),
            end=_as_date(data["period"]["end"]),
            countries=tuple(data["countries"]),
            customers=int(data["customers"]),
            min_customers_per_country=int(data["min_customers_per_country"]),
            merchants_per_1000_customers=float(data["merchants_per_1000_customers"]),
            retail_txns_per_customer_month=float(data["retail_txns_per_customer_month"]),
            mobile_money_txns_per_user_month=float(data["mobile_money_txns_per_user_month"]),
            failed_mobile_money_rate=float(data["failed_mobile_money_rate"]),
            loyalty={k: float(v) for k, v in data["loyalty"].items()},
            calibration_defaults={k: float(v) for k, v in data["calibration_defaults"].items()},
            raw=data,
        )


def _as_date(value: Any) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def load_synthetic_settings(path: Path = SYNTHETIC_CONFIG_PATH) -> SyntheticSettings:
    return SyntheticSettings.from_dict(yaml.safe_load(path.read_text(encoding="utf-8")))
