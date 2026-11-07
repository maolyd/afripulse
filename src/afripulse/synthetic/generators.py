"""Generate synthetic customers, merchants and transactions.

Pure functions: settings + calibration + a seeded random generator in,
pandas DataFrames out. No database and no clock are involved, so the same seed
and the same calibration always produce exactly the same data (reproducible).

How real statistics shape the synthetic data:

    population          -> how many customers each country gets
    gdp_per_capita_usd  -> typical transaction size (richer markets spend more)
    mobile_money_share  -> share of customers with mobile money, and how often they use it
    fi_account_share    -> share with a bank account, and so how often cards are used

Realistic patterns added on top: log-normal amounts (many small purchases, few
large ones), busier weekends, month-end salary peaks, a December peak, and
daytime/evening hours.
"""

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from afripulse.synthetic.calibration import Calibration
from afripulse.synthetic.settings import SyntheticSettings

CITIES = {
    "KEN": ["Nairobi", "Mombasa", "Kisumu"],
    "NGA": ["Lagos", "Abuja", "Kano"],
    "GHA": ["Accra", "Kumasi", "Tamale"],
    "ZAF": ["Johannesburg", "Cape Town", "Durban"],
    "EGY": ["Cairo", "Alexandria", "Giza"],
    "SEN": ["Dakar", "Thiès", "Saint-Louis"],
    "UGA": ["Kampala", "Gulu", "Mbarara"],
    "TZA": ["Dar es Salaam", "Dodoma", "Mwanza"],
}
CITY_WEIGHTS = [0.6, 0.25, 0.15]

AGE_BANDS = ["18-24", "25-34", "35-44", "45-54", "55+"]
AGE_WEIGHTS = [0.24, 0.31, 0.22, 0.13, 0.10]  # young, urban customer base

# category: (share of merchants, amount multiplier, card acceptance probability)
MERCHANT_CATEGORIES = {
    "grocery": (0.30, 1.0, 0.45),
    "restaurant": (0.15, 1.1, 0.40),
    "pharmacy": (0.10, 1.3, 0.55),
    "fuel": (0.10, 2.0, 0.70),
    "clothing": (0.10, 2.5, 0.50),
    "airtime_data": (0.10, 0.4, 0.20),
    "electronics": (0.07, 6.0, 0.85),
    "utilities": (0.08, 2.2, 0.60),
}

# mobile money type: (probability, amount multiplier vs a typical purchase, fee rate)
MOBILE_MONEY_TYPES = {
    "p2p_transfer": (0.35, 2.0, 0.010),
    "cash_in": (0.20, 3.0, 0.000),
    "cash_out": (0.20, 2.5, 0.015),
    "airtime_purchase": (0.12, 0.3, 0.000),
    "bill_payment": (0.13, 2.5, 0.000),
}
AMOUNT_SIGMA = 0.9  # spread of the log-normal amount distribution

# Hour-of-day profile: quiet nights, lunchtime and after-work peaks.
HOUR_WEIGHTS = np.array(
    [1, 1, 1, 1, 1, 2, 4, 6, 8, 9, 10, 11, 13, 12, 10, 9, 10, 12, 13, 11, 8, 5, 3, 2], float
)


@dataclass
class SyntheticDataset:
    customers: pd.DataFrame
    merchants: pd.DataFrame
    retail_transactions: pd.DataFrame
    mobile_money_transactions: pd.DataFrame
    loyalty_events: pd.DataFrame

    def tables(self) -> dict[str, pd.DataFrame]:
        """In load order: parents before children (foreign keys)."""
        return {
            "customers": self.customers,
            "merchants": self.merchants,
            "retail_transactions": self.retail_transactions,
            "mobile_money_transactions": self.mobile_money_transactions,
            "loyalty_events": self.loyalty_events,
        }


# ------------------------------------------------------------------ helpers


def typical_purchase_usd(gdp_per_capita: float) -> float:
    """Median basket size: grows with income, but much more slowly (square root)."""
    return float(np.clip(1.5 * np.sqrt(gdp_per_capita / 100), 2.0, 40.0))


def day_weights(days: pd.DatetimeIndex) -> np.ndarray:
    """Relative transaction volume per calendar day."""
    weekday = np.array([0.95, 0.95, 1.0, 1.0, 1.1, 1.2, 0.85])[days.dayofweek]
    month_end = np.where(days.day >= 25, 1.3, 1.0)  # salaries are paid at month end
    december = np.where(days.month == 12, 1.4, 1.0)  # festive season
    return weekday * month_end * december


def allocate_customers(settings: SyntheticSettings, calibration: Calibration) -> dict[str, int]:
    """Customers per country: a guaranteed minimum, the rest in proportion to population."""
    countries = list(settings.countries)
    minimum = settings.min_customers_per_country
    remaining = settings.customers - minimum * len(countries)
    if remaining < 0:
        raise ValueError("customers is smaller than min_customers_per_country x countries")
    population = np.array([calibration[c]["population"].value for c in countries])
    extra = np.floor(remaining * population / population.sum()).astype(int)
    extra[np.argmax(population)] += remaining - extra.sum()  # rounding remainder
    return {country: minimum + int(n) for country, n in zip(countries, extra, strict=True)}


def _timestamps(rng: np.random.Generator, days: pd.DatetimeIndex, probs: np.ndarray, n: int):
    picked = days[rng.choice(len(days), size=n, p=probs)]
    hours = rng.choice(24, size=n, p=HOUR_WEIGHTS / HOUR_WEIGHTS.sum())
    seconds = rng.integers(0, 3600, size=n)
    return picked + pd.to_timedelta(hours, "h") + pd.to_timedelta(seconds, "s")


# --------------------------------------------------------------- generators


def generate_customers(
    settings: SyntheticSettings, calibration: Calibration, rng: np.random.Generator
) -> pd.DataFrame:
    frames = []
    signup_start = date(2019, 1, 1)
    signup_days = (settings.end - timedelta(days=60) - signup_start).days
    for country, n in allocate_customers(settings, calibration).items():
        cal = calibration[country]
        frames.append(
            pd.DataFrame(
                {
                    "country_iso3": country,
                    "city": rng.choice(CITIES[country], size=n, p=CITY_WEIGHTS),
                    "gender": rng.choice(["female", "male"], size=n),
                    "age_band": rng.choice(AGE_BANDS, size=n, p=AGE_WEIGHTS),
                    "signup_date": [
                        signup_start + timedelta(days=int(d))
                        for d in rng.integers(0, signup_days, size=n)
                    ],
                    "has_mobile_money": rng.random(n) < cal["mobile_money_share"].value,
                    "has_bank_account": rng.random(n) < cal["fi_account_share"].value,
                    "is_loyalty_member": rng.random(n) < settings.loyalty["membership_rate"],
                }
            )
        )
    customers = pd.concat(frames, ignore_index=True)
    customers.insert(0, "customer_id", [f"CUS-{i:06d}" for i in range(1, len(customers) + 1)])
    return customers


def generate_merchants(
    settings: SyntheticSettings, customers: pd.DataFrame, rng: np.random.Generator
) -> pd.DataFrame:
    categories = list(MERCHANT_CATEGORIES)
    shares = np.array([MERCHANT_CATEGORIES[c][0] for c in categories])
    frames = []
    for country, n_customers in customers["country_iso3"].value_counts(sort=False).items():
        n = max(10, round(n_customers * settings.merchants_per_1000_customers / 1000))
        category = rng.choice(categories, size=n, p=shares / shares.sum())
        card_probability = np.array([MERCHANT_CATEGORIES[c][2] for c in category])
        city = rng.choice(CITIES[country], size=n, p=CITY_WEIGHTS)
        frames.append(
            pd.DataFrame(
                {
                    "country_iso3": country,
                    "city": city,
                    "category": category,
                    "accepts_card": rng.random(n) < card_probability,
                    "accepts_mobile_money": rng.random(n) < 0.85,
                    "onboard_date": [
                        date(2018, 1, 1) + timedelta(days=int(d))
                        for d in rng.integers(0, 2000, size=n)
                    ],
                }
            )
        )
    merchants = pd.concat(frames, ignore_index=True)
    merchants.insert(0, "merchant_id", [f"MER-{i:05d}" for i in range(1, len(merchants) + 1)])
    label = merchants["category"].str.replace("_", " & ").str.title()
    merchants.insert(
        1,
        "merchant_name",
        merchants["city"] + " " + label + " " + merchants["merchant_id"].str[-3:],
    )
    return merchants


def _payment_methods(
    rng: np.random.Generator,
    n: int,
    customer: pd.Series,
    mm_share: float,
    fi_share: float,
    accepts_card: np.ndarray,
    accepts_mm: np.ndarray,
) -> np.ndarray:
    """Choose a payment method per purchase, from what customer AND merchant can use."""
    weights = np.zeros((n, 4))  # cash, card, mobile_money, bank_transfer
    weights[:, 0] = 1.0
    if customer["has_bank_account"]:
        weights[:, 1] = 1.5 * fi_share * accepts_card
        weights[:, 3] = 0.05
    if customer["has_mobile_money"]:
        weights[:, 2] = 3.0 * mm_share * accepts_mm
    cumulative = np.cumsum(weights / weights.sum(axis=1, keepdims=True), axis=1)
    picks = (rng.random((n, 1)) > cumulative).sum(axis=1)
    return np.array(["cash", "card", "mobile_money", "bank_transfer"])[np.minimum(picks, 3)]


def generate_retail_transactions(
    settings: SyntheticSettings,
    calibration: Calibration,
    customers: pd.DataFrame,
    merchants: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    days = pd.date_range(settings.start, settings.end, freq="D")
    weights = day_weights(days)
    months = len(days) / 30.44
    merchants_by_country = {c: g for c, g in merchants.groupby("country_iso3")}
    multiplier = {c: v[1] for c, v in MERCHANT_CATEGORIES.items()}

    frames = []
    for customer in customers.itertuples(index=False):
        active = days >= pd.Timestamp(customer.signup_date)
        if not active.any():
            continue
        active_months = months * active.mean()
        n = rng.poisson(settings.retail_txns_per_customer_month * active_months)
        if n == 0:
            continue
        cal = calibration[customer.country_iso3]
        shop = merchants_by_country[customer.country_iso3].sample(
            n=n, replace=True, random_state=rng
        )
        probs = weights * active
        typical = typical_purchase_usd(cal["gdp_per_capita_usd"].value)
        amounts = (
            typical
            * shop["category"].map(multiplier).to_numpy()
            * rng.lognormal(0, AMOUNT_SIGMA, size=n)
        )
        frames.append(
            pd.DataFrame(
                {
                    "customer_id": customer.customer_id,
                    "merchant_id": shop["merchant_id"].to_numpy(),
                    "txn_ts": _timestamps(rng, days, probs / probs.sum(), n),
                    "payment_method": _payment_methods(
                        rng,
                        n,
                        pd.Series(customer._asdict()),
                        cal["mobile_money_share"].value,
                        cal["fi_account_share"].value,
                        shop["accepts_card"].to_numpy(),
                        shop["accepts_mobile_money"].to_numpy(),
                    ),
                    "amount_usd": np.maximum(np.round(amounts, 2), 0.1),
                    "item_count": 1 + rng.poisson(2, size=n),
                }
            )
        )
    retail = pd.concat(frames, ignore_index=True).sort_values("txn_ts", kind="stable")
    retail.insert(0, "txn_id", [f"RTX-{i:07d}" for i in range(1, len(retail) + 1)])
    return retail.reset_index(drop=True)


def generate_mobile_money_transactions(
    settings: SyntheticSettings,
    calibration: Calibration,
    customers: pd.DataFrame,
    retail: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    days = pd.date_range(settings.start, settings.end, freq="D")
    weights = day_weights(days)
    months = len(days) / 30.44
    users = customers[customers["has_mobile_money"]]
    users_by_country = {c: g["customer_id"].to_numpy() for c, g in users.groupby("country_iso3")}
    types = list(MOBILE_MONEY_TYPES)
    type_probs = np.array([MOBILE_MONEY_TYPES[t][0] for t in types])

    frames = []
    for user in users.itertuples(index=False):
        active = days >= pd.Timestamp(user.signup_date)
        n = rng.poisson(settings.mobile_money_txns_per_user_month * months * active.mean())
        if n == 0:
            continue
        txn_type = rng.choice(types, size=n, p=type_probs)
        typical = typical_purchase_usd(calibration[user.country_iso3]["gdp_per_capita_usd"].value)
        size = np.array([MOBILE_MONEY_TYPES[t][1] for t in txn_type])
        fee_rate = np.array([MOBILE_MONEY_TYPES[t][2] for t in txn_type])
        amount = np.maximum(np.round(typical * size * rng.lognormal(0, AMOUNT_SIGMA, n), 2), 0.1)
        peers = users_by_country[user.country_iso3]
        counterparty = np.where(txn_type == "p2p_transfer", rng.choice(peers, size=n), None)
        counterparty = np.where(counterparty == user.customer_id, None, counterparty)
        probs = weights * active
        frames.append(
            pd.DataFrame(
                {
                    "customer_id": user.customer_id,
                    "txn_type": txn_type,
                    "amount_usd": amount,
                    "fee_usd": np.round(amount * fee_rate, 2),
                    "txn_ts": _timestamps(rng, days, probs / probs.sum(), n),
                    "counterparty_customer_id": counterparty,
                    "merchant_id": None,
                    "retail_txn_id": None,
                }
            )
        )

    # Every retail purchase paid by mobile money also appears as a merchant payment.
    paid = retail[retail["payment_method"] == "mobile_money"]
    frames.append(
        pd.DataFrame(
            {
                "customer_id": paid["customer_id"].to_numpy(),
                "txn_type": "merchant_payment",
                "amount_usd": paid["amount_usd"].to_numpy(),
                "fee_usd": 0.0,
                "txn_ts": paid["txn_ts"].to_numpy(),
                "counterparty_customer_id": None,
                "merchant_id": paid["merchant_id"].to_numpy(),
                "retail_txn_id": paid["txn_id"].to_numpy(),
            }
        )
    )
    mm = pd.concat(frames, ignore_index=True).sort_values("txn_ts", kind="stable")
    failed = (rng.random(len(mm)) < settings.failed_mobile_money_rate) & mm["retail_txn_id"].isna()
    mm.insert(2, "status", np.where(failed, "failed", "completed"))
    mm.insert(0, "mm_txn_id", [f"MMT-{i:07d}" for i in range(1, len(mm) + 1)])
    return mm.reset_index(drop=True)


def generate_loyalty_events(
    settings: SyntheticSettings,
    customers: pd.DataFrame,
    retail: pd.DataFrame,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Members earn points on every purchase and sometimes redeem them.

    Processed in time order per customer, so the balance can never go negative.
    A redemption is always timestamped BEFORE the customer's next purchase, so
    balances stay consistent in time order (caught by the dbt reconciliation test).
    """
    points_per_usd = settings.loyalty["points_per_usd"]
    threshold = int(settings.loyalty["redeem_threshold"])
    redeem_probability = settings.loyalty["redeem_probability"]
    members = set(customers.loc[customers["is_loyalty_member"], "customer_id"])
    purchases = retail[retail["customer_id"].isin(members)].sort_values(
        ["customer_id", "txn_ts"], kind="stable"
    )
    # When does each customer shop next? (NaT after their last purchase.)
    purchases = purchases.assign(next_txn_ts=purchases.groupby("customer_id")["txn_ts"].shift(-1))

    events = []
    balance: dict[str, int] = {}
    for txn in purchases.itertuples(index=False):
        earned = int(txn.amount_usd * points_per_usd)
        if earned <= 0:
            continue
        current = balance.get(txn.customer_id, 0) + earned
        events.append((txn.customer_id, "earn", earned, current, txn.txn_ts, txn.txn_id))
        if current >= threshold and rng.random() < redeem_probability:
            current -= threshold
            delay = timedelta(hours=int(rng.integers(1, 72)))
            if not pd.isna(txn.next_txn_ts):  # redeem before the next purchase
                delay = min(delay, (txn.next_txn_ts - txn.txn_ts) / 2)
            redeemed_at = txn.txn_ts + delay
            events.append((txn.customer_id, "redeem", threshold, current, redeemed_at, None))
        balance[txn.customer_id] = current

    loyalty = pd.DataFrame(
        events,
        columns=[
            "customer_id",
            "event_type",
            "points",
            "balance_after",
            "event_ts",
            "retail_txn_id",
        ],
    ).sort_values("event_ts", kind="stable")
    loyalty.insert(0, "event_id", [f"LYE-{i:07d}" for i in range(1, len(loyalty) + 1)])
    return loyalty.reset_index(drop=True)


def generate_dataset(settings: SyntheticSettings, calibration: Calibration) -> SyntheticDataset:
    """Generate every table from one seeded random generator."""
    rng = np.random.default_rng(settings.seed)
    customers = generate_customers(settings, calibration, rng)
    merchants = generate_merchants(settings, customers, rng)
    retail = generate_retail_transactions(settings, calibration, customers, merchants, rng)
    mobile_money = generate_mobile_money_transactions(settings, calibration, customers, retail, rng)
    loyalty = generate_loyalty_events(settings, customers, retail, rng)
    return SyntheticDataset(customers, merchants, retail, mobile_money, loyalty)
