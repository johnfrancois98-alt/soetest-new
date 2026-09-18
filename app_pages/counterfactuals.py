import plotly.graph_objects as go
import streamlit as st

from config import BAR_CORNER_RADIUS, CHART_LAYOUT, SHOCKS, THEME
from utils import theme, summary
from utils.charts import wrap_label
from utils.filters import render_filters
from utils.model import predict, scenario_z
from utils.portfolio import latest_per_soe

theme.header(
    "FISCAL RISK",
    "Transfers & Counterfactuals",
    "Predicted government transfers to each SOE from its Altman Z-score, with 90% intervals. "
    "Test how a change in natural disaster or exchange-rate conditions — via their estimated "
    "effect on Z — flows through to transfers.",
)

if st.session_state.get("df") is None:
    st.markdown(
        '<div class="sfp-alert warn">No data loaded yet — go to the Home page and upload a file '
        'or use the example portfolio.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

df = render_filters(st.session_state.df)
df = df.dropna(subset=["Z"])
if df.empty:
    st.markdown('<div class="sfp-alert warn">No rows match the current filter.</div>', unsafe_allow_html=True)
    st.stop()

# One row per SOE — its most recent year — rather than pooling every year,
# which both double-counted SOEs and mixed years together in the charts.
df = latest_per_soe(df)
latest_year_label = df["Year"].iloc[0] if df["Year"].nunique() == 1 and df["Year"].iloc[0] else "most recent year per SOE"
st.markdown(f'<p class="sfp-hint">Showing each SOE\'s {latest_year_label} data.</p>', unsafe_allow_html=True)

# ------------------------------------------------------------------ #
# Scenario controls — delta_Z = beta * delta_X, so each slider is a direct
# change in the shock variable itself, not a multiplier on a "typical" shock.
# ------------------------------------------------------------------ #

st.markdown('<div class="sfp-card"><h3>Shock scenario</h3>', unsafe_allow_html=True)
sc1, sc2 = st.columns(2)
disaster_dx = 0.0
fx_dx = 0.0
with sc1:
    if SHOCKS["disaster"]["active"]:
        s = SHOCKS["disaster"]
        disaster_dx = st.slider(
            s["label"], s["slider_min"], s["slider_max"], 0.0, s["slider_step"],
            help=f"ΔZ = {s['coef']} × Δx — move this to set Δx (the change in the disaster index) directly.",
        )
with sc2:
    if SHOCKS["fx"]["active"]:
        s = SHOCKS["fx"]
        fx_dx = st.slider(
            s["label"], s["slider_min"], s["slider_max"], 0.0, s["slider_step"],
            help=f"ΔZ = {s['coef']} × Δx — move this to set Δx (the change in LCU per US$) directly.",
        )
st.markdown("</div>", unsafe_allow_html=True)

shock_active = disaster_dx != 0 or fx_dx != 0

# ------------------------------------------------------------------ #
# Optional GDP conversion — transfers/assets * assets/GDP = transfers/GDP
# ------------------------------------------------------------------ #

has_assets = "TotalAssets" in df.columns and df["TotalAssets"].notna().any()

st.markdown('<div class="sfp-card"><h3>Display units</h3>', unsafe_allow_html=True)
g1, g2 = st.columns([2, 1])
with g1:
    gdp_value = st.number_input(
        "Current GDP (LCU) — optional", min_value=0.0, value=0.0, step=1.0, format="%.0f",
        help="Enter GDP in the same currency/units as your uploaded TotalAssets figures.",
    )
with g2:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    gdp_mode = st.checkbox(
        "Show as % of GDP", value=False,
        disabled=not (has_assets and gdp_value > 0),
    )
if not has_assets:
    st.markdown('<p class="sfp-hint">Needs a TotalAssets figure per SOE (from a raw-financials upload) to convert to % of GDP.</p>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

gdp_mode = gdp_mode and has_assets and gdp_value > 0
unit_label = "% of GDP" if gdp_mode else "% of assets"

# ------------------------------------------------------------------ #
# Compute
# ------------------------------------------------------------------ #

work = df.copy()
preds = work["Z"].apply(predict)
work["Base"] = preds.apply(lambda t: t[0])
work["Lower"] = preds.apply(lambda t: t[1])
work["Upper"] = preds.apply(lambda t: t[2])
work["Z_scenario"] = work["Z"].apply(lambda z: scenario_z(z, disaster_dx, fx_dx))
scen_preds = work["Z_scenario"].apply(predict)
work["Scenario"] = scen_preds.apply(lambda t: t[0])

if gdp_mode:
    ratio = work["TotalAssets"] / gdp_value
    for col in ["Base", "Lower", "Upper", "Scenario"]:
        work[col] = work[col] * ratio

work["Delta"] = work["Scenario"] - work["Base"]

avg_base = work["Base"].mean()
avg_scen = work["Scenario"].mean()
avg_delta = avg_scen - avg_base
distress_n = (work["Z"] < 1.1).sum()

# ------------------------------------------------------------------ #
# Stat cards
# ------------------------------------------------------------------ #

s1, s2, s3, s4 = st.columns(4)
with s1:
    st.markdown(theme.stat_card("💰", "blue", "Avg. transfer — baseline", f"{avg_base:.2f}%", unit_label), unsafe_allow_html=True)
with s2:
    st.markdown(theme.stat_card("🎯", "gold", "Avg. transfer — scenario", f"{avg_scen:.2f}%", unit_label), unsafe_allow_html=True)
with s3:
    trend_cls = "up" if avg_delta >= 0 else "down"
    arrow = "▲" if avg_delta >= 0 else "▼"
    sign = "+" if avg_delta >= 0 else ""
    st.markdown(
        theme.stat_card(
            "📈" if avg_delta >= 0 else "📉", "red" if avg_delta >= 0 else "green",
            "Change under scenario", f"{sign}{avg_delta:.2f}pp",
            f"<b class='{trend_cls}'>{arrow} {sign}{avg_delta:.2f}</b> vs baseline",
        ),
        unsafe_allow_html=True,
    )
with s4:
    st.markdown(theme.stat_card("⚠️", "red", "SOEs in distress zone", f"{distress_n} / {len(work)}", "Z &lt; 1.1"), unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)


def _no_grid(fig, tick_font_size=None):
    fig.update_layout(**CHART_LAYOUT)
    fig.update_xaxes(showgrid=False, showline=False, tickangle=0, tickfont=dict(size=tick_font_size))
    fig.update_yaxes(showgrid=False, showline=False, title=unit_label)
    return fig


# ------------------------------------------------------------------ #
# Charts — individual SOEs and by-sector, side by side
# ------------------------------------------------------------------ #

TICK_FONT_SIZE = round(9 * 1.2, 1)  # slightly smaller than the chart's base font, to fit wrapped labels

chart_col1, chart_col2 = st.columns(2)

with chart_col1:
    title = "By SOE" + (": baseline vs scenario" if shock_active else "")
    st.markdown(f'<div class="sfp-card"><h3>{title}</h3>', unsafe_allow_html=True)

    labels = work["SOE"].apply(lambda s: wrap_label(s, 10))
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=labels, y=work["Base"].round(2), name="Baseline (90% CI)",
            marker=dict(color=THEME["chart_navy"], cornerradius=BAR_CORNER_RADIUS),
            error_y=dict(
                type="data", symmetric=False,
                array=(work["Upper"] - work["Base"]).round(2),
                arrayminus=(work["Base"] - work["Lower"]).round(2),
                color=THEME["muted"], thickness=1.2, width=3,
            ),
        )
    )
    if shock_active:
        fig.add_trace(go.Bar(x=labels, y=work["Scenario"].round(2), name="Under scenario", marker=dict(color=THEME["gold"], cornerradius=BAR_CORNER_RADIUS)))

    _no_grid(fig, TICK_FONT_SIZE)
    fig.update_layout(height=320, showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=TICK_FONT_SIZE)))
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    theme.summary_box(summary.summarize_transfer_scenario(avg_base, avg_scen, len(work), shock_active))

    export_cols = ["SOE", "Country", "Sector", "Year", "Z", "Base", "Lower", "Upper"]
    if shock_active:
        export_cols += ["Z_scenario", "Scenario", "Delta"]
    st.download_button("⬇ Download underlying data", work[export_cols].round(3).to_csv(index=False), file_name="transfer_predictions.csv")
    st.markdown("</div>", unsafe_allow_html=True)

with chart_col2:
    title2 = "By sector" + (": baseline vs scenario" if shock_active else "")
    st.markdown(f'<div class="sfp-card"><h3>{title2}</h3>', unsafe_allow_html=True)
    st.markdown('<p class="sfp-hint">Simple average across SOEs in each sector — not asset-weighted.</p>', unsafe_allow_html=True)

    by_sector = work.groupby("Sector", as_index=False)[["Base", "Scenario"]].mean().sort_values("Base")
    sector_labels = by_sector["Sector"].apply(lambda s: wrap_label(s, 10))

    fig_sector = go.Figure()
    fig_sector.add_trace(go.Bar(x=sector_labels, y=by_sector["Base"].round(2), name="Baseline", marker=dict(color=THEME["chart_navy"], cornerradius=BAR_CORNER_RADIUS)))
    if shock_active:
        fig_sector.add_trace(go.Bar(x=sector_labels, y=by_sector["Scenario"].round(2), name="Under scenario", marker=dict(color=THEME["gold"], cornerradius=BAR_CORNER_RADIUS)))
    _no_grid(fig_sector, TICK_FONT_SIZE)
    fig_sector.update_layout(height=320, showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=TICK_FONT_SIZE)))
    st.plotly_chart(fig_sector, use_container_width=True, config={"displayModeBar": False})
    st.download_button("⬇ Download underlying data", by_sector.round(3).to_csv(index=False), file_name="transfer_predictions_by_sector.csv", key="sector_dl")
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="sfp-footnote">
    <p><b>Model.</b> Transfers ({unit_label}) = 18.22 − 0.767 × Z<sub>t−1</sub>
    (robust SE 0.387, p = 0.051). Intervals are approximate 90% intervals treating the slope
    and intercept errors as independent — to be tightened once the full coefficient
    covariance matrix is available.</p>
    <p><b>Shocks.</b> ΔZ = β × Δx for each active shock — natural disaster and exchange-rate
    coefficients are from estimated bivariate regressions; terms of trade is defined in the
    tool but not active in this build.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
