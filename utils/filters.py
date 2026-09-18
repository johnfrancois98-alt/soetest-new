"""
Top-bar filters. Same widget keys on every page keep the selection in sync
as you move between pages (Streamlit's session_state persists it).
"""

import streamlit as st

from config import fs


def render_filters(df):
    """Renders a compact Country / Sector filter row and returns the filtered df."""
    st.markdown('<div class="sfp-topbar">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2.2, 2.2, 1.6])

    countries = sorted(df["Country"].dropna().unique().tolist())
    with c1:
        sel_countries = st.multiselect("Country", countries, default=countries, key="sel_countries")

    scoped = df[df["Country"].isin(sel_countries)] if sel_countries else df.iloc[0:0]

    sectors = sorted(scoped["Sector"].dropna().unique().tolist())
    with c2:
        sel_sectors = st.multiselect("Sector", sectors, default=sectors, key="sel_sectors")

    scoped = scoped[scoped["Sector"].isin(sel_sectors)] if sel_sectors else scoped.iloc[0:0]

    with c3:
        years = scoped["Year"].astype(str).replace("", None).dropna().unique().tolist()
        year_label = "—"
        if years:
            try:
                years_sorted = sorted(years, key=lambda y: float(y))
                year_label = f"{years_sorted[0]}–{years_sorted[-1]}" if len(years_sorted) > 1 else years_sorted[0]
            except ValueError:
                year_label = ", ".join(sorted(years)[:2])
        st.markdown(
            f'<div class="sfp-hint" style="margin-top:28px;">Data as of<br><b style="color:#151B2B;font-size:{fs(14)};">{year_label}</b></div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
    return scoped
