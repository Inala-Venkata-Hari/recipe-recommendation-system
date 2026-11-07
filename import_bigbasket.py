"""Import a publicly shared supermarket product CSV into an isolated data directory.
Run: python import_bigbasket.py --input bigbasket.csv
Or: python import_bigbasket.py --url https://.../bigbasket.csv
This never modifies small-test, synthetic_demo or existing recipe/inventory data.
"""
import argparse
import json
import re
from pathlib import Path
import pandas as pd
from datetime import datetime, timezone

OUT = Path(__file__).resolve().parent / "data" / "bigbasket_import"
ALIASES = {
    "product_name": ["product_name", "product", "productname", "name"],
    "category": ["category_name", "category"],
    "sub_category": ["sub_category", "subcategory"],
    "brand": ["brand_name", "brand"],
    "sale_price": ["sale_price", "selling_price", "price"],
    "market_price": ["market_price", "mrp"],
    "type": ["type_product", "type", "product_type"],
    "rating": ["rating_product", "rating"],
}

def norm(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(value).casefold())).strip()

def pack_grams(text):
    text = str(text).lower()
    if re.search(r"\d\s*[x×*]\s*\d|pack of\s*\d|combo|\d\s*(?:ml|litre|liters)\b", text):
        return None
    match = re.findall(r"(?<!\w)(\d+(?:\.\d+)?)\s*(kg|kgs|g|gm|gms|grams?)\b", text)
    if len(match) != 1:
        return None
    value, unit = match[0]
    return float(value) * (1000 if unit.startswith("k") else 1)

def import_catalog(df, source):
    available = {norm(x).replace(" ", "_"): x for x in df.columns}
    cols = {target: next((available[x] for x in choices if x in available), None)
            for target, choices in ALIASES.items()}
    if not cols["product_name"] or not cols["sale_price"]:
        raise ValueError("Dataset needs product/product_name and sale_price columns.")
    output = pd.DataFrame({name: df[source_col] for name, source_col in cols.items() if source_col})
    for name in ALIASES:
        if name not in output:
            output[name] = pd.NA
    original_rows = len(output)
    output["product_name"] = output["product_name"].astype("string").str.strip()
    output["sale_price"] = pd.to_numeric(output["sale_price"], errors="coerce")
    output["market_price"] = pd.to_numeric(output["market_price"], errors="coerce")
    output = output.dropna(subset=["product_name", "sale_price"])
    output = output[(output.product_name.str.len() > 1) & (output.sale_price > 0)]
    output = output.drop_duplicates(subset=["product_name", "brand", "sale_price", "type"])
    output["category"] = output["category"].fillna("Unknown")
    nonfood = ("beauty", "hygiene", "household", "cleaning", "garden", "pet", "stationery", "electronics")
    output["grocery_candidate"] = ~output["category"].astype(str).str.casefold().apply(
        lambda category: any(word in category for word in nonfood))
    output["normalized_product"] = output["product_name"].map(norm)
    output["pack_grams"] = [pack_grams(f"{name} {kind}") for name, kind in zip(output["product_name"], output["type"])]
    output["listed_price_per_100g"] = (output["sale_price"] * 100 /
        pd.to_numeric(output["pack_grams"], errors="coerce")).round(2)
    output["source"] = source
    OUT.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUT / "product_catalog.csv", index=False)
    summary = {
        "source": source,
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "source_rows": original_rows,
        "valid_distinct_listings": len(output),
        "grocery_candidates": int(output["grocery_candidate"].sum()),
        "weight_known": int(output["pack_grams"].notna().sum()),
        "warnings": ["Third-party listing, not live price or inventory.",
                     "No real seller stock, cost, expiry, sales or nutrition fields.",
                     "Retail SKUs have not been assumed equivalent to recipe ingredients."],
    }
    (OUT / "import_summary.json").write_text(json.dumps(summary, indent=2))
    return summary

def main():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input")
    source.add_argument("--url")
    args = parser.parse_args()
    location = args.input or args.url
    print(json.dumps(import_catalog(pd.read_csv(location, low_memory=False), location), indent=2))

if __name__ == "__main__":
    main()
