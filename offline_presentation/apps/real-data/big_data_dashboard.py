"""BigBasket listing analytics; run: streamlit run big_data_dashboard.py.
Shows real third-party *product listings* only after import_bigbasket.py was run.
"""
import json
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "bigbasket_import"
FILE = DATA / "product_catalog.csv"
st.set_page_config(page_title="Smart Cart | Supermarket Data", layout="wide", page_icon="🛒")
st.title("🛒 Smart Cart — Supermarket Data")
st.caption("BigBasket third-party public product listings | Isolated big-data branch")
if not FILE.exists():
    st.warning("The original supermarket CSV has not been imported yet. No source data has been fabricated.")
    st.code("python import_bigbasket.py --input /path/to/bigbasket.csv", language="bash")
    st.markdown("Public reference dataset: https://github.com/arnavification/bigbasket_sql")
    st.stop()
df = pd.read_csv(FILE)
info = DATA / "import_summary.json"
if info.exists():
    summary = json.loads(info.read_text())
    st.caption("Dataset source: " + str(summary.get("source", "unknown")))
    st.caption("Imported at (UTC): " + str(summary.get("imported_at", "unknown")))
st.info("This is a historical third-party listing snapshot, not live BigBasket stock or prices. It contains no observed supermarket expiry dates, procurement costs, or customer orders.")
tabs = st.tabs(["Overview", "Data quality", "Prices & brands", "Integration gaps"])
with tabs[0]:
    a,b,c,d = st.columns(4)
    a.metric("Listings", f"{len(df):,}")
    b.metric("Categories", df["category"].nunique())
    c.metric("Brands", df["brand"].nunique())
    d.metric("Grocery candidates", int(df["grocery_candidate"].astype(str).str.lower().isin(["true", "1"]).sum()))
    st.subheader("Product categories")
    st.bar_chart(df["category"].value_counts().head(20).rename("Products"))
    st.dataframe(df.head(100), use_container_width=True, hide_index=True)
with tabs[1]:
    st.subheader("Missing values")
    st.bar_chart(df.isna().sum().sort_values(ascending=False).rename("Missing"))
    st.metric("Rows with explicit mass-unit pack information", int(df["pack_grams"].notna().sum()))
    st.caption("Unit pricing excludes unparseable packs and does not convert volume (ml/litre) to grams.")
with tabs[2]:
    st.subheader("Prices and product mix")
    cats = sorted(df["category"].dropna().astype(str).unique())
    chosen = st.multiselect("Categories", cats, default=cats[:min(3, len(cats))])
    viewed = df[df["category"].astype(str).isin(chosen)] if chosen else df
    st.bar_chart(viewed["brand"].value_counts().head(15).rename("Products"))
    if "listed_price_per_100g" in viewed:
        prices = pd.to_numeric(viewed["listed_price_per_100g"], errors="coerce")
        st.metric("Median listed price per 100 g (known weight only)", f"₹{prices.median():,.2f}" if prices.notna().any() else "N/A")
    columns = [x for x in ["product_name","brand","category","sale_price","market_price","pack_grams","listed_price_per_100g"] if x in viewed]
    st.dataframe(viewed[columns].head(300), hide_index=True, use_container_width=True)
with tabs[3]:
    st.subheader("Data integration policy")
    st.markdown("""
- **Available from source:** product name, category, brand, source sale price, MRP, type and some ratings.
- **Derived:** normalized product name, likely grocery category, unambiguous weight in grams, price per 100 g.
- **Not available:** actual stock quantities, sales history, seller acquisition costs, expiry dates and calories per 100 g.
- **Recipe integration requires matching:** a supermarket product SKU such as a branded multi-pack is *not automatically* the same as a recipe ingredient such as rice. A reviewed mapping and a reference quantity are required.
- **Future ML:** Instacart transaction data can train basket association models, but must not be mislabeled as Indian BigBasket purchases.
""")
