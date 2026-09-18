# SOE Fiscal Risk Tool

Multi-page Python/Streamlit tool for SOEs: performance ratios (IMF SOE
Health Check Tool thresholds), Altman Z-score analysis, and transfers-to-SOE
prediction with disaster/exchange-rate counterfactuals. Accepts either a
pre-computed Z-score or raw financial statements — the tool computes the
Altman components, Z, and every ratio itself from the raw numbers.

## Structure

```
soe_fiscal_tool/
├── Home.py                          Entry point — page config, shared
│                                     chrome, routes to the pages below
├── config.py                        ALL tunable numbers live here
├── assets/
│   └── logo.png                     sidebar wordmark (used via st.logo)
├── utils/
│   ├── data_io.py                   column detection, raw-financials
│   │                                parsing, Altman component/Z computation
│   ├── model.py                     Z prediction, CI, scenario math
│   ├── kpis.py                      KPI ratio calcs + red/amber/green
│   ├── summary.py                   rules-based plain-language summaries
│   ├── filters.py                   shared top-bar country/sector filters
│   └── theme.py                     shared CSS, color palette, stat cards
├── app_pages/
│   ├── home.py                      About + data upload
│   ├── performance.py               Profitability/Liquidity/Solvency —
│   │                                3-column layout, dropdown per column
│   ├── fiscal_risk.py               Altman component matrix (X1–X4 + Z),
│   │                                scorecard with rating, benchmark, donut
│   └── counterfactuals.py           Shock sliders, transfers prediction
└── requirements.txt
```

`Home.py` is what you run (`streamlit run Home.py`). It registers each page
via `st.Page(...)` with its sidebar icon passed as a plain parameter — page
files stay ordinary ASCII filenames, nothing depends on an emoji surviving
a zip download or a Windows filesystem.

## Where to make changes later

Almost everything you're likely to want to tune lives in **`config.py`**:

- `MAIN_MODEL` — the transfer-prediction regression coefficients/SEs
- `SHOCKS` — disaster/exchange-rate/terms-of-trade coefficients, each a
  slider. Each has an `"active": True/False` flag — flip terms of trade on
  later without touching any page code
- `KPI_THRESHOLDS` — red/amber/green cutoffs, formulas' required raw
  fields, and the plain-language description shown under each chart, for
  every ratio. Sourced from the IMF SOE-HCT User Guide (Figure A2.5) where
  it gives an explicit threshold; `net_profit_margin` and
  `operating_profit_margin` don't have one in that guide, so they carry a
  placeholder — flagged in their own `description` text
- `KPI_CATEGORIES` — which ratios show up under Profitability / Liquidity
  / Solvency on the Performance page
- `Z_DISTRESS_CUTOFF` / `Z_SAFE_CUTOFF` — Altman Z zone boundaries
- `Z_RATING_TABLE` — the Z-score credit-rating cohort mapping (AAA…D)
- `THEME` — the color palette (navy / sky-blue / gold / red)
- `ZONE_COLORS` / `ZONE_STYLE` — which color each Z zone uses on charts
- `CHART_LAYOUT` / `CHART_HEIGHT` — the shared compact chart sizing every
  chart in the tool uses
- `FONT_SCALE` — multiplies every font size in the app (custom UI and
  native Streamlit widgets alike) from one place
- `ALIASES` — column names the upload parser recognizes, for both a
  pre-computed file and a raw financial-statement file

If you want the CI construction itself to change (e.g. once you have the
full coefficient covariance matrix), that's the `predict()` function in
`utils/model.py`.

The 3-tier red/amber/green currently used collapses the IMF guide's full
5-category scale (Category 1–5) down to one boundary each side — the
guide's Category 1/2 boundary as the green cut, Category 4/5 as the red
cut. Swap in the full 5-tier scale later in `KPI_THRESHOLDS` /
`utils/kpis.classify()` if you want that granularity back.

## Run it locally

```bash
cd soe_fiscal_tool
pip install -r requirements.txt
streamlit run Home.py
```

Opens at `http://localhost:8501`.

## Publish it

Push this folder to a GitHub repo, then deploy free on
[share.streamlit.io](https://share.streamlit.io) with the main file set to
`Home.py`. You get a shareable URL that redeploys on every push.

## Data format

**Required:** `SOE`, plus one of:
- a `Z` column, or
- all four Altman components (`X1` working capital/assets, `X2` retained
  earnings/assets, `X3` EBIT/assets, `X4` equity/liabilities), or
- enough raw financial statement fields for the tool to compute Z itself:
  `CurrentAssets`, `CurrentLiabilities`, `TotalAssets`, `TotalLiabilities`,
  `Equity`, `RetainedEarnings`, `Revenue`, and either `EBIT` or
  `EBITDA` + `Depreciation`.

**Recommended:** `Country`, `Sector`, `Year` (needed for time trends).

**Extra raw fields** unlock more Performance-page ratios — a ratio simply
doesn't appear if its inputs are missing: `OperatingExpense`,
`InterestExpense`, `GovernmentGrants`, `TotalExpense`, `TaxExpense`.

Two templates are downloadable from the Home page — one for a
pre-computed-Z file, one for a raw-financials file — and two example
portfolios: illustrative Pacific SOEs (Z only), and two real water
utilities with five years of full statements (raw financials, computed
live).

## Known simplifications, flagged for v4

- Portfolio averages (Performance page, Counterfactuals page) are simple
  means across SOEs — not asset-weighted. Add a `TotalAssets`-based
  weighting later if you want this.
- The 90% prediction interval treats the slope/intercept SEs as
  independent (no covariance term) — a placeholder pending the full
  regression output.
- Shock coefficients have no SEs yet in `config.py` (`"se": None`) — the
  counterfactual currently applies point estimates only.
- KPI thresholds use the 3-tier red/amber/green collapse described above,
  not the IMF guide's full 5-category scale.
- Historical data bank (benchmarking new uploads against an accumulated
  dataset) is intentionally not built yet, per your instruction.
- A short user guidance note for download from the dashboard — planned,
  not yet built.
