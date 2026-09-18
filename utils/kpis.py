"""
KPI ratio calculations and threshold-based flagging. Formulas follow the
IMF SOE Health Check Tool User Guide, Figure A2.4.
"""

import pandas as pd

from config import KPI_THRESHOLDS
from utils.data_io import FIELD_TO_COLUMN


def available_kpis(df: pd.DataFrame, category=None):
    """
    Which KPIs have all their required input columns present (non-empty).
    Pass category ("profitability"/"liquidity"/"solvency") to filter to
    just that group; omit it to check every KPI.
    """
    from config import KPI_CATEGORIES

    keys = KPI_CATEGORIES[category] if category else list(KPI_THRESHOLDS.keys())
    available = []
    for key in keys:
        spec = KPI_THRESHOLDS[key]
        cols = [FIELD_TO_COLUMN[f] for f in spec["requires"]]
        if all(c in df.columns and df[c].notna().any() for c in cols):
            available.append(key)
    return available


def compute_kpis(df: pd.DataFrame) -> pd.DataFrame:
    """Adds one column per computable KPI (NaN where inputs are missing)."""
    out = df.copy()

    def safe_div(a, b):
        a = pd.to_numeric(a, errors="coerce")
        b = pd.to_numeric(b, errors="coerce")
        return a / b.replace({0: pd.NA})

    def has(*cols):
        return all(c in out.columns for c in cols)

    # Profitability
    if has("NetIncome", "Revenue"):
        out["net_profit_margin"] = safe_div(out["NetIncome"], out["Revenue"])
    if has("EBIT", "Revenue"):
        out["operating_profit_margin"] = safe_div(out["EBIT"], out["Revenue"])
    if has("NetIncome", "TotalAssets"):
        out["roa"] = safe_div(out["NetIncome"], out["TotalAssets"])
    if has("NetIncome", "TotalEquity"):
        out["roe"] = safe_div(out["NetIncome"], out["TotalEquity"])
    if has("Revenue", "OperatingExpense"):
        out["cost_recovery"] = safe_div(out["Revenue"], out["OperatingExpense"])

    # Liquidity
    if has("CurrentAssets", "CurrentLiabilities"):
        out["current_ratio"] = safe_div(out["CurrentAssets"], out["CurrentLiabilities"])

    # Solvency
    if has("TotalLiabilities", "TotalAssets"):
        out["debt_to_assets"] = safe_div(out["TotalLiabilities"], out["TotalAssets"])
    if has("TotalLiabilities", "TotalEquity"):
        out["debt_to_equity"] = safe_div(out["TotalLiabilities"], out["TotalEquity"])
    if has("TotalLiabilities", "EBITDA"):
        out["debt_to_ebitda"] = safe_div(out["TotalLiabilities"], out["EBITDA"])
    if has("EBIT", "InterestExpense"):
        out["interest_coverage"] = safe_div(out["EBIT"], out["InterestExpense"])
    if has("EBITDA", "InterestExpense"):
        out["cash_interest_coverage"] = safe_div(out["EBITDA"], out["InterestExpense"])
    if has("GovernmentGrants", "Revenue"):
        total_revenue_incl_grants = out["Revenue"] + out["GovernmentGrants"]
        out["government_transfers_to_revenue"] = safe_div(out["GovernmentGrants"], total_revenue_incl_grants)

    return out


def classify(value, kpi_key):
    """Returns (label, color_key) for a single KPI value: red/amber/green."""
    if pd.isna(value):
        return "No data", "muted"

    spec = KPI_THRESHOLDS[kpi_key]
    red_cut, green_cut = spec["red_cut"], spec["green_cut"]

    if spec["direction"] == "higher_is_better":
        if value < red_cut:
            return "Red", "red"
        if value >= green_cut:
            return "Green", "green"
        return "Amber", "amber"
    else:  # lower_is_better
        if value > red_cut:
            return "Red", "red"
        if value <= green_cut:
            return "Green", "green"
        return "Amber", "amber"
