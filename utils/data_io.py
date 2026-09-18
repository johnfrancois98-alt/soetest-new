"""
Data intake: detect columns by alias, parse the upload, and standardize
everything into one clean dataframe used by every page.

Handles two kinds of upload:
  1. A file that already has a Z-score (or the four Altman X1–X4
     components) per SOE-year.
  2. A raw financial-statement file — balance sheet + income statement
     line items, in the spirit of the IMF SOE Health Check Tool's input
     form — from which this module computes the Altman components, Z,
     and every KPI ratio itself.

FIELD_TO_COLUMN is the single source of truth mapping a standardized raw
field name (as used in config.ALIASES / KPI_THRESHOLDS "requires" lists)
to the column name used in the working dataframe. utils/kpis.py imports
it from here so the two stay in sync.
"""

import numpy as np
import pandas as pd

from config import ALIASES

FIELD_TO_COLUMN = {
    "current_assets": "CurrentAssets",
    "current_liabilities": "CurrentLiabilities",
    "total_assets": "TotalAssets",
    "total_liabilities": "TotalLiabilities",
    "total_equity": "TotalEquity",
    "retained_earnings": "RetainedEarnings",
    "revenue": "Revenue",
    "total_expense": "TotalExpense",
    "operating_expense": "OperatingExpense",
    "net_income": "NetIncome",
    "interest_expense": "InterestExpense",
    "tax_expense": "TaxExpense",
    "ebit": "EBIT",
    "ebitda": "EBITDA",
    "depreciation": "Depreciation",
    "government_grants": "GovernmentGrants",
}


def _norm(s):
    return "".join(ch for ch in str(s).lower() if ch.isalnum())


def detect_columns(columns):
    """Map each standard field name to the actual column found in the file."""
    table = {_norm(c): c for c in columns}

    def find(keys):
        for k in keys:
            if k in table:
                return table[k]
        return None

    return {name: find(keys) for name, keys in ALIASES.items()}


def _compute_components(out: pd.DataFrame):
    """X1–X4 from raw balance-sheet/income-statement fields, NaN-safe."""
    x1 = (out["CurrentAssets"] - out["CurrentLiabilities"]) / out["TotalAssets"]
    x2 = out["RetainedEarnings"] / out["TotalAssets"]
    x3 = out["EBIT"] / out["TotalAssets"]
    x4 = out["TotalEquity"] / out["TotalLiabilities"]
    return x1, x2, x3, x4


def build_dataframe(raw: pd.DataFrame):
    """
    Standardize an uploaded dataframe.

    Returns (df, error, note):
      - df is None and error is set if the file can't be used at all
      - otherwise df has SOE, Country, Sector, Year, X1–X4, Z, ZSource,
        plus every raw financial field found (see FIELD_TO_COLUMN) —
        present as NaN where not found, so downstream KPI/component code
        can skip gracefully rather than fail.
    """
    cols = detect_columns(raw.columns)

    if cols["soe"] is None:
        return None, 'No SOE name column found. Rename it to "SOE" and upload again.', None

    out = pd.DataFrame()
    out["SOE"] = raw[cols["soe"]].astype(str).str.strip()
    out["Country"] = raw[cols["country"]].astype(str).str.strip() if cols["country"] else "Unspecified"
    out["Sector"] = raw[cols["sector"]].astype(str).str.strip() if cols["sector"] else "Unspecified"
    out["Year"] = raw[cols["year"]].astype(str).str.strip() if cols["year"] else ""

    # Raw financial fields — always present as a column, NaN where the
    # upload doesn't have that field, so arithmetic downstream never KeyErrors.
    found_financials = []
    for key, out_col in FIELD_TO_COLUMN.items():
        if cols[key] is not None:
            out[out_col] = pd.to_numeric(raw[cols[key]], errors="coerce")
            found_financials.append(out_col)
        else:
            out[out_col] = np.nan

    # EBIT: use it directly if given; otherwise derive EBITDA - Depreciation
    # wherever EBIT itself is missing for that row.
    derived_ebit = out["EBITDA"] - out["Depreciation"]
    out["EBIT"] = out["EBIT"].fillna(derived_ebit)

    has_z = cols["z"] is not None
    has_components_direct = all(cols[k] is not None for k in ["x1", "x2", "x3", "x4"])

    if has_z:
        out["Z"] = pd.to_numeric(raw[cols["z"]], errors="coerce")
        out["ZSource"] = "direct"
        z_note = f'Z-score column "{cols["z"]}"'
        out["X1"], out["X2"], out["X3"], out["X4"] = _compute_components(out)
    elif has_components_direct:
        out["X1"] = pd.to_numeric(raw[cols["x1"]], errors="coerce")
        out["X2"] = pd.to_numeric(raw[cols["x2"]], errors="coerce")
        out["X3"] = pd.to_numeric(raw[cols["x3"]], errors="coerce")
        out["X4"] = pd.to_numeric(raw[cols["x4"]], errors="coerce")
        out["Z"] = 6.56 * out["X1"] + 3.26 * out["X2"] + 6.72 * out["X3"] + 1.05 * out["X4"]
        out["ZSource"] = "computed_from_components"
        z_note = "the four Altman components (X1–X4)"
    else:
        out["X1"], out["X2"], out["X3"], out["X4"] = _compute_components(out)
        out["Z"] = 6.56 * out["X1"] + 3.26 * out["X2"] + 6.72 * out["X3"] + 1.05 * out["X4"]
        out["ZSource"] = "computed_from_financials"
        if out["Z"].notna().any():
            z_note = (
                "Z computed from raw financial statement fields (Altman EM formula: working "
                "capital, retained earnings, EBIT and equity, each scaled by total assets/liabilities)"
            )
        else:
            return None, (
                "No Z-score column, no X1–X4 components, and not enough raw financial fields "
                "(current assets/liabilities, total assets, retained earnings, EBIT or "
                "EBITDA+Depreciation, total equity, total liabilities) to compute Z. Check the template."
            ), None

    note = f'Matched SOE column "{cols["soe"]}" and {z_note}.'
    if found_financials:
        note += f" Also found {len(found_financials)} raw financial field(s) for the Performance page."
    else:
        note += " No raw financial fields found — the Performance page will be empty until you add them."

    return out, None, note


TEMPLATE_CSV = (
    "SOE,Country,Sector,Year,Z,CurrentAssets,CurrentLiabilities,NetIncome,"
    "TotalAssets,TotalEquity,TotalLiabilities,Revenue,EBIT\n"
    "Islands Power Authority,Fiji,Energy,2025,0.8,120,150,-8,400,90,310,220,-5\n"
    "Pacific Water Board,Tonga,Water,2025,1.6,60,40,3,180,70,110,95,8\n"
    "National Airways Ltd,Samoa,Transport,2025,-0.4,45,70,-15,260,20,240,150,-20\n"
)

# A worked raw-financials example: seven fictional SOEs across five
# sectors, so the tool's charts have real breadth to show. The two water
# utilities (National Water Utility 1/2) use anonymized real financial
# statements; the other five are illustrative. Country "Developia" is
# borrowed from the IMF SOE-HCT User Guide's own fictional example country.
SAMPLE_RAW_FINANCIALS = pd.DataFrame(
    [
        # National Water Utility 1 — anonymized real utility, structurally distressed (negative equity)
        {"Entity": "National Water Utility 1", "Country": "Developia", "Sector": "Water", "Year": 2020, "Revenue": 30271510431, "TotalExpense": 53261812296, "OperatingExpense": 51429979206, "NetIncome": -22990301865, "CurrentAssets": 31648484897, "TotalAssets": 50564692838, "CurrentLiabilities": 50455671036, "TotalLiabilities": 64327611746, "Equity": -13762918908, "RetainedEarnings": -8469714137, "InterestExpense": 610868478, "TaxExpense": 302715104, "EBITDA": -17842468772, "GovernmentGrants": 15517321949, "Depreciation": 6173944775},
        {"Entity": "National Water Utility 1", "Country": "Developia", "Sector": "Water", "Year": 2021, "Revenue": 34557778288, "TotalExpense": 35886836510, "OperatingExpense": 35383283013, "NetIncome": -1329058222, "CurrentAssets": 40810007803, "TotalAssets": 62442063419, "CurrentLiabilities": 63145445773, "TotalLiabilities": 74822227996, "Equity": -12380164577, "RetainedEarnings": -31460016002, "InterestExpense": 290098143, "TaxExpense": 305653942, "EBITDA": 2182341518, "GovernmentGrants": 18229134502, "Depreciation": 3007846243},
        {"Entity": "National Water Utility 1", "Country": "Developia", "Sector": "Water", "Year": 2022, "Revenue": 34693268082, "TotalExpense": 39854246066, "OperatingExpense": 39142772316, "NetIncome": -5160977984, "CurrentAssets": 40967799947, "TotalAssets": 70293954181, "CurrentLiabilities": 72470060858, "TotalLiabilities": 88609037352, "Equity": -18315083171, "RetainedEarnings": -32789074224, "InterestExpense": 123264449, "TaxExpense": 346932680, "EBITDA": 242479036, "GovernmentGrants": 1505559000, "Depreciation": 4691984270},
        {"Entity": "National Water Utility 1", "Country": "Developia", "Sector": "Water", "Year": 2023, "Revenue": 38235261289, "TotalExpense": 31844487779, "OperatingExpense": 32418714872, "NetIncome": 6813438922, "CurrentAssets": 45129531424, "TotalAssets": 83684082230, "CurrentLiabilities": 92937887980, "TotalLiabilities": 111759665933, "Equity": -28075583703, "RetainedEarnings": -37953021814, "InterestExpense": 479444638, "TaxExpense": 382665412, "EBITDA": 11102470602, "GovernmentGrants": 14511101888, "Depreciation": 4702590831},
        {"Entity": "National Water Utility 1", "Country": "Developia", "Sector": "Water", "Year": 2024, "Revenue": 38423772477, "TotalExpense": 46534568933, "OperatingExpense": 48269970712, "NetIncome": -8057641089, "CurrentAssets": 47374294289, "TotalAssets": 90303140285, "CurrentLiabilities": 109262403808, "TotalLiabilities": 129137545242, "Equity": -38834404957, "RetainedEarnings": -44766460736, "InterestExpense": 587161828, "TaxExpense": 384237725, "EBITDA": -2496980951, "GovernmentGrants": 11809921723, "Depreciation": 4595123119},
        # National Water Utility 2 — anonymized real utility, borderline grey-zone
        {"Entity": "National Water Utility 2", "Country": "Developia", "Sector": "Water", "Year": 2020, "Revenue": 4107284286, "TotalExpense": 6795173873, "OperatingExpense": 6053698168, "NetIncome": -1678623608, "CurrentAssets": 34299848286, "TotalAssets": 165798922850, "CurrentLiabilities": 5025485902, "TotalLiabilities": 144569370510, "Equity": 21229542844, "RetainedEarnings": -2509855635, "InterestExpense": 741475705, "TaxExpense": 41072843, "EBITDA": 396194336, "GovernmentGrants": 16958124859, "Depreciation": 3450432470},
        {"Entity": "National Water Utility 2", "Country": "Developia", "Sector": "Water", "Year": 2021, "Revenue": 5304148268, "TotalExpense": 11111429504, "OperatingExpense": 8231264230, "NetIncome": -1765501072, "CurrentAssets": 38696504564, "TotalAssets": 175363451931, "CurrentLiabilities": 5791781654, "TotalLiabilities": 158003236483, "Equity": 17360215448, "RetainedEarnings": -4188479243, "InterestExpense": 827315468, "TaxExpense": 53041483, "EBITDA": 3189216918, "GovernmentGrants": 14854298535, "Depreciation": 6116332880},
        {"Entity": "National Water Utility 2", "Country": "Developia", "Sector": "Water", "Year": 2022, "Revenue": 5674095665, "TotalExpense": 8320013000, "OperatingExpense": 7254070000, "NetIncome": -1533261234, "CurrentAssets": 43874758647, "TotalAssets": 178578576195, "CurrentLiabilities": 6394854275, "TotalLiabilities": 163178640327, "Equity": 15399935868, "RetainedEarnings": -5953980315, "InterestExpense": 1009193455, "TaxExpense": 56740957, "EBITDA": 3678092806, "GovernmentGrants": 14427280189, "Depreciation": 5258067063},
        {"Entity": "National Water Utility 2", "Country": "Developia", "Sector": "Water", "Year": 2023, "Revenue": 6134488908, "TotalExpense": 8169292820, "OperatingExpense": 7732659414, "NetIncome": -2034803912, "CurrentAssets": 48170728769, "TotalAssets": 190991805260, "CurrentLiabilities": 7576528787, "TotalLiabilities": 167373741454, "Equity": 23618063806, "RetainedEarnings": -7487241549, "InterestExpense": 1567059813, "TaxExpense": 61344889, "EBITDA": 3884462312, "GovernmentGrants": 24680212039, "Depreciation": 6677479120},
        {"Entity": "National Water Utility 2", "Country": "Developia", "Sector": "Water", "Year": 2024, "Revenue": 6279189030, "TotalExpense": 10131040111, "OperatingExpense": 6703248655, "NetIncome": -1781721271, "CurrentAssets": 53533758953, "TotalAssets": 191813708958, "CurrentLiabilities": 9116087247, "TotalLiabilities": 170731784701, "Equity": 21081924257, "RetainedEarnings": -9522045461, "InterestExpense": 2124729222, "TaxExpense": 62791890, "EBITDA": 4325681000, "GovernmentGrants": 23925793761, "Depreciation": 4720516232},
        # National Power Corp — Energy, healthy and improving
        {"Entity": "National Power Corp", "Country": "Developia", "Sector": "Energy", "Year": 2022, "Revenue": 50000000000, "TotalExpense": 42000000000, "OperatingExpense": 42000000000, "NetIncome": 4500000000, "CurrentAssets": 20000000000, "TotalAssets": 150000000000, "CurrentLiabilities": 18000000000, "TotalLiabilities": 80000000000, "Equity": 70000000000, "RetainedEarnings": 30000000000, "InterestExpense": 3000000000, "TaxExpense": 1500000000, "EBITDA": 12000000000, "GovernmentGrants": 2000000000, "Depreciation": 5000000000},
        {"Entity": "National Power Corp", "Country": "Developia", "Sector": "Energy", "Year": 2023, "Revenue": 53000000000, "TotalExpense": 44000000000, "OperatingExpense": 44000000000, "NetIncome": 5200000000, "CurrentAssets": 21500000000, "TotalAssets": 158000000000, "CurrentLiabilities": 17500000000, "TotalLiabilities": 78000000000, "Equity": 80000000000, "RetainedEarnings": 35000000000, "InterestExpense": 2900000000, "TaxExpense": 1700000000, "EBITDA": 13500000000, "GovernmentGrants": 1800000000, "Depreciation": 5200000000},
        {"Entity": "National Power Corp", "Country": "Developia", "Sector": "Energy", "Year": 2024, "Revenue": 56000000000, "TotalExpense": 46000000000, "OperatingExpense": 46000000000, "NetIncome": 6000000000, "CurrentAssets": 23000000000, "TotalAssets": 165000000000, "CurrentLiabilities": 17000000000, "TotalLiabilities": 76000000000, "Equity": 89000000000, "RetainedEarnings": 41000000000, "InterestExpense": 2800000000, "TaxExpense": 1900000000, "EBITDA": 15000000000, "GovernmentGrants": 1600000000, "Depreciation": 5400000000},
        # Metro Transit Authority — Transport, distressed and worsening
        {"Entity": "Metro Transit Authority", "Country": "Developia", "Sector": "Transport", "Year": 2022, "Revenue": 8000000000, "TotalExpense": 11000000000, "OperatingExpense": 11000000000, "NetIncome": -2800000000, "CurrentAssets": 3000000000, "TotalAssets": 40000000000, "CurrentLiabilities": 9000000000, "TotalLiabilities": 45000000000, "Equity": -5000000000, "RetainedEarnings": -9000000000, "InterestExpense": 900000000, "TaxExpense": 0, "EBITDA": -1200000000, "GovernmentGrants": 3500000000, "Depreciation": 1800000000},
        {"Entity": "Metro Transit Authority", "Country": "Developia", "Sector": "Transport", "Year": 2023, "Revenue": 8300000000, "TotalExpense": 11600000000, "OperatingExpense": 11600000000, "NetIncome": -3100000000, "CurrentAssets": 2700000000, "TotalAssets": 39000000000, "CurrentLiabilities": 9800000000, "TotalLiabilities": 47500000000, "Equity": -8100000000, "RetainedEarnings": -12100000000, "InterestExpense": 950000000, "TaxExpense": 0, "EBITDA": -1400000000, "GovernmentGrants": 3700000000, "Depreciation": 1900000000},
        {"Entity": "Metro Transit Authority", "Country": "Developia", "Sector": "Transport", "Year": 2024, "Revenue": 8600000000, "TotalExpense": 12300000000, "OperatingExpense": 12300000000, "NetIncome": -3600000000, "CurrentAssets": 2400000000, "TotalAssets": 38000000000, "CurrentLiabilities": 10700000000, "TotalLiabilities": 50300000000, "Equity": -12300000000, "RetainedEarnings": -15700000000, "InterestExpense": 1000000000, "TaxExpense": 0, "EBITDA": -1700000000, "GovernmentGrants": 3900000000, "Depreciation": 2000000000},
        # State Telecom Ltd — Telecom, strong and safe
        {"Entity": "State Telecom Ltd", "Country": "Developia", "Sector": "Telecom", "Year": 2022, "Revenue": 30000000000, "TotalExpense": 18000000000, "OperatingExpense": 18000000000, "NetIncome": 8000000000, "CurrentAssets": 15000000000, "TotalAssets": 60000000000, "CurrentLiabilities": 8000000000, "TotalLiabilities": 20000000000, "Equity": 40000000000, "RetainedEarnings": 28000000000, "InterestExpense": 600000000, "TaxExpense": 2400000000, "EBITDA": 14000000000, "GovernmentGrants": 0, "Depreciation": 3000000000},
        {"Entity": "State Telecom Ltd", "Country": "Developia", "Sector": "Telecom", "Year": 2023, "Revenue": 33000000000, "TotalExpense": 19500000000, "OperatingExpense": 19500000000, "NetIncome": 9200000000, "CurrentAssets": 17000000000, "TotalAssets": 65000000000, "CurrentLiabilities": 8500000000, "TotalLiabilities": 19500000000, "Equity": 45500000000, "RetainedEarnings": 33500000000, "InterestExpense": 550000000, "TaxExpense": 2700000000, "EBITDA": 15800000000, "GovernmentGrants": 0, "Depreciation": 3100000000},
        {"Entity": "State Telecom Ltd", "Country": "Developia", "Sector": "Telecom", "Year": 2024, "Revenue": 36500000000, "TotalExpense": 21000000000, "OperatingExpense": 21000000000, "NetIncome": 10500000000, "CurrentAssets": 19500000000, "TotalAssets": 71000000000, "CurrentLiabilities": 9000000000, "TotalLiabilities": 19000000000, "Equity": 52000000000, "RetainedEarnings": 40500000000, "InterestExpense": 500000000, "TaxExpense": 3100000000, "EBITDA": 17800000000, "GovernmentGrants": 0, "Depreciation": 3200000000},
        # Fisheries Development Board — Fisheries, grey zone / mixed
        {"Entity": "Fisheries Development Board", "Country": "Developia", "Sector": "Fisheries", "Year": 2022, "Revenue": 6000000000, "TotalExpense": 5600000000, "OperatingExpense": 5600000000, "NetIncome": 250000000, "CurrentAssets": 3500000000, "TotalAssets": 18000000000, "CurrentLiabilities": 3000000000, "TotalLiabilities": 11000000000, "Equity": 7000000000, "RetainedEarnings": 1500000000, "InterestExpense": 400000000, "TaxExpense": 80000000, "EBITDA": 900000000, "GovernmentGrants": 500000000, "Depreciation": 500000000},
        {"Entity": "Fisheries Development Board", "Country": "Developia", "Sector": "Fisheries", "Year": 2023, "Revenue": 6300000000, "TotalExpense": 5900000000, "OperatingExpense": 5900000000, "NetIncome": 280000000, "CurrentAssets": 3600000000, "TotalAssets": 18500000000, "CurrentLiabilities": 3100000000, "TotalLiabilities": 11300000000, "Equity": 7200000000, "RetainedEarnings": 1700000000, "InterestExpense": 420000000, "TaxExpense": 90000000, "EBITDA": 950000000, "GovernmentGrants": 550000000, "Depreciation": 520000000},
        {"Entity": "Fisheries Development Board", "Country": "Developia", "Sector": "Fisheries", "Year": 2024, "Revenue": 6500000000, "TotalExpense": 6200000000, "OperatingExpense": 6200000000, "NetIncome": 200000000, "CurrentAssets": 3550000000, "TotalAssets": 19000000000, "CurrentLiabilities": 3300000000, "TotalLiabilities": 11800000000, "Equity": 7200000000, "RetainedEarnings": 1750000000, "InterestExpense": 450000000, "TaxExpense": 60000000, "EBITDA": 850000000, "GovernmentGrants": 600000000, "Depreciation": 540000000},
        # National Mining Co — Mining, strong and safe
        {"Entity": "National Mining Co", "Country": "Developia", "Sector": "Mining", "Year": 2022, "Revenue": 45000000000, "TotalExpense": 30000000000, "OperatingExpense": 30000000000, "NetIncome": 10000000000, "CurrentAssets": 25000000000, "TotalAssets": 90000000000, "CurrentLiabilities": 12000000000, "TotalLiabilities": 30000000000, "Equity": 60000000000, "RetainedEarnings": 42000000000, "InterestExpense": 1200000000, "TaxExpense": 3000000000, "EBITDA": 18000000000, "GovernmentGrants": 0, "Depreciation": 4000000000},
        {"Entity": "National Mining Co", "Country": "Developia", "Sector": "Mining", "Year": 2023, "Revenue": 48000000000, "TotalExpense": 31500000000, "OperatingExpense": 31500000000, "NetIncome": 11200000000, "CurrentAssets": 27000000000, "TotalAssets": 96000000000, "CurrentLiabilities": 11500000000, "TotalLiabilities": 29000000000, "Equity": 67000000000, "RetainedEarnings": 49000000000, "InterestExpense": 1100000000, "TaxExpense": 3400000000, "EBITDA": 19500000000, "GovernmentGrants": 0, "Depreciation": 4100000000},
        {"Entity": "National Mining Co", "Country": "Developia", "Sector": "Mining", "Year": 2024, "Revenue": 51000000000, "TotalExpense": 33000000000, "OperatingExpense": 33000000000, "NetIncome": 12300000000, "CurrentAssets": 29000000000, "TotalAssets": 101000000000, "CurrentLiabilities": 11000000000, "TotalLiabilities": 28000000000, "Equity": 73000000000, "RetainedEarnings": 56000000000, "InterestExpense": 1000000000, "TaxExpense": 3700000000, "EBITDA": 21200000000, "GovernmentGrants": 0, "Depreciation": 4200000000},
    ]
)

# A raw financial-statement template, matching the IMF SOE-HCT style file
# (Z is computed by the tool, not supplied).
TEMPLATE_RAW_CSV = (
    "Entity,Country,Sector,Year,Revenue,OperatingExpense,NetIncome,CurrentAssets,TotalAssets,"
    "CurrentLiabilities,TotalLiabilities,Equity,RetainedEarnings,InterestExpense,EBITDA,"
    "GovernmentGrants,Depreciation\n"
    "Example SOE,Fiji,Energy,2024,34557778288,35383283013,-1329058222,40810007803,62442063419,"
    "63145445773,74822227996,-12380164577,-31460016002,290098143,2182341518,18229134502,3007846243\n"
)
