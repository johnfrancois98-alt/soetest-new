"""
Automated, rules-based summaries for charts across the tool. These read
the already-computed numbers and fill in a sentence template — no model
call, no cost, and every figure quoted is guaranteed to match the chart.
"""

import pandas as pd

from utils.model import zone


def summarize_zone_distribution(df: pd.DataFrame) -> str:
    if df.empty:
        return "No data available for this selection."
    zones = df["Z"].apply(zone)
    counts = zones.value_counts()
    n = len(df)
    distress = counts.get("Distress", 0)
    grey = counts.get("Grey zone", 0)
    safe = counts.get("Safe", 0)

    parts = [f"{distress} of {n} SOEs are in the distress zone (Z < 1.1)"]
    if grey:
        parts.append(f"{grey} in the grey zone")
    if safe:
        parts.append(f"{safe} in the safe zone")
    sentence = ", ".join(parts) + "."

    if distress > 0:
        worst_sectors = (
            df.loc[zones == "Distress", "Sector"]
            .value_counts()
            .head(2)
            .index.tolist()
        )
        if worst_sectors:
            sentence += f" Distress is concentrated in {', '.join(worst_sectors)}."
    return sentence


def summarize_z_trend(df_soe: pd.DataFrame, soe_name: str) -> str:
    d = df_soe.dropna(subset=["Z"]).sort_values("Year")
    if len(d) < 2:
        return f"Not enough time points to describe a trend for {soe_name}."
    first, last = d["Z"].iloc[0], d["Z"].iloc[-1]
    change = last - first
    direction = "improved" if change > 0 else "declined" if change < 0 else "held steady"
    return (
        f"{soe_name}'s Z-score {direction} from {first:.2f} in {d['Year'].iloc[0]} "
        f"to {last:.2f} in {d['Year'].iloc[-1]}, ending in the {zone(last).lower()} zone."
    )


def summarize_kpi_flags(df: pd.DataFrame, kpi_key: str, kpi_label: str, flags: pd.Series) -> str:
    n = len(flags)
    red = int((flags == "Red").sum())
    green = int((flags == "Green").sum())
    if n == 0:
        return f"No data available to assess {kpi_label}."
    return (
        f"{red} of {n} SOEs are flagged red on {kpi_label}, "
        f"{green} are green."
    )


def summarize_transfer_scenario(portfolio_baseline, portfolio_scenario, n_soes, shock_active) -> str:
    if not shock_active:
        return (
            f"Baseline prediction: average transfers of {portfolio_baseline:.2f}% of assets "
            f"across {n_soes} SOEs."
        )
    delta = portfolio_scenario - portfolio_baseline
    direction = "increases" if delta > 0 else "decreases"
    return (
        f"Under the selected scenario, average predicted transfers {direction} from "
        f"{portfolio_baseline:.2f}% to {portfolio_scenario:.2f}% of assets "
        f"({delta:+.2f} percentage points) across {n_soes} SOEs."
    )
