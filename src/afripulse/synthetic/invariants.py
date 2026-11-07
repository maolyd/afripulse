"""Rules the synthetic data must ALWAYS satisfy. Checked before every load.

Generated data is only useful if it is internally consistent: a dashboard built
on broken synthetic data teaches the wrong lessons. Each rule returns a list of
problems; an empty list means the rule holds.
"""

from datetime import timedelta

import pandas as pd

from afripulse.synthetic.generators import SyntheticDataset


def find_invariant_violations(data: SyntheticDataset, start, end) -> list[str]:
    problems: list[str] = []
    customers, merchants = data.customers, data.merchants
    retail, mm, loyalty = (
        data.retail_transactions,
        data.mobile_money_transactions,
        data.loyalty_events,
    )

    def check(condition_failures: int, message: str) -> None:
        if condition_failures:
            problems.append(f"{message}: {condition_failures} row(s)")

    for name, df, key in [
        ("customers", customers, "customer_id"),
        ("merchants", merchants, "merchant_id"),
        ("retail_transactions", retail, "txn_id"),
        ("mobile_money_transactions", mm, "mm_txn_id"),
        ("loyalty_events", loyalty, "event_id"),
    ]:
        check(df[key].duplicated().sum(), f"{name}: duplicate {key}")

    # Referential integrity, also enforced later by the database's foreign keys.
    check((~retail["customer_id"].isin(customers["customer_id"])).sum(), "retail: unknown customer")
    check((~retail["merchant_id"].isin(merchants["merchant_id"])).sum(), "retail: unknown merchant")

    # Shoppers buy from merchants in their own country.
    country = retail.merge(customers[["customer_id", "country_iso3"]], on="customer_id").merge(
        merchants[["merchant_id", "country_iso3"]], on="merchant_id", suffixes=("_c", "_m")
    )
    check((country["country_iso3_c"] != country["country_iso3_m"]).sum(), "retail: cross-border")

    # Nobody pays by mobile money without an account, or by card without a bank account.
    method = retail.merge(customers, on="customer_id")
    check(
        ((method["payment_method"] == "mobile_money") & ~method["has_mobile_money"]).sum(),
        "retail: mobile money payment by customer without mobile money",
    )
    check(
        ((method["payment_method"] == "card") & ~method["has_bank_account"]).sum(),
        "retail: card payment by customer without bank account",
    )

    # Mobile money transactions belong to mobile money users.
    mm_users = set(customers.loc[customers["has_mobile_money"], "customer_id"])
    check((~mm["customer_id"].isin(mm_users)).sum(), "mobile money: customer without account")

    # Amounts and timing.
    check((retail["amount_usd"] <= 0).sum(), "retail: non-positive amount")
    check((mm["amount_usd"] <= 0).sum(), "mobile money: non-positive amount")
    # Day arithmetic in plain Python: adding a pd.Timedelta triggers a NumPy
    # deprecation warning with recent NumPy versions.
    period_start, period_end = pd.Timestamp(start), pd.Timestamp(end + timedelta(days=1))
    outside = (retail["txn_ts"] < period_start) | (retail["txn_ts"] >= period_end)
    check(outside.sum(), "retail: timestamp outside period")
    signup = retail.merge(customers[["customer_id", "signup_date"]], on="customer_id")
    check(
        (signup["txn_ts"] < pd.to_datetime(signup["signup_date"])).sum(),
        "retail: purchase before customer signed up",
    )

    # Loyalty: balances never go negative, and only members take part.
    check((loyalty["balance_after"] < 0).sum(), "loyalty: negative balance")
    # ...and in time order, each balance = previous balance + earned - redeemed.
    ordered = loyalty.sort_values(["customer_id", "event_ts", "event_id"], kind="stable")
    signed = ordered["points"].where(ordered["event_type"] == "earn", -ordered["points"])
    previous = ordered.groupby("customer_id")["balance_after"].shift(1).fillna(0)
    check(
        (previous + signed != ordered["balance_after"]).sum(),
        "loyalty: balance not consistent in time order",
    )
    members = set(customers.loc[customers["is_loyalty_member"], "customer_id"])
    check((~loyalty["customer_id"].isin(members)).sum(), "loyalty: event for non-member")
    return problems
