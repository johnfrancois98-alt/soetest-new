"""
Central configuration for the SOE Fiscal Risk Tool.

Everything you are likely to want to tune later — regression coefficients,
KPI thresholds, shock parameters, zone cutoffs, colors — lives here so the
page code never needs to change when the numbers do.

KPI thresholds and formulas follow the IMF Fiscal Affairs Department's
"SOE Health Check Tool" User Guide (Halstead, Marrison, Ryan & Sayegh,
Nov 2021), Figures A2.4–A2.5 and Annex III — reduced here to a 3-tier
red/amber/green (using the guide's Category 1/2 boundary as the green cut
and its Category 4/5 boundary as the red cut, rather than its full 5-tier
scale). Swap in the full 5-tier scale later if you want that granularity.
"""

# ------------------------------------------------------------------ #
# Main model: transfers-to-SOE (grants/assets, % of assets) ~ Z_{t-1}
# ------------------------------------------------------------------ #
# Fiscal injections = B0 + B1 * Z_{t-1}
MAIN_MODEL = {
    "b0": 18.21999,
    "se_b0": 4.817782,
    "b1": -0.7666951,
    "se_b1": 0.3868693,
}

# Two-sided critical value used to build the prediction interval.
# 1.645 = asymptotic 90% (normal approximation, since df is unknown for the
# robust regression). Swap for a t-critical value once you give me N/df,
# or replace the whole CI construction in utils/model.py once you have the
# full coefficient covariance matrix.
CI_LEVEL = 0.90
Z_CRIT = 1.645

# ------------------------------------------------------------------ #
# Shock -> Altman Z bivariate regressions
# ------------------------------------------------------------------ #
# The underlying model is delta_Z = beta * delta_X — a direct linear effect
# of a change in the shock variable on Z, not a multiplier on some assumed
# "typical" shock size. Each slider on the Counterfactuals page lets the
# user set delta_X directly, in the shock's own units; slider_min/slider_max
# below are that range. "active": False hides a shock from the
# counterfactual page without deleting its numbers.
SHOCKS = {
    "disaster": {
        "label": "Natural disaster shock (Δx)",
        "coef": -0.235,
        "se": None,       # fill in once you have the full regression output
        "kind": "continuous",
        "slider_min": 0.0,
        "slider_max": 10.0,
        "slider_step": 0.5,
        "active": True,
    },
    "fx": {
        "label": "Exchange rate shock (Δx, LCU per US$)",
        "coef": -0.406,
        "se": None,
        "kind": "continuous",
        "slider_min": -10.0,
        "slider_max": 10.0,
        "slider_step": 0.5,
        "active": True,
    },
    "tot": {
        "label": "Terms of trade shock (Δx)",
        "coef": 0.045,
        "se": None,
        "kind": "continuous",
        "slider_min": -10.0,
        "slider_max": 10.0,
        "slider_step": 0.5,
        "active": False,  # parked for now per current scope; flip on later
    },
}

# ------------------------------------------------------------------ #
# Altman Z zone cutoffs (Z'' EM convention, Eidelman 1995)
# ------------------------------------------------------------------ #
Z_DISTRESS_CUTOFF = 1.1   # Z below this  -> Distress (red)
Z_SAFE_CUTOFF = 2.6       # Z above this  -> Safe (green); between -> Grey (amber)

# Z_DISTRESS_CUTOFF / Z_SAFE_CUTOFF define the zone boundaries; the colors
# used to draw them (ZONE_COLORS / ZONE_STYLE) are defined further down,
# next to the rest of the chart palette.

# Z''-score credit-rating cohort mapping (Altman EM model), highest to
# lowest. Used as an extra "Rating" column alongside the Distress/Grey/Safe
# zone — purely descriptive, not used in any calculation.
Z_RATING_TABLE = [
    (4.90, "AAA"),
    (4.35, "AA+"),
    (4.05, "AA"),
    (3.75, "AA-"),
    (3.60, "A+"),
    (3.40, "A"),
    (3.15, "A-"),
    (3.00, "BBB+"),
    (2.60, "BBB"),
    (2.40, "BBB-"),
    (2.00, "BB+"),
    (1.70, "BB"),
    (1.50, "BB-"),
    (1.25, "B+"),
    (0.90, "B"),
    (0.50, "B-"),
    (-0.05, "CCC+"),
    (-0.75, "CCC"),
    (-1.50, "CCC-"),
]
Z_RATING_BELOW = "D"  # anything below the lowest table entry


def z_rating(z):
    if z is None:
        return None
    for lower, label in Z_RATING_TABLE:
        if z >= lower:
            return label
    return Z_RATING_BELOW


# ------------------------------------------------------------------ #
# KPI categories, thresholds, formulas, and plain-language descriptions
# ------------------------------------------------------------------ #
# direction: "higher_is_better" or "lower_is_better" — controls which side
# of the cutoffs counts as red/green.
# red_cut / green_cut: for higher_is_better, values below red_cut are red,
# at/above green_cut are green, in between are amber. For lower_is_better
# it's reversed. Sourced from IMF SOE-HCT Figure A2.5 where the guide gives
# an explicit threshold; a few ratios (net profit margin, operating margin)
# aren't in that table, so those two keep provisional placeholder cuts —
# flagged below.
# requires: standardized raw-field keys (see ALIASES) needed to compute it.
KPI_CATEGORIES = {
    "profitability": ["net_profit_margin", "operating_profit_margin", "roa", "roe", "cost_recovery"],
    "liquidity": ["current_ratio"],
    "solvency": [
        "debt_to_assets", "debt_to_equity", "debt_to_ebitda",
        "interest_coverage", "cash_interest_coverage", "government_transfers_to_revenue",
    ],
}
CATEGORY_LABELS = {"profitability": "Profitability", "liquidity": "Liquidity", "solvency": "Solvency"}

KPI_THRESHOLDS = {
    "net_profit_margin": {
        "label": "Net profit margin",
        "direction": "higher_is_better",
        "red_cut": 0.0,
        "green_cut": 0.10,
        "unit": "%",
        "requires": ["net_income", "revenue"],
        "description": (
            "Share of each unit of revenue that ends up as profit. Positive means the entity is "
            "profitable — the higher, the more profitable and the better costs are contained. "
            "(Threshold not in the IMF guide's indicative table; placeholder pending sector benchmarks.)"
        ),
    },
    "operating_profit_margin": {
        "label": "Operating profit margin",
        "direction": "higher_is_better",
        "red_cut": 0.0,
        "green_cut": 0.10,
        "unit": "%",
        "requires": ["ebit", "revenue"],
        "description": (
            "Share of revenue left as operating profit, before financing costs and tax. Should be "
            "positive; the higher, the stronger the entity's core operations. "
            "(Threshold not in the IMF guide's indicative table; placeholder pending sector benchmarks.)"
        ),
    },
    "roa": {
        "label": "Return on assets (ROA)",
        "direction": "higher_is_better",
        "red_cut": -0.10,
        "green_cut": 0.10,
        "unit": "%",
        "requires": ["net_income", "total_assets"],
        "description": "How efficiently the entity uses its assets to generate profit. Higher is better.",
    },
    "roe": {
        "label": "Return on equity (ROE)",
        "direction": "higher_is_better",
        "red_cut": -0.10,
        "green_cut": 0.20,
        "unit": "%",
        "requires": ["net_income", "total_equity"],
        "description": (
            "Return generated on the government's equity stake. Ideally exceeds what that capital "
            "could earn elsewhere; persistently negative ROE erodes equity over time."
        ),
    },
    "cost_recovery": {
        "label": "Cost recovery",
        "direction": "higher_is_better",
        "red_cut": 0.8,
        "green_cut": 1.5,
        "unit": "x",
        "requires": ["revenue", "operating_expense"],
        "description": (
            "Whether the entity earns enough revenue to cover its operating costs. Below 1 means it "
            "isn't breaking even at the operating level."
        ),
    },
    "current_ratio": {
        "label": "Current ratio",
        "direction": "higher_is_better",
        "red_cut": 1.0,
        "green_cut": 2.0,
        "unit": "x",
        "requires": ["current_assets", "current_liabilities"],
        "description": (
            "Ability to cover short-term liabilities with short-term assets. Below 1 means the entity "
            "can't meet obligations due in the next year from assets convertible to cash that soon."
        ),
    },
    "debt_to_assets": {
        "label": "Debt to assets",
        "direction": "lower_is_better",
        "red_cut": 1.0,
        "green_cut": 0.3,
        "unit": "%",
        "requires": ["total_liabilities", "total_assets"],
        "description": (
            "Share of financing that comes from liabilities rather than equity. Above 1 means "
            "liabilities exceed assets — technically insolvent."
        ),
    },
    "debt_to_equity": {
        "label": "Debt to equity",
        "direction": "lower_is_better",
        "red_cut": 2.0,
        "green_cut": 0.5,
        "unit": "x",
        "requires": ["total_liabilities", "total_equity"],
        "description": "Liabilities relative to equity financing. Lower usually means a more stable capital structure.",
    },
    "debt_to_ebitda": {
        "label": "Debt to EBITDA",
        "direction": "lower_is_better",
        "red_cut": 5.0,
        "green_cut": 1.5,
        "unit": "x",
        "requires": ["total_liabilities", "ebitda"],
        "description": (
            "Years of current cash generation it would take to pay off all liabilities. Higher means "
            "more indebted and less able to service that debt."
        ),
    },
    "interest_coverage": {
        "label": "Interest coverage",
        "direction": "higher_is_better",
        "red_cut": 1.0,
        "green_cut": 2.0,
        "unit": "x",
        "requires": ["ebit", "interest_expense"],
        "description": (
            "Whether operating profit covers financing costs. Below 1 means the entity can't meet its "
            "interest payments and stay profitable."
        ),
    },
    "cash_interest_coverage": {
        "label": "Cash interest coverage",
        "direction": "higher_is_better",
        "red_cut": 1.0,
        "green_cut": 3.0,
        "unit": "x",
        "requires": ["ebitda", "interest_expense"],
        "description": (
            "Cash generated from operations relative to interest expense. Below 1 means the entity "
            "would need to borrow just to cover interest payments."
        ),
    },
    "government_transfers_to_revenue": {
        "label": "Government transfers / revenue",
        "direction": "lower_is_better",
        "red_cut": 0.6,
        "green_cut": 0.3,
        "unit": "%",
        "requires": ["government_grants", "revenue"],
        "description": (
            "How dependent the entity is on government transfers as a share of total revenue. Higher "
            "means more exposure if that support were reduced."
        ),
    },
}

# ------------------------------------------------------------------ #
# Column aliases for auto-detection (see utils/data_io.py)
# ------------------------------------------------------------------ #
# Standardized field name -> list of normalized (lowercase, no punctuation)
# header variants it should match. Covers both a pre-computed Z/ratio file
# and a raw financial-statement file like the IMF SOE-HCT input form.
ALIASES = {
    "soe": ["soe", "entity", "company", "name", "firm"],
    "country": ["country", "nation"],
    "sector": ["sector", "industry"],
    "year": ["year", "yr", "fy", "fiscalyear"],
    "z": ["z", "altmanz", "zscore", "altman_z", "zem", "zscoreem", "z2", "zdoubleprime"],
    "x1": ["x1", "wcta", "workingcapitaltotalassets", "wc_ta"],
    "x2": ["x2", "reta", "retainedearningstotalassets", "re_ta"],
    "x3": ["x3", "ebitta", "ebittotalassets", "ebit_ta"],
    "x4": ["x4", "bvetl", "bookequitytotalliabilities", "equityliabilities", "bve_tl"],
    # Balance sheet
    "current_assets": ["currentassets", "ca"],
    "current_liabilities": ["currentliabilities", "cl"],
    "total_assets": ["totalassets", "ta", "assets"],
    "total_liabilities": ["totalliabilities", "liabilities", "tl"],
    "total_equity": ["totalequity", "equity", "bookequity", "te"],
    "retained_earnings": ["retainedearnings", "re"],
    # Income statement
    "revenue": ["revenue", "revenues", "sales", "totalrevenue", "revenuefromtradingactivities"],
    "total_expense": ["totalexpense", "totalexpenses"],
    "operating_expense": ["operatingexpense", "operatingexpenses"],
    "net_income": ["netincome", "ni", "profit", "netprofit", "netprofitaftertax"],
    "interest_expense": ["interestexpense", "financecosts", "financecost"],
    "tax_expense": ["taxexpense", "incometaxexpense"],
    "ebit": ["ebit", "operatingincome"],
    "ebitda": ["ebitda"],
    "depreciation": ["depreciation", "depreciationandamortization", "da"],
    "government_grants": ["governmentgrants", "governmentgrantsreceived", "govttransfers", "govtgrants"],
}

# ------------------------------------------------------------------ #
# Font scale
# ------------------------------------------------------------------ #
# Every font size in the app — the custom UI (theme.py) and the chart text
# (CHART_LAYOUT below) — is multiplied by this. Change it here once and
# everything scales together; nothing else needs editing.
FONT_SCALE = 1.2
BASE_ROOT_PX = 16  # Streamlit's own default root size, for native widgets


def fs(px):
    """Scale a base pixel size by FONT_SCALE, e.g. fs(12) -> '14.4px'."""
    return f"{round(px * FONT_SCALE, 1)}px"


# ------------------------------------------------------------------ #
# Theme
# ------------------------------------------------------------------ #
# Light dashboard palette with a dark navy sidebar, in the spirit of the
# reference mockup. Change any value here and every page picks it up.
THEME = {
    # Sidebar
    "sidebar_bg": "#0B2340",
    "sidebar_bg_active": "#173A63",
    "sidebar_text": "#AEBDD1",
    "sidebar_text_active": "#FFFFFF",
    # Page
    "bg": "#F3F5F9",
    "card": "#FFFFFF",
    "border": "#E6E9F0",
    "text": "#151B2B",
    "muted": "#69738A",
    # Accent / semantic colors
    "blue": "#2F6FE4",
    "blue_bg": "#E9EFFD",
    "gold": "#E8A33D",
    "gold_bg": "#FCF2E1",
    "green": "#2AA876",
    "green_bg": "#E6F6EE",
    "amber": "#F0A93A",
    "amber_bg": "#FDF1DD",
    "red": "#E5484D",
    "red_bg": "#FCEAE9",
    "purple": "#7A5FD1",
    "purple_bg": "#EFEAFB",
    # Chart palette — dark navy + sky-blue + gold + red, per the reference charts
    "chart_navy": "#12294A",
    "chart_navy_bg": "#E7EAF2",
    "chart_cyan": "#29ABE2",
    "chart_cyan_bg": "#E3F4FC",
    # Kept for backward compatibility with earlier page code
    "navy": "#12294A",
    "navy_light": "#2F6FE4",
    "gold_deep": "#C97F1E",
    "teal": "#2AA876",
    "coral": "#E5484D",
    "paper": "#F3F5F9",
    "line": "#E6E9F0",
}

# Risk-zone -> chart color + chip color, matching the reference charts
# (distress = red, grey/vulnerable = sky-blue, safe = dark navy).
ZONE_COLORS = {
    "Distress": THEME["red"],
    "Grey zone": THEME["chart_cyan"],
    "Safe": THEME["chart_navy"],
}
ZONE_STYLE = {
    "Distress": {"color": THEME["red"], "bg": THEME["red_bg"]},
    "Grey zone": {"color": THEME["chart_cyan"], "bg": THEME["chart_cyan_bg"]},
    "Safe": {"color": THEME["chart_navy"], "bg": THEME["chart_navy_bg"]},
}

# Shared Plotly layout so every small chart looks the same: minimal gridlines,
# narrower bars (via bargap), compact height. Import and spread into
# fig.update_layout(**CHART_LAYOUT) / bar traces use BAR_STYLE.
CHART_HEIGHT = 165
CHART_LAYOUT = dict(
    height=CHART_HEIGHT,
    margin=dict(l=6, r=6, t=6, b=6),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Segoe UI, sans-serif", size=round(11 * FONT_SCALE, 1), color=THEME["text"]),
    bargap=0.45,
    bargroupgap=0.15,
    showlegend=False,
)

# Rounded bar corners and smoothed (spline) lines, used everywhere a chart
# draws a bar or a connecting line — the shared "smoother, less boxy" look.
BAR_CORNER_RADIUS = 6
LINE_SHAPE = "spline"
LINE_SMOOTHING = 0.4  # 0 = straight segments, 1 = maximally smoothed
