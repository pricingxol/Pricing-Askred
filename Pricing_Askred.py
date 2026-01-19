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
MAX_COVERAGE = 0.75
MAX_RELATIVITY = 3.5
ACQUISITION_OPTIONS = [0.0, 0.025, 0.05, 0.075, 0.10]

st.set_page_config(
    page_title="Pricing Asuransi Kredit",
    layout="wide"
)

st.title("📊 Pricing Asuransi Kredit – Data OJK per September 2025")
st.caption("By Divisi Aktuaria Askrindo")

# =====================================================
# LOAD MASTER DATA
# =====================================================
@st.cache_data
def load_master():
    xls = pd.ExcelFile("Data Base OJK.xlsx")

    prov_prod = pd.read_excel(xls, "Template NPL Produktif Provinsi")
    prov_cons = pd.read_excel(xls, "Template NPL Konsumtif Provinsi")
    bank_df = pd.read_excel(xls, "Template NPL Jenis Bank")
    sector_df = pd.read_excel(xls, "Template NPL Sektor")

    # strip column names (ANTI SPASI TERSEMBUNYI)
    for df in [prov_prod, prov_cons, bank_df, sector_df]:
        df.columns = df.columns.str.strip()

    return prov_prod, prov_cons, bank_df, sector_df

prov_prod, prov_cons, bank_df, sector_df = load_master()

# =====================================================
# STRICT COLUMN CHECK
# =====================================================
def require_column(df, col):
    if col not in df.columns:
        raise ValueError(f"Kolom '{col}' WAJIB ada di Excel")
    return col

# =====================================================
# HELPER FUNCTIONS
# =====================================================
def get_value(df, key_col, key_val, val_col):
    return float(df.loc[df[key_col] == key_val, val_col].values[0])

def calc_total_relativity(rp, rb, rs):
    return min(rp * rb * rs, MAX_RELATIVITY)

def expected_probability(npl, porsi_non_nd, relativity, coverage, recovery):
    return npl * porsi_non_nd * relativity * coverage * (1 - recovery)

def average_baki_debet(rate, tenor):
    balances = [(1 / ((1 + rate) ** t)) for t in range(1, tenor + 1)]
    return np.mean(balances)

def pure_rate(probability, severity):
    return probability * severity

def gross_rate(pure, risk_margin, expense, profit, acquisition):
    return (pure * (1 + risk_margin)) / (1 - expense - profit - acquisition)

# =====================================================
# INPUT IDENTITAS
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
# INPUT DATA RISIKO
# =====================================================
st.subheader("Data Risiko")

c1, c2, c3 = st.columns(3)

with c1:
    jenis_kredit = st.selectbox("Jenis Kredit", ["Produktif", "Konsumtif"])
    prov_df = prov_prod if jenis_kredit == "Produktif" else prov_cons

    prov_col = require_column(prov_df, "Provinsi")
    npl_col = require_column(prov_df, "Average NPL")
    rel_col = require_column(prov_df, "Average Relativity")

    wilayah = st.selectbox("Wilayah", prov_df[prov_col].unique())

with c2:
    bank_col = require_column(bank_df, "Jenis Bank")
    bank_rel_col = require_column(bank_df, "Average Relativity")

    jenis_bank = st.selectbox("Jenis Bank", bank_df[bank_col].unique())

    sector_col = require_column(sector_df, "Sektor")
    sector_rel_col = require_column(sector_df, "Average Relativity")

    sektor = st.selectbox("Sektor", sector_df[sector_col].unique())

with c3:
    coverage = st.number_input("Coverage", 0.0, MAX_COVERAGE, 0.6)
    loan_rate = st.number_input("Suku Bunga Kredit (%)", 0.0, 50.0, 12.0) / 100
    tenor = st.number_input("Jangka Waktu (Tahun)", 1, 20, 3)

# =====================================================
# SIDEBAR ASSUMPTIONS
# =====================================================
st.sidebar.header("Asumsi Pricing")

risk_margin = st.sidebar.number_input("Risk Margin", 0.0, 1.0, 0.1)
expense = st.sidebar.number_input("Expense", 0.0, 1.0, 0.05)
profit = st.sidebar.number_input("Profit", 0.0, 1.0, 0.1)

rec_prod = st.sidebar.number_input("Recoveries Produktif", 0.0, 1.0, 0.4)
rec_cons = st.sidebar.number_input("Recoveries Konsumtif", 0.0, 1.0, 0.2)

inv_rate = st.sidebar.number_input("Suku Bunga Investasi", 0.0, 20.0, 6.0) / 100
porsi_non_nd = st.sidebar.number_input("Porsi Non-ND", 0.0, 1.0, 0.8)

# =====================================================
# CALCULATE
# =====================================================
if st.button("Calculate"):

    npl = get_value(prov_df, prov_col, wilayah, npl_col)

    rel_p = get_value(prov_df, prov_col, wilayah, rel_col)
    rel_b = get_value(bank_df, bank_col, jenis_bank, bank_rel_col)
    rel_s = get_value(sector_df, sector_col, sektor, sector_rel_col)

    total_rel = calc_total_relativity(rel_p, rel_b, rel_s)

    recovery = rec_prod if jenis_kredit == "Produktif" else rec_cons

    prob = expected_probability(
        npl, porsi_non_nd, total_rel, coverage, recovery
    )

    avg_bd = average_baki_debet(loan_rate, tenor)
    severity = avg_bd / ((1 + inv_rate) ** tenor)

    pure = pure_rate(prob, severity)

    st.subheader("Hasil Perhitungan Rate")

    results = []
    for acq in ACQUISITION_OPTIONS:
        gr = gross_rate(pure, risk_margin, expense, profit, acq)
        results.append([f"{acq*100:.1f}%", f"{gr:.4%}"])

    df_result = pd.DataFrame(results, columns=["Akuisisi", "Gross Rate"])
    st.table(df_result)

    # =================================================
    # EXPORT PDF
    # =================================================
    if st.button("Export PDF"):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(tmp.name)

        story = [
            Paragraph("<b>Pricing Asuransi Kredit – Data OJK per September 2025</b>", styles["Title"]),
            Spacer(1, 12),
            Paragraph(f"Nama Tertanggung: {nama_tertanggung}", styles["Normal"]),
            Paragraph(f"Nama Bank: {nama_bank_input}", styles["Normal"]),
            Paragraph(f"Nomor Polis: {no_polis}", styles["Normal"]),
            Paragraph(f"Nomor PKS: {no_pks}", styles["Normal"]),
            Spacer(1, 12),
        ]

        table = Table(
            [["Akuisisi", "Gross Rate"]] + results,
            style=TableStyle([
                ("GRID", (0,0), (-1,-1), 0.5, colors.black),
                ("BACKGROUND", (0,0), (-1,0), colors.lightgrey)
            ])
        )

        story.append(table)
        doc.build(story)

        with open(tmp.name, "rb") as f:
            st.download_button(
                "Download PDF",
                f,
                file_name="Pricing_Askred.pdf"
            )
