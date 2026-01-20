import streamlit as st
import pandas as pd
import numpy as np

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Pricing Asuransi Kredit",
    layout="wide"
)

st.title("📊 Pricing Asuransi Kredit")

MASTER_FILE = "master_askred.xlsx"  # pastikan nama file sesuai

# =====================================================
# HELPER
# =====================================================
def clean_dropdown(series):
    return (
        series.dropna()
        .astype(str)
        .str.strip()
        .sort_values()
        .unique()
        .tolist()
    )

def to_decimal(x):
    """Konversi input persen → desimal"""
    if x > 1:
        return x / 100
    return x

# =====================================================
# LOAD MASTER
# =====================================================
@st.cache_data
def load_master():
    xls = pd.ExcelFile(MASTER_FILE)

    prov_prod = pd.read_excel(xls, xls.sheet_names[0])
    prov_cons = pd.read_excel(xls, xls.sheet_names[1])
    bank_df   = pd.read_excel(xls, xls.sheet_names[2])
    sector_df = pd.read_excel(xls, xls.sheet_names[3])

    return prov_prod, prov_cons, bank_df, sector_df

prov_prod, prov_cons, bank_df, sector_df = load_master()

# =====================================================
# SIDEBAR – ASUMSI PRICING
# =====================================================
st.sidebar.header("Asumsi Pricing")

risk_margin_input = st.sidebar.number_input("Risk Margin", 0.0, 1.0, 0.25)
expense_input     = st.sidebar.number_input("Expense", 0.0, 1.0, 0.15)
profit_input      = st.sidebar.number_input("Profit", 0.0, 1.0, 0.05)

recovery_prod     = st.sidebar.number_input("Recoveries Produktif", 0.0, 1.0, 0.0)
recovery_cons     = st.sidebar.number_input("Recoveries Konsumtif", 0.0, 1.0, 0.0)

bunga_investasi_input = st.sidebar.number_input(
    "Suku Bunga Investasi",
    min_value=0.0,
    max_value=1.0,
    value=0.06106778,
    step=0.00000001,
    format="%.8f"
)

porsi_non_nd          = st.sidebar.number_input("Porsi Non-ND", 0.0, 1.0, 0.40)

# Konversi ke desimal
risk_margin = to_decimal(risk_margin_input)
expense     = to_decimal(expense_input)
profit      = to_decimal(profit_input)
bunga_investasi = to_decimal(bunga_investasi_input)

# Validasi denominator (POINT 2)
denom = 1 - risk_margin - expense - profit
if denom <= 0:
    st.error("Risk Margin + Expense + Profit ≥ 100%")
    st.stop()

# =====================================================
# IDENTITAS RISIKO
# =====================================================
st.subheader("Identitas Risiko")

col1, col2 = st.columns(2)
with col1:
    nama_tertanggung = st.text_input("Nama Tertanggung")
    nama_bank        = st.text_input("Nama Bank")
with col2:
    no_polis = st.text_input("Nomor Polis Existing", "New")
    no_pks   = st.text_input("Nomor PKS Existing", "New")

# =====================================================
# DATA RISIKO
# =====================================================
st.subheader("Data Risiko")

# ---- ROW 1 (sesuai gambar)
c1, c2, c3, c4, c5, c6 = st.columns([1, 1, 1, 0.8, 1, 1])

with c1:
    jenis_kredit = st.selectbox("Jenis Kredit", ["Produktif", "Konsumtif"])

prov_df = prov_prod if jenis_kredit == "Produktif" else prov_cons

with c2:
    wilayah = st.selectbox(
        "Wilayah",
        clean_dropdown(prov_df["Wilayah"])
    )

with c3:
    jenis_bank = st.selectbox(
        "Jenis Bank",
        clean_dropdown(bank_df["Jenis Bank"])
    )

with c4:
    coverage = st.number_input("Coverage", 0.0, 1.0, 0.75)

with c5:
    bunga_kredit_input = st.number_input("Suku Bunga Kredit (%)", 0.0, 100.0, 11.0)
    bunga_kredit = to_decimal(bunga_kredit_input)

with c6:
    tenor = st.number_input("Jangka Waktu (Tahun)", 1, 30, 1)

# ---- SEKTOR (FULL WIDTH, PALING BAWAH)
sektor = st.selectbox(
    "Sektor",
    clean_dropdown(sector_df["Sektor"])
)

# =====================================================
# CALCULATION
# =====================================================
st.markdown("---")

if st.button("Calculate"):
    # Dummy PD & LGD (placeholder, nanti bisa tarik dari tabel)
    pd_rate = 0.02
    lgd = coverage * (1 - (recovery_prod if jenis_kredit == "Produktif" else recovery_cons))

    expected_loss = pd_rate * lgd * tenor
    net_risk_rate = expected_loss * (1 + bunga_kredit - bunga_investasi)

    gross_rate = net_risk_rate / denom

    result_df = pd.DataFrame({
        "Akusisi": [f"{x:.1%}" for x in np.arange(0, 0.125, 0.025)],
        "Gross Rate": [gross_rate * (1 + x) * 100 for x in np.arange(0, 0.125, 0.025)]
    })

    st.subheader("Hasil Perhitungan Rate")
    st.dataframe(result_df, use_container_width=True)
