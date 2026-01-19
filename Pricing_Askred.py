import streamlit as st
import pandas as pd

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Bundling Rate Calculator",
    layout="wide"
)

st.title("📊 Bundling Rate Calculator")
st.caption("by Divisi Aktuaria Askrindo")

# =====================================================
# PRICING ASSUMPTIONS (LOCKED)
# =====================================================
EXPENSE = 0.15
PROFIT = 0.05
MAX_AKUISISI = 0.20

LOCKED_AKUISISI = {
    "Property": 0.15,
    "Motorvehicle": 0.25
}

# =====================================================
# LOAD RATE MATRIX
# =====================================================
@st.cache_data(show_spinner="Loading rate matrix...")
def load_rate_matrix(path):
    df = pd.read_excel(path)
    df.columns = df.columns.str.strip()
    return df

df_rate = load_rate_matrix("rate_matrix_produk.xlsx")

# =====================================================
# CORE RATE ENGINE
# =====================================================
def get_rate(df, coverage, subcover, factors):

    q = (df["Coverage"] == coverage) & (df["Subcover"] == subcover)

    for col, val in factors.items():
        q &= (
            (df[col].astype(str) == str(val)) |
            (df[col].isna())
        )

    result = df[q].copy()

    if result.empty:
        raise ValueError(f"Rate tidak ditemukan: {coverage} - {subcover}")

    factor_cols = [
        c for c in df.columns
        if c not in ["Coverage", "Subcover", "Rate"]
    ]

    result["priority"] = result[factor_cols].isna().sum(axis=1)

    return float(result.sort_values("priority").iloc[0]["Rate"])

# =====================================================
# SESSION STATE
# =====================================================
if "products" not in st.session_state:
    st.session_state.products = [{}]

if "results" not in st.session_state:
    st.session_state.results = None

# =====================================================
# INPUT PRODUK
# =====================================================
st.subheader("Input Produk")

coverage_list = sorted(df_rate["Coverage"].dropna().unique())

for i, p in enumerate(st.session_state.products):

    cols = st.columns([2, 3, 2, 2, 2, 1, 0.5])

    # Coverage
    with cols[0]:
        p["Coverage"] = st.selectbox(
            "Coverage" if i == 0 else "",
            coverage_list,
            key=f"coverage_{i}"
        )

    # Subcover
    subcover_list = (
        df_rate[df_rate["Coverage"] == p["Coverage"]]["Subcover"]
        .dropna().unique()
    )

    with cols[1]:
        p["Subcover"] = st.selectbox(
            "Subcover" if i == 0 else "",
            sorted(subcover_list),
            key=f"subcover_{i}"
        )

    # Context-aware factors
    df_ctx = df_rate[
        (df_rate["Coverage"] == p["Coverage"]) &
        (df_rate["Subcover"] == p["Subcover"])
    ]

    factor_cols = [
        c for c in df_ctx.columns
        if c not in ["Coverage", "Subcover", "Rate"]
        and df_ctx[c].dropna().nunique() > 0
    ]

    factors = {}

    for idx, col in enumerate(factor_cols[:3]):
        with cols[2 + idx]:
            values = (
                df_ctx[col]
                .dropna()
                .astype(str)
                .unique()
            )

            selected = st.selectbox(
                col if i == 0 else "",
                sorted(values),
                key=f"{col}_{i}"
            )

            factors[col] = selected

            df_ctx = df_ctx[
                (df_ctx[col].astype(str) == str(selected)) |
                (df_ctx[col].isna())
            ]

    p["Factors"] = factors
    p["ExpectedFactors"] = factor_cols

    # =================================================
    # AKUISISI PER PRODUK (PROTECTED)
    # =================================================
    with cols[5]:
        if p["Coverage"] in LOCKED_AKUISISI:
            p["Akuisisi"] = LOCKED_AKUISISI[p["Coverage"]]

            st.number_input(
                "Akuisisi (%)" if i == 0 else "",
                value=p["Akuisisi"] * 100,
                disabled=True,
                key=f"akuisisi_{i}"
            )
        else:
            p["Akuisisi"] = st.number_input(
                "Akuisisi (%)" if i == 0 else "",
                min_value=0.0,
                max_value=20.0,
                value=20.0,
                step=0.5,
                key=f"akuisisi_{i}"
            ) / 100

    # Delete row
    with cols[6]:
        if len(st.session_state.products) > 1:
            if st.button("❌", key=f"del_{i}"):
                st.session_state.products.pop(i)
                st.session_state.results = None
                st.rerun()

# =====================================================
# ADD PRODUCT
# =====================================================
if st.button("➕ Tambah Produk"):
    st.session_state.products.append({})
    st.session_state.results = None
    st.rerun()

# =====================================================
# VALIDATION
# =====================================================
def validate_products(products):
    for idx, p in enumerate(products, start=1):

        if len(p.get("Factors", {})) < len(p.get("ExpectedFactors", [])):
            return False, f"Produk {idx}: Faktor risiko belum lengkap"

        if p["Coverage"] not in LOCKED_AKUISISI and p["Akuisisi"] > MAX_AKUISISI:
            return False, f"Akuisisi Produk {idx} melebihi 20%"

    return True, None

# =====================================================
# HITUNG RATE
# =====================================================
if st.button("Hitung Rate"):

    valid, msg = validate_products(st.session_state.products)

    if not valid:
        st.error(f"❌ {msg}")
    else:
        results = []
        total_rate = 0

        denom_matrix = 1 - EXPENSE - PROFIT - MAX_AKUISISI  # 0.6

        for p in st.session_state.products:

            base_rate = get_rate(
                df_rate,
                p["Coverage"],
                p["Subcover"],
                p["Factors"]
            )

            denom_user = 1 - EXPENSE - PROFIT - p["Akuisisi"]
            adjusted_rate = base_rate * (denom_matrix / denom_user)

            total_rate += adjusted_rate

            results.append({
                "Coverage": p["Coverage"],
                "Subcover": p["Subcover"],
                **p["Factors"],
                "Akuisisi (%)": f"{p['Akuisisi']*100:.1f}%",
                "Rate (%)": adjusted_rate * 100
            })

        st.session_state.results = (results, total_rate)

# =====================================================
# OUTPUT
# =====================================================
if st.session_state.results:

    results, total_rate = st.session_state.results

    st.subheader("Bundling Product")

    df_out = pd.DataFrame(results)
    df_out.insert(0, "No", range(1, len(df_out) + 1))
    df_out["Rate (%)"] = df_out["Rate (%)"].map(lambda x: f"{x:.4f}%")

    st.dataframe(df_out, use_container_width=True, hide_index=True)

    st.success(
        f"✅ **Total Bundling Rate (Adjusted)**: {total_rate * 100:.4f}%"
    )

    st.warning(
        """
        **Catatan:**
        1. Rate dan akuisisi kelas bisnis Property dan Motorvehicle menyesuaikan ketentuan Regulator.
        2. Maksimum akuisisi untuk produk selain Property dan Motorvehicle adalah **20%**.
        3. Besarnya rate adjustment dilakukan dengan adanya **perbedaan asumsi akuisisi**.
        4. Perhitungan profitability bundling dapat diakses pada link **https://profitabilitycheckingaskrindo.streamlit.app/**.
        """
    )
