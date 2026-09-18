import streamlit as st

from utils import theme

st.set_page_config(page_title="SOE Fiscal Risk Tool", layout="wide", page_icon="🏛️")
theme.inject()
theme.sidebar_footer()

home_page = st.Page("app_pages/home.py", title="Home", icon="🏠", default=True)
performance_page = st.Page("app_pages/performance.py", title="Performance", icon="📊")
fiscal_risk_page = st.Page("app_pages/fiscal_risk.py", title="Fiscal Risk", icon="📉")
counterfactuals_page = st.Page("app_pages/counterfactuals.py", title="Counterfactuals", icon="💸")

pg = st.navigation([home_page, performance_page, fiscal_risk_page, counterfactuals_page])
pg.run()
