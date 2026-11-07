"""Follow-up checks on the UN WPP file: test hypotheses from the profile.

Run:
    python scripts/explore/check_un_wpp.py PATH_TO_WPP_CSV
"""

import sys

import pandas as pd


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def main() -> None:
    path = sys.argv[1]
    df = pd.read_csv(path, low_memory=False)
    # Same file read as plain text, with automatic "NA" -> null detection disabled.
    as_text = pd.read_csv(path, low_memory=False, dtype=str, keep_default_na=False)

    section("H1. UNITS: Angola population, 2025")
    angola = df[(df["ISO3_code"] == "AGO") & (df["Time"] == 2025)]
    print(
        angola[["Location", "Time", "TPopulation1Jan", "TPopulation1July"]].to_string(index=False)
    )
    print("World Bank SP.POP.TOTL, Angola 2025: 39,040,039")

    section("H2. NAMIBIA'S ISO2 CODE")
    default_read = df.loc[df["ISO3_code"] == "NAM", "ISO2_code"].iloc[0]
    text_read = as_text.loc[as_text["ISO3_code"] == "NAM", "ISO2_code"].iloc[0]
    print(f"Default pandas read: {default_read!r}")
    print(f"Read as text:        {text_read!r}")

    section("H3. ROWS WITH A NULL JULY POPULATION, BY YEAR")
    print(df.loc[df["TPopulation1July"].isna(), "Time"].value_counts().to_string())

    section("H4. IS (LocID, Time) A UNIQUE KEY?")
    print(f"Duplicate (LocID, Time) pairs: {df.duplicated(subset=['LocID', 'Time']).sum()}")

    section("H5. LOCATION TYPES")
    print(df.drop_duplicates("LocID")["LocTypeName"].value_counts(dropna=False).to_string())

    section("H6. NAMES SHARED BY MORE THAN ONE LocID")
    shared = df.groupby("Location")["LocID"].unique()
    print(shared[shared.str.len() > 1].to_string())

    section("H7. FOOTNOTE CODES ON COUNTRIES")
    noted = df[df["ISO3_code"].notna() & df["Notes"].notna()]
    print(noted[["ISO3_code", "Location", "Notes"]].drop_duplicates().to_string(index=False))


if __name__ == "__main__":
    main()
