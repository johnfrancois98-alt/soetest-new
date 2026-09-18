"""
Shared portfolio-level helpers used across pages — chiefly, reducing a
SOE-year panel down to one row per SOE so counts/averages aren't inflated
by counting the same SOE once per year it appears.
"""

import pandas as pd


def latest_per_soe(df: pd.DataFrame) -> pd.DataFrame:
    """One row per SOE: its most recent year if Year data varies, else the
    row as-is (already one row per SOE)."""
    if df.empty:
        return df
    has_years = df["Year"].astype(str).str.strip().ne("").any() and df["Year"].nunique() > 1
    if has_years:
        return df.sort_values("Year").groupby("SOE", as_index=False).last()
    return df.drop_duplicates(subset=["SOE"], keep="first")
