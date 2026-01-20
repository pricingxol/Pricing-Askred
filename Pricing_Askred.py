import streamlit as st
import pandas as pd
import numpy as np

# =====================================================
# CONFIG
# =====================================================
MAX_RELATIVITY = 3.5
ACQUISITION_OPTIONS = [0.0, 2.5, 5.0, 7.5, 10.0]
MAX_TENOR = 5

st.set_page_config(page_title="Pricing Asuransi Kredit", layout="wide")
st.title("📊 Pricing Asuransi Kredit – Data OJK")
st.caption("Divisi Aktuaria")

# =====================================================
# HELPER
# =====================================================
def pct(x): return x / 100

def clean_options(s):
    return s.dropna().astype(str).str.strip().unique().tolist()

def safe_get(df, k, v, c):
    r = df.loc[df[k].astype(str).str.strip() == str(v).strip(), c]
    if r.empty:
        st.error(f"Data tidak ditemukan: {v}")
        st.stop()
    return float(r.iloc[0])

# =====================================================
# LOAN & SEVERITY (FINAL)
# =====================================================
def outstanding_schedule(rate_annual, tenor_year):
    r = rate_annual / 12
    n = tenor_year * 12
    return np.array([
        ((1 + r) ** n - (1 + r) ** m) / ((1 + r) ** n - 1)
        for m in range(1, n + 1)
    ])

def average_baki_debet(rate_annual, tenor_year):
    sch = outstanding_schedule(rate_annual, tenor_year)
    return [sch[i*12:(i+1)*12].mean() for i in range(tenor_year)]

def severity_amortizing(rate_kredit, rate_invest, tenor_year):
    abd = average_baki_debet(rate_kredit, tenor_year)
    return sum(abd[i] / ((1 + rate_invest) ** i) for i in range(len(abd)))

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
# INPUT
# =====================================================
st.subheader("Data Risiko")

c1, c2, c3, c4 = st.columns(4)

with c1:
    jenis_kredit = st.selectbox("Jenis Kredit", ["Produktif", "Konsumtif"])
    prov_df = prov_prod if jenis_kredit == "Produktif" else prov_cons
    wilayah = st.selectbox("Wilayah", clean_options(prov_df["Provinsi"]))

with c2:
    jenis_bank = st.selectbox("Jenis Bank", clean_options(bank_df["Jenis Bank"]))
    sektor = st.selectbox("Sektor", clean_options(sector_df["Sektor"]))

with c3:
    coverage = pct(st.number_input("Coverage (%)", 0.0, 100.0, 75.0, 0.01))
    rate_kredit = pct(st.number_input("Suku Bunga Kredit (%)", 0.0, 50.0, 11.0, 0.01))

with c4:
    tenor = st.number_input("Tenor Maks (Tahun)", 1, MAX_TENOR, 5)

# =====================================================
# SIDEBAR
# =====================================================
st.sidebar.header("Asumsi Pricing (%)")
risk_margin = pct(st.sidebar.number_input("Risk Margin", 0.0, 100.0, 25.0, 0.01))
expense     = pct(st.sidebar.number_input("Expense", 0.0, 100.0, 15.0, 0.01))
profit      = pct(st.sidebar.number_input("Profit", 0.0, 100.0, 10.0, 0.01))
recovery    = pct(st.sidebar.number_input("Recovery", 0.0, 100.0, 0.0, 0.01))
inv_rate    = pct(st.sidebar.number_input("Suku Bunga Investasi", 0.0, 20.0, 6.1, 0.0001))
porsi_non_nd = pct(st.sidebar.number_input("Porsi Non-ND", 0.0, 100.0, 40.0, 0.01))

# =====================================================
# CALCULATION
# =====================================================
if st.button("Calculate"):

    base_npl = prov_df.loc[np.isclose(prov_df["Average Relativity"], 1), "Average NPL"].iloc[0]

    rel = (
        safe_get(prov_df, "Provinsi", wilayah, "Average Relativity") *
        safe_get(bank_df, "Jenis Bank", jenis_bank, "Average Relativity") *
        safe_get(sector_df, "Sektor", sektor, "Average Relativity")
    )

    frek = base_npl * rel * coverage * (1 - recovery)
    if jenis_kredit == "Konsumtif":
        frek *= porsi_non_nd

    results = []

    for acq in ACQUISITION_OPTIONS:
        row = [f"{acq:.1f}%"]
        den = 1 - expense - profit - pct(acq)

        for t in range(1, tenor + 1):
            sev = severity_amortizing(rate_kredit, inv_rate, t)
            pure = frek * sev
            gross = (pure * (1 + risk_margin)) / den
            row.append(f"{gross:.4%}")

        results.append(row)

    columns = ["Akuisisi"] + \
              ["Rate 1 tahun"] + \
              [f"Rate Sekaligus {i} tahun" for i in range(2, tenor + 1)]

    st.subheader("Hasil Perhitungan Rate")
    st.table(pd.DataFrame(results, columns=columns))
