import streamlit as st
import pandas as pd
import numpy as np

# =====================================================
# CONFIG
# =====================================================
MAX_RELATIVITY = 3.5
ACQUISITION_OPTIONS = [0.0, 2.5, 5.0, 7.5, 10.0]  # %

st.set_page_config(
    page_title="Pricing Asuransi Kredit",
    layout="wide"
)

st.title("📊 Pricing Asuransi Kredit – Data OJK")
st.caption("Divisi Aktuaria")

# =====================================================
# HELPER
# =====================================================
def pct(x):
    return x / 100.0

def clean_options(series):
    return (
        series.dropna()
        .astype(str)
        .str.strip()
        .sort_values()
        .unique()
        .tolist()
    )

def safe_get_value(df, key_col, key_val, val_col):
    row = df.loc[
        df[key_col].astype(str).str.strip() == str(key_val).strip(),
        val_col
    ]
    if row.empty:
        st.error(f"Data tidak ditemukan: {key_col} = {key_val}")
        st.stop()
    return float(row.iloc[0])

# =====================================================
# LOAD DATA
# =====================================================
xls = pd.ExcelFile("Data Base OJK.xlsx")

prov_prod = pd.read_excel(xls, "NPL Produktif per Provinsi")
prov_cons = pd.read_excel(xls, "NPL Konsumtif per Provinsi")
bank_df   = pd.read_excel(xls, "NPL Jenis Bank")
sector_df = pd.read_excel(xls, "NPL Sektor")

for df in [prov_prod, prov_cons, bank_df, sector_df]:
    df.columns = df.columns.str.strip()

# =====================================================
# SEVERITY – SESUAI EXCEL
# =====================================================
def severity_by_tenor(loan_rate, inv_rate, tenor):
    sev = 0.0
    for t in range(1, tenor + 1):
        abd = 1 / ((1 + loan_rate) ** t)
        pv  = 1 / ((1 + inv_rate) ** (t - 1))
        sev += abd * pv
    return sev

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
# DATA RISIKO
# =====================================================
st.subheader("Data Risiko")

c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    jenis_kredit = st.selectbox("Jenis Kredit", ["Produktif", "Konsumtif"])
    prov_df = prov_prod if jenis_kredit == "Produktif" else prov_cons
    wilayah = st.selectbox("Wilayah", clean_options(prov_df["Provinsi"]))

with c2:
    jenis_bank = st.selectbox("Jenis Bank", clean_options(bank_df["Jenis Bank"]))

with c3:
    coverage_pct = st.number_input(
        "Coverage (%)", 0.0, 100.0, 75.00, step=0.01, format="%.2f"
    )
    coverage = pct(coverage_pct)

with c4:
    loan_rate_pct = st.number_input(
        "Suku Bunga Kredit (%)", 0.0, 50.0, 11.00, step=0.01, format="%.2f"
    )
    loan_rate = pct(loan_rate_pct)

with c5:
    tenor = st.number_input("Jangka Waktu (Tahun)", 1, 30, 1)

# ---- SEKTOR (FULL WIDTH)
sektor = st.selectbox("Sektor", clean_options(sector_df["Sektor"]))

# =====================================================
# SIDEBAR – ASUMSI
# =====================================================
st.sidebar.header("Asumsi Pricing (%)")

risk_margin = pct(st.sidebar.number_input("Risk Margin (%)", 0.0, 100.0, 25.00, 0.01))
expense     = pct(st.sidebar.number_input("Expense (%)", 0.0, 100.0, 15.00, 0.01))
profit      = pct(st.sidebar.number_input("Profit (%)", 0.0, 100.0, 10.00, 0.01))

rec_prod = pct(st.sidebar.number_input("Recoveries Produktif (%)", 0.0, 100.0, 0.00, 0.01))
rec_cons = pct(st.sidebar.number_input("Recoveries Konsumtif (%)", 0.0, 100.0, 0.00, 0.01))

inv_rate = pct(st.sidebar.number_input(
    "Suku Bunga Investasi (%)", 0.0, 20.0, 6.10, step=0.0001, format="%.4f"
))

porsi_non_nd = pct(st.sidebar.number_input("Porsi Non-ND (%)", 0.0, 100.0, 40.00, 0.01))

# =====================================================
# CALCULATION
# =====================================================
if st.button("Calculate"):

    base_denom = 1 - expense - profit
    if base_denom <= 0:
        st.error("Expense + Profit ≥ 100%")
        st.stop()

    # --- NPL
    npl = safe_get_value(prov_df, "Provinsi", wilayah, "Average NPL")

    # --- RELATIVITY
    rel_p = safe_get_value(prov_df, "Provinsi", wilayah, "Average Relativity")
    rel_b = safe_get_value(bank_df, "Jenis Bank", jenis_bank, "Average Relativity")
    rel_s = safe_get_value(sector_df, "Sektor", sektor, "Average Relativity")

    total_rel = min(rel_p * rel_b * rel_s, MAX_RELATIVITY)

    # --- FREKUENSI (FINAL)
    recovery = rec_prod if jenis_kredit == "Produktif" else rec_cons

    if jenis_kredit == "Produktif":
        frek = npl * total_rel * coverage * (1 - recovery)
    else:
        frek = npl * porsi_non_nd * total_rel * coverage * (1 - recovery)

    st.info(f"Frekuensi: {frek:.4%}")

    # --- HASIL PER TENOR
    results = []

    for acq in ACQUISITION_OPTIONS:
        acq_d = pct(acq)
        den = base_denom - acq_d
        if den <= 0:
            results.append([f"{acq:.1f}%", "INVALID"])
            continue

        sev = severity_by_tenor(loan_rate, inv_rate, tenor)
        rate_net = frek * sev

        gross = (rate_net * (1 + risk_margin)) / den

        results.append([f"{acq:.1f}%", f"{gross:.4%}"])

    st.subheader("Hasil Perhitungan Rate")
    st.table(pd.DataFrame(results, columns=["Akuisisi", "Gross Rate"]))
