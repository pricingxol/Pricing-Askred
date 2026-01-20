import streamlit as st
import pandas as pd
import numpy as np
import tempfile

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# =====================================================
# CONFIG
# =====================================================
MAX_COVERAGE = 100.0
MAX_RELATIVITY = 3.5
ACQUISITION_OPTIONS = [0.0, 2.5, 5.0, 7.5, 10.0]  # persen

st.set_page_config(
    page_title="Pricing Asuransi Kredit",
    layout="wide"
)

st.title("📊 Pricing Asuransi Kredit – Data OJK per September 2025")
st.caption("By Divisi Aktuaria Askrindo")

# =====================================================
# HELPER – RATE HANDLING
# =====================================================
def pct(x):
    """convert percent input → decimal"""
    return x / 100

# =====================================================
# LOAD MASTER DATA
# =====================================================
@st.cache_data
def load_master():
    xls = pd.ExcelFile("Data Base OJK.xlsx")

    prov_prod = pd.read_excel(xls, "NPL Produktif per Provinsi")
    prov_cons = pd.read_excel(xls, "NPL Konsumtif per Provinsi")
    bank_df   = pd.read_excel(xls, "NPL Jenis Bank")
    sector_df = pd.read_excel(xls, "NPL Sektor")

    for df in [prov_prod, prov_cons, bank_df, sector_df]:
        df.columns = df.columns.str.strip()

    return prov_prod, prov_cons, bank_df, sector_df

prov_prod, prov_cons, bank_df, sector_df = load_master()

# =====================================================
# VALIDATION
# =====================================================
def require_column(df, col):
    if col not in df.columns:
        raise ValueError(f"Kolom '{col}' WAJIB ada di Excel")
    return col

def get_value(df, key_col, key_val, val_col):
    return float(df.loc[df[key_col] == key_val, val_col].values[0])

# =====================================================
# SEVERITY (FIXED – SESUAI EXCEL)
# =====================================================
def severity_askred(loan_rate, inv_rate, tenor):
    sev = 0.0
    for t in range(1, tenor + 1):
        abd = 1 / ((1 + loan_rate) ** t)
        pv  = 1 / ((1 + inv_rate) ** (t - 1))
        sev += abd * pv
    return sev

# =====================================================
# IDENTITAS
# =====================================================
st.subheader("Identitas Risiko")

c1, c2 = st.columns(2)
with c1:
    nama_tertanggung = st.text_input("Nama Tertanggung")
    nama_bank_input = st.text_input("Nama Bank")
with c2:
    no_polis = st.text_input("Nomor Polis Existing", "New")
    no_pks = st.text_input("Nomor PKS Existing", "New")

# =====================================================
# DATA RISIKO
# =====================================================
st.subheader("Data Risiko")

c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    jenis_kredit = st.selectbox("Jenis Kredit", ["Produktif", "Konsumtif"])
    prov_df = prov_prod if jenis_kredit == "Produktif" else prov_cons

    prov_col = require_column(prov_df, "Provinsi")
    npl_col  = require_column(prov_df, "Average NPL")
    rel_col  = require_column(prov_df, "Average Relativity")

    wilayah = st.selectbox("Wilayah", prov_df[prov_col].dropna().unique())

with c2:
    bank_col = require_column(bank_df, "Jenis Bank")
    bank_rel_col = require_column(bank_df, "Average Relativity")
    jenis_bank = st.selectbox("Jenis Bank", bank_df[bank_col].dropna().unique())

with c3:
    coverage_pct = st.number_input(
        "Coverage (%)",
        0.0, MAX_COVERAGE, 75.00,
        step=0.01, format="%.2f"
    )
    coverage = pct(coverage_pct)

with c4:
    loan_rate_pct = st.number_input(
        "Suku Bunga Kredit (%)",
        0.0, 50.0, 11.00,
        step=0.01, format="%.2f"
    )
    loan_rate = pct(loan_rate_pct)

with c5:
    tenor = st.number_input("Jangka Waktu (Tahun)", 1, 20, 1)

# ---- SEKTOR (PALING BAWAH, FULL WIDTH)
sector_col = require_column(sector_df, "Sektor")
sector_rel_col = require_column(sector_df, "Average Relativity")

sektor = st.selectbox(
    "Sektor",
    sector_df[sector_col].dropna().unique()
)

# =====================================================
# SIDEBAR – ASUMSI (%)
# =====================================================
st.sidebar.header("Asumsi Pricing (%)")

risk_margin_pct = st.sidebar.number_input(
    "Risk Margin (%)", 0.0, 100.0, 25.00, step=0.01, format="%.2f"
)
expense_pct = st.sidebar.number_input(
    "Expense (%)", 0.0, 100.0, 15.00, step=0.01, format="%.2f"
)
profit_pct = st.sidebar.number_input(
    "Profit (%)", 0.0, 100.0, 10.00, step=0.01, format="%.2f"
)

rec_prod_pct = st.sidebar.number_input(
    "Recoveries Produktif (%)", 0.0, 100.0, 0.00, step=0.01, format="%.2f"
)
rec_cons_pct = st.sidebar.number_input(
    "Recoveries Konsumtif (%)", 0.0, 100.0, 0.00, step=0.01, format="%.2f"
)

inv_rate_pct = st.sidebar.number_input(
    "Suku Bunga Investasi (%)",
    0.0, 20.0, 6.106778,
    step=0.000001, format="%.6f"
)

porsi_non_nd_pct = st.sidebar.number_input(
    "Porsi Non-ND (%)", 0.0, 100.0, 40.00, step=0.01, format="%.2f"
)

# convert
risk_margin = pct(risk_margin_pct)
expense     = pct(expense_pct)
profit      = pct(profit_pct)
rec_prod    = pct(rec_prod_pct)
rec_cons    = pct(rec_cons_pct)
inv_rate    = pct(inv_rate_pct)
porsi_non_nd = pct(porsi_non_nd_pct)

# =====================================================
# CALCULATE
# =====================================================
if st.button("Calculate"):

    base_denom = 1 - expense - profit
    if base_denom <= 0:
        st.error("Expense + Profit ≥ 100%")
        st.stop()

    npl = get_value(prov_df, prov_col, wilayah, npl_col)

    rel_p = get_value(prov_df, prov_col, wilayah, rel_col)
    rel_b = get_value(bank_df, bank_col, jenis_bank, bank_rel_col)
    rel_s = get_value(sector_df, sector_col, sektor, sector_rel_col)

    total_rel = min(rel_p * rel_b * rel_s, MAX_RELATIVITY)

    recovery = rec_prod if jenis_kredit == "Produktif" else rec_cons

    probability = npl * porsi_non_nd * total_rel * (1 - recovery)

    sev = severity_askred(loan_rate, inv_rate, tenor)
    pure = probability * sev * coverage

    st.subheader("Hasil Perhitungan Rate")

    results = []
    for acq in ACQUISITION_OPTIONS:
        acq_d = pct(acq)
        if base_denom - acq_d <= 0:
            results.append([f"{acq:.1f}%", "INVALID"])
            continue
        gross = (pure * (1 + risk_margin)) / (base_denom - acq_d)
        results.append([f"{acq:.1f}%", f"{gross:.4%}"])

    st.table(pd.DataFrame(results, columns=["Akuisisi", "Gross Rate"]))
