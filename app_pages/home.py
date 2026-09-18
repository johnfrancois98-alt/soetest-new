import pandas as pd
import streamlit as st

from utils import theme, data_io
from utils.portfolio import latest_per_soe

theme.header(
    "PACIFIC SOE FISCAL RISK",
    "SOE Fiscal Risk Dashboard",
    "A three-layer framework for state-owned enterprises: financial performance (Performance "
    "page), fiscal risk (Altman Z-score, on the Fiscal Risk page), and counterfactual shock "
    "scenarios linking external shocks to Z, and Z to expected government transfers "
    "(Counterfactuals page).",
)

if "df" not in st.session_state:
    st.session_state.df = None
    st.session_state.using_sample = False

# ------------------------------------------------------------------ #
# Overview stat row — right up top, since it's a welcoming summary
# ------------------------------------------------------------------ #

if st.session_state.df is not None:
    valid = st.session_state.df.dropna(subset=["Z"])
    d = latest_per_soe(valid)  # one row per SOE, not one row per SOE-year
    n_soes = d["SOE"].nunique()
    n_countries = d["Country"].nunique()
    distress_n = int((d["Z"] < 1.1).sum())
    avg_z = d["Z"].mean() if n_soes else float("nan")

    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(
            theme.stat_card("🏛️", "blue", "Total SOEs", n_soes, f"Across {n_countries} countr{'y' if n_countries==1 else 'ies'}"),
            unsafe_allow_html=True,
        )
    with s2:
        st.markdown(theme.stat_card("📊", "purple", "Average Z-score", f"{avg_z:.2f}", "Portfolio-wide, latest data"), unsafe_allow_html=True)
    with s3:
        pct = (distress_n / n_soes * 100) if n_soes else 0
        st.markdown(
            theme.stat_card("⚠️", "red", "SOEs in distress", f"{distress_n} / {n_soes}", f"{pct:.0f}% of portfolio (Z &lt; 1.1)"),
            unsafe_allow_html=True,
        )
    with s4:
        st.markdown(theme.stat_card("🌍", "green", "Coverage", "Multi-country", "Filter by country on any page"), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# About
# ------------------------------------------------------------------ #

with st.expander("About this tool", expanded=st.session_state.df is None):
    st.markdown(
        """
**How it works**

1. **Upload** — a portfolio of SOEs, one row per SOE-year. Either a Z-score (or the four
   Altman EM components) directly, **or** raw financial statement fields — the tool computes
   the components, Z, and every KPI ratio itself from the raw numbers.
2. **Performance** — profitability, liquidity and solvency ratios (IMF SOE Health Check Tool
   thresholds), compared across SOEs and tracked over time for one SOE at a time.
3. **Fiscal Risk** — the four Altman components and the Z-score itself, cross-SOE
   benchmarking, and a distress/grey/safe distribution with an indicative credit-rating cohort.
4. **Counterfactuals** — predicted government transfers to each SOE from its Z-score, with
   sliders to test natural disaster and exchange rate shocks.

Every chart in the tool can export its underlying data, and comes with an automated
plain-language summary generated directly from the numbers on screen (not a live AI call).

**Scope.** v1. Coefficients and thresholds are provisional and will be refined as fuller
regression results and country data come in.
        """
    )

# ------------------------------------------------------------------ #
# Data upload — label/description and the dropzone side by side
# ------------------------------------------------------------------ #

st.markdown('<div class="sfp-card">', unsafe_allow_html=True)
up_label, up_widget = st.columns([1, 2])
with up_label:
    st.markdown(
        '<h3 style="margin-bottom:6px;">Upload your data</h3>'
        '<p class="sfp-hint">CSV or Excel, one row per SOE-year.</p>',
        unsafe_allow_html=True,
    )
with up_widget:
    uploaded = st.file_uploader("Drop a CSV or Excel file", type=["csv", "xlsx", "xls"], label_visibility="collapsed")

if uploaded is not None:
    try:
        raw = pd.read_csv(uploaded) if uploaded.name.lower().endswith(".csv") else pd.read_excel(uploaded)
        df, error, note = data_io.build_dataframe(raw)
        if error:
            st.markdown(f'<div class="sfp-alert warn">{error}</div>', unsafe_allow_html=True)
        else:
            st.session_state.df = df
            st.session_state.using_sample = False
            st.markdown(f'<div class="sfp-alert ok">✓ {note}</div>', unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f'<div class="sfp-alert warn">Couldn\'t read that file: {e}</div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# Try it with example data
# ------------------------------------------------------------------ #

st.markdown('<div class="sfp-card"><h3>Try it with example data</h3>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    if st.button("Use example: pre-computed Z"):
        raw = pd.DataFrame(
            [
                {"SOE": "Islands Power Authority", "Country": "Fiji", "Sector": "Energy", "Year": 2023, "Z": 1.9},
                {"SOE": "Islands Power Authority", "Country": "Fiji", "Sector": "Energy", "Year": 2024, "Z": 1.3},
                {"SOE": "Islands Power Authority", "Country": "Fiji", "Sector": "Energy", "Year": 2025, "Z": 0.8},
                {"SOE": "Pacific Water Board", "Country": "Tonga", "Sector": "Water", "Year": 2024, "Z": 1.9},
                {"SOE": "Pacific Water Board", "Country": "Tonga", "Sector": "Water", "Year": 2025, "Z": 1.6},
                {"SOE": "National Airways Ltd", "Country": "Samoa", "Sector": "Transport", "Year": 2024, "Z": 0.1},
                {"SOE": "National Airways Ltd", "Country": "Samoa", "Sector": "Transport", "Year": 2025, "Z": -0.4},
                {"SOE": "Ports & Harbours Corp", "Country": "Fiji", "Sector": "Transport", "Year": 2025, "Z": 2.9},
                {"SOE": "Telecom Pasifika", "Country": "Vanuatu", "Sector": "Telecom", "Year": 2025, "Z": 3.4},
                {"SOE": "Fisheries Development Corp", "Country": "Kiribati", "Sector": "Fisheries", "Year": 2025, "Z": 1.1},
            ]
        )
        df, error, note = data_io.build_dataframe(raw)
        st.session_state.df = df
        st.session_state.using_sample = True
        st.rerun()
    st.caption("Ten Pacific SOEs, Z already supplied — no Performance-page ratios.")
with c2:
    if st.button("Use example: raw financials"):
        df, error, note = data_io.build_dataframe(data_io.SAMPLE_RAW_FINANCIALS)
        st.session_state.df = df
        st.session_state.using_sample = True
        st.rerun()
    st.caption("Seven SOEs across five sectors, up to 5 years of full statements — Z and every ratio computed live.")
st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# Templates
# ------------------------------------------------------------------ #

st.markdown('<div class="sfp-card"><h3>Templates</h3>', unsafe_allow_html=True)
t1, t2 = st.columns(2)
with t1:
    st.download_button("Template: pre-computed Z", data_io.TEMPLATE_CSV, file_name="soe_tool_template.csv")
with t2:
    st.download_button("Template: raw financials", data_io.TEMPLATE_RAW_CSV, file_name="soe_tool_template_raw.csv")

st.markdown(
    '<p class="sfp-hint">Required: <b>SOE</b>, plus one of — a <b>Z</b> column; all four Altman '
    "components (<b>X1</b> working capital/assets, <b>X2</b> retained earnings/assets, "
    "<b>X3</b> EBIT/assets, <b>X4</b> equity/liabilities); or enough raw financial statement fields "
    "(<b>CurrentAssets</b>, <b>CurrentLiabilities</b>, <b>TotalAssets</b>, <b>TotalLiabilities</b>, "
    "<b>Equity</b>, <b>RetainedEarnings</b>, <b>Revenue</b>, and either <b>EBIT</b> or "
    "<b>EBITDA</b>+<b>Depreciation</b>) for the tool to compute Z itself. Recommended: "
    "<b>Country</b>, <b>Sector</b>, <b>Year</b> (needed for time trends). Extra raw fields "
    "(<b>OperatingExpense</b>, <b>InterestExpense</b>, <b>GovernmentGrants</b>, etc.) unlock more "
    "Performance-page ratios — missing ones simply don't appear.</p>",
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# Data preview — collapsed until the user asks for it
# ------------------------------------------------------------------ #

if st.session_state.df is None:
    st.markdown(
        '<div class="sfp-alert info">No data loaded yet. Upload a file above, or try one of the '
        "example portfolios.</div>",
        unsafe_allow_html=True,
    )
else:
    if st.session_state.using_sample:
        st.markdown(
            '<div class="sfp-alert info">Showing example data. Upload your own file above to replace it.</div>',
            unsafe_allow_html=True,
        )
    with st.expander("Data preview"):
        st.dataframe(st.session_state.df, use_container_width=True, height=240)
    st.markdown(
        '<p class="sfp-hint">Use the pages in the left sidebar — Performance, Fiscal Risk, '
        "Counterfactuals — to explore this data.</p>",
        unsafe_allow_html=True,
    )
