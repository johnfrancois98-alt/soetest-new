import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from config import BAR_CORNER_RADIUS, CHART_LAYOUT, LINE_SHAPE, LINE_SMOOTHING, THEME, ZONE_COLORS, z_rating
from utils import theme, summary
from utils.charts import wrap_label
from utils.filters import render_filters
from utils.model import zone

theme.header(
    "FINANCIAL DISTRESS SIGNAL",
    "Altman Z-Score",
    "The four components behind the Altman EM Z-score, the score itself, and where each SOE "
    "sits in the distress / grey / safe distribution.",
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

df["Zone"] = df["Z"].apply(zone)
df["Rating"] = df["Z"].apply(z_rating)
has_years = df["Year"].astype(str).str.strip().ne("").any() and df["Year"].nunique() > 1


def _sorted_years(series):
    years = series.dropna().astype(str).unique().tolist()
    try:
        return sorted(years, key=float)
    except ValueError:
        return sorted(years)


def _mini_layout(fig, y_title=""):
    fig.update_layout(**CHART_LAYOUT)
    fig.update_xaxes(showgrid=False, showline=False, type="category")
    fig.update_yaxes(showgrid=True, gridcolor=THEME["border"], zeroline=False, title=y_title)
    return fig


COMPONENTS = [
    ("X1", "X1: Working capital-to-assets ratio"),
    ("X2", "X2: Retained earnings-to-assets ratio"),
    ("X3", "X3: EBIT-to-assets ratio"),
    ("X4", "X4: Equity-to-liabilities ratio"),
    ("Z", "Z-score"),
]

# ==================================================================== #
# Altman component matrix — one SOE at a time, over a chosen year range
# ==================================================================== #

st.markdown("#### Altman Z-score components")
soe_choice = st.selectbox("SOE", sorted(df["SOE"].unique()), key="z_matrix_soe")
d_full = df[df["SOE"] == soe_choice].sort_values("Year")

if len(d_full) < 2:
    st.markdown(
        f'<p class="sfp-hint">Only one year of data for {soe_choice} — need at least two to plot a trend.</p>',
        unsafe_allow_html=True,
    )
else:
    soe_years = _sorted_years(d_full["Year"])
    if len(soe_years) > 2:
        year_range = st.select_slider(
            "Year range", options=soe_years, value=(soe_years[0], soe_years[-1]), key="z_matrix_year_range"
        )
        lo, hi = soe_years.index(year_range[0]), soe_years.index(year_range[1])
        years_in_range = set(soe_years[lo:hi + 1])
        d = d_full[d_full["Year"].isin(years_in_range)]
    else:
        d = d_full

    def _draw_component(key, label):
        st.markdown(f'<div class="sfp-card-compact"><div class="sfp-compact-title">{label}</div>', unsafe_allow_html=True)
        dd = d.dropna(subset=[key])
        if dd.empty:
            st.markdown('<p class="sfp-kpi-desc">No data for this component.</p>', unsafe_allow_html=True)
        else:
            marker_color = THEME["gold"] if key == "Z" else THEME["chart_navy"]
            fig = go.Figure(
                go.Scatter(
                    x=dd["Year"], y=dd[key], mode="lines+markers",
                    line=dict(color=THEME["chart_navy"], width=2.2, shape=LINE_SHAPE, smoothing=LINE_SMOOTHING),
                    marker=dict(size=6, color=marker_color),
                )
            )
            if key == "Z":
                fig.add_hline(y=1.1, line_dash="dash", line_width=1.3, line_color=THEME["red"])
                fig.add_hline(y=2.6, line_dash="dash", line_width=1.3, line_color=THEME["chart_cyan"])
            _mini_layout(fig)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=f"comp_{key}")
        st.markdown("</div>", unsafe_allow_html=True)

    row1, row2 = COMPONENTS[:3], COMPONENTS[3:]

    cols1 = st.columns(3)
    for (key, label), col in zip(row1, cols1):
        with col:
            _draw_component(key, label)

    cols2 = st.columns(3)
    for (key, label), col in zip(row2, cols2[:2]):
        with col:
            _draw_component(key, label)
    with cols2[2]:
        st.markdown('<div class="sfp-card-compact">', unsafe_allow_html=True)
        theme.summary_box(summary.summarize_z_trend(d, soe_choice))
        st.download_button(
            "⬇ Download underlying data",
            d[["SOE", "Country", "Sector", "Year", "X1", "X2", "X3", "X4", "Z"]].round(3).to_csv(index=False),
            file_name=f"{soe_choice}_z_components.csv",
        )
        st.markdown("</div>", unsafe_allow_html=True)

# ==================================================================== #
# One shared period control — drives the benchmark, donut and scorecard
# below together, so they never show different years from each other.
# ==================================================================== #

st.markdown("#### Portfolio view")

if has_years:
    years = _sorted_years(df["Year"])
    view_mode = st.selectbox(
        "Period", ["Most recent year", "Specific year", "Average across years"], key="fr_view_mode"
    )
    if view_mode == "Most recent year":
        period_df = df.sort_values("Year").groupby("SOE", as_index=False).last()
        period_label = "most recent year per SOE"
    elif view_mode == "Specific year":
        year_choice = st.select_slider("Year", options=years, value=years[-1], key="fr_year_slider")
        period_df = df[df["Year"] == year_choice].copy()
        period_label = f"{year_choice}"
    else:
        sel_years = st.multiselect("Years to average", years, default=years, key="fr_avg_years")
        period_df = (
            df[df["Year"].isin(sel_years)]
            .groupby(["SOE", "Country", "Sector"], as_index=False)["Z"]
            .mean()
        )
        period_df["Year"] = "Avg"
        period_label = f"average of {', '.join(sel_years)}" if sel_years else "average (no years selected)"
else:
    period_df = df.copy()
    period_label = "all data"

period_df["Zone"] = period_df["Z"].apply(zone)
period_df["Rating"] = period_df["Z"].apply(z_rating)
period_df = period_df.sort_values("Z")

st.markdown(f'<p class="sfp-hint">Showing: <b>{period_label}</b></p>', unsafe_allow_html=True)

# -------------------------- Benchmark + donut ----------------------------- #

bc1, bc2 = st.columns([3, 2])

with bc1:
    st.markdown('<div class="sfp-card"><h3>Benchmark across SOEs</h3>', unsafe_allow_html=True)
    labels = period_df["SOE"].apply(lambda s: wrap_label(s, 10))
    fig2 = go.Figure(go.Bar(x=labels, y=period_df["Z"], marker=dict(color=period_df["Zone"].map(ZONE_COLORS), cornerradius=BAR_CORNER_RADIUS)))
    fig2.add_hline(y=1.1, line_dash="dash", line_width=1.5, line_color=THEME["red"])
    fig2.add_hline(y=2.6, line_dash="dash", line_width=1.5, line_color=THEME["chart_navy"])
    _mini_layout(fig2, "Z-score")
    fig2.update_xaxes(tickangle=0)
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    st.download_button("⬇ Data", period_df.to_csv(index=False), file_name="altman_z_benchmark.csv", key="bench_download")
    st.markdown("</div>", unsafe_allow_html=True)

with bc2:
    st.markdown('<div class="sfp-card"><h3>Portfolio distribution</h3>', unsafe_allow_html=True)
    counts = period_df["Zone"].value_counts()
    fig3 = go.Figure(
        go.Pie(
            labels=counts.index, values=counts.values,
            marker=dict(colors=[ZONE_COLORS[z] for z in counts.index]),
            hole=0.55, textinfo="percent",
        )
    )
    fig3.update_layout(**{**CHART_LAYOUT, "showlegend": True})
    fig3.update_layout(legend=dict(orientation="h", y=-0.1, x=0, font=dict(size=round(10 * 1.2, 1))))
    st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
    theme.summary_box(summary.summarize_zone_distribution(period_df))
    st.download_button(
        "⬇ Data", counts.rename("Count").to_csv(), file_name="zone_distribution.csv", key="zone_dist_download",
    )
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------- Scorecard ------------------------------- #

st.markdown('<div class="sfp-card"><h3>Scorecard</h3>', unsafe_allow_html=True)
rows_html = []
for _, r in period_df.iterrows():
    color = ZONE_COLORS[r["Zone"]]
    rows_html.append(
        f"<tr><td>{r['SOE']}</td><td>{r['Country']}</td><td>{r['Sector']}</td>"
        f"<td>{r['Year'] or '—'}</td><td>{r['Z']:.2f}</td>"
        f"<td><span class='sfp-dot' style='background:{color}'></span>{r['Zone']}</td>"
        f"<td>{r['Rating']}</td></tr>"
    )
st.markdown(
    "<table class='sfp-table'><thead><tr><th>SOE</th><th>Country</th><th>Sector</th>"
    f"<th>Year</th><th>Z</th><th>Zone</th><th>Rating</th></tr></thead><tbody>{''.join(rows_html)}</tbody></table>",
    unsafe_allow_html=True,
)
st.download_button("⬇ Download underlying data", period_df.to_csv(index=False), file_name="altman_z_scorecard.csv")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    """
    <div class="sfp-footnote">
    <p><b>Z-score.</b> Altman Z''-EM (Eidelman, 1995): Z = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4.
    Z &lt; 1.1 = distress, 1.1–2.6 = grey zone, &gt; 2.6 = safe. Rating is an indicative credit-rating
    cohort mapping for the Z-score, for reference only.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
