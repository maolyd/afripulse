"""Unit tests for the synthetic data generator (no database: calibration is faked)."""

import dataclasses
from pathlib import Path

import pandas as pd
import pytest

from afripulse.ingestion.jobs import synthetic_fingerprint
from afripulse.synthetic.calibration import CalibrationValue
from afripulse.synthetic.generators import (
    allocate_customers,
    generate_dataset,
    typical_purchase_usd,
)
from afripulse.synthetic.invariants import find_invariant_violations
from afripulse.synthetic.settings import load_synthetic_settings

SMALL_SETTINGS = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_small.yml"

# Kenya: mobile money leader. Egypt: mostly cash. (Real Findex 2024 levels.)
REAL = {
    "KEN": {
        "population": 57e6,
        "gdp_per_capita_usd": 2100,
        "mobile_money_share": 0.875,
        "fi_account_share": 0.454,
    },
    "EGY": {
        "population": 117e6,
        "gdp_per_capita_usd": 3300,
        "mobile_money_share": 0.156,
        "fi_account_share": 0.353,
    },
}


def calibration(real=REAL):
    return {
        iso3: {m: CalibrationValue(iso3, m, v, "test", 2024) for m, v in metrics.items()}
        for iso3, metrics in real.items()
    }


@pytest.fixture(scope="module")
def settings():
    return load_synthetic_settings(SMALL_SETTINGS)


@pytest.fixture(scope="module")
def dataset(settings):
    return generate_dataset(settings, calibration())


def test_same_seed_gives_identical_data(settings, dataset):
    again = generate_dataset(settings, calibration())

    for name, df in dataset.tables().items():
        pd.testing.assert_frame_equal(df, again.tables()[name], obj=name)


def test_different_seed_gives_different_data(settings, dataset):
    other = generate_dataset(dataclasses.replace(settings, seed=7), calibration())

    assert not dataset.retail_transactions["amount_usd"].equals(
        other.retail_transactions["amount_usd"]
    )


def test_every_invariant_holds(settings, dataset):
    assert find_invariant_violations(dataset, settings.start, settings.end) == []


def test_invariants_catch_a_planted_error(settings, dataset):
    broken = dataclasses.replace(dataset, retail_transactions=dataset.retail_transactions.copy())
    unbanked = dataset.customers.loc[~dataset.customers["has_bank_account"], "customer_id"].iloc[0]
    broken.retail_transactions.loc[0, ["customer_id", "payment_method"]] = [unbanked, "card"]

    problems = find_invariant_violations(broken, settings.start, settings.end)

    assert any("card payment by customer without bank account" in p for p in problems)


def test_customers_follow_population_with_a_minimum(settings):
    allocation = allocate_customers(settings, calibration())

    assert sum(allocation.values()) == 400
    assert min(allocation.values()) >= 100
    assert allocation["EGY"] > allocation["KEN"]  # larger population


def test_mobile_money_use_follows_real_findex_shares(dataset):
    """The core calibration promise: Kenya's customers use mobile money far more than Egypt's."""
    retail = dataset.retail_transactions.merge(dataset.customers, on="customer_id")
    share = retail.groupby("country_iso3")["payment_method"].apply(
        lambda methods: (methods == "mobile_money").mean()
    )

    assert share["KEN"] > 3 * share["EGY"]


def test_typical_purchase_grows_with_income_but_is_bounded():
    assert typical_purchase_usd(1000) < typical_purchase_usd(6000)
    assert typical_purchase_usd(1) == 2.0
    assert typical_purchase_usd(10_000_000) == 40.0


def test_loyalty_balances_never_go_negative_and_points_are_redeemed(dataset):
    loyalty = dataset.loyalty_events

    assert (loyalty["balance_after"] >= 0).all()
    assert (loyalty["event_type"] == "redeem").any()


def test_every_mobile_money_retail_payment_has_a_matching_wallet_transaction(dataset):
    paid = dataset.retail_transactions.query("payment_method == 'mobile_money'")["txn_id"]
    mirrored = dataset.mobile_money_transactions["retail_txn_id"].dropna()

    assert set(paid) == set(mirrored)


def test_fingerprint_changes_only_when_inputs_change(settings):
    base = synthetic_fingerprint(settings, calibration())
    changed_real = {**REAL, "KEN": {**REAL["KEN"], "mobile_money_share": 0.9}}

    assert synthetic_fingerprint(settings, calibration()) == base
    assert synthetic_fingerprint(settings, calibration(changed_real)) != base
    reseeded = dataclasses.replace(settings, raw={**settings.raw, "seed": 7})
    assert synthetic_fingerprint(reseeded, calibration()) != base
