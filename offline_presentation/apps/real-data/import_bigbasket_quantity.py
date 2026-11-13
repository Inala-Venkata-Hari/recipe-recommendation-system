"""Normalize the quantity-aware BigBasket CSV without guessing volumes or piece weights."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parent
SOURCE='https://www.kaggle.com/datasets/chinmayshanbhag/big-basket-products'
FOOD_CATEGORIES={'Fruits & Vegetables','Foodgrains, Oil & Masala','Bakery, Cakes & Dairy','Snacks & Branded Foods','Gourmet & World Food','Eggs, Meat & Fish','Beverages'}


def quantity_grams(value):
    match=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*(kg|g|gm)\s*',str(value),re.I)
    if not match:return None
    grams=float(match[1])*(1000 if match[2].lower()=='kg' else 1)
    return grams if math.isfinite(grams) and grams>0 else None


def normalize_products(data):
    required={'ProductName','Brand','Price','DiscountPrice','Quantity','Category','Absolute_Url'}
    if not required.issubset(data):raise ValueError('Missing quantity-aware BigBasket columns.')
    rows=[]
    for index,row in data.iterrows():
        if row.Category not in FOOD_CATEGORIES:continue
        grams=quantity_grams(row.Quantity)
        if grams is None:continue
        sale=pd.to_numeric(row.DiscountPrice,errors='coerce')
        regular=pd.to_numeric(row.Price,errors='coerce')
        price=sale if pd.notna(sale) and sale>0 else regular
        if pd.isna(price) or not math.isfinite(float(price)) or price<=0:continue
        if pd.notna(sale) and pd.notna(regular) and regular>0 and sale>regular:continue
        name=str(row.ProductName).strip()
        url=str(row.Absolute_Url).strip()
        if not name or not url.startswith(('http://','https://')):continue
        rows.append(dict(source_product_id=f'BBQ-{index}',product_name=name,brand=row.Brand,category=row.Category,
                         sale_price=float(price),market_price=float(regular) if pd.notna(regular) else None,
                         original_quantity=str(row.Quantity),pack_grams=grams,quantity_verified=True,
                         grocery_candidate=True,product_url=url,source=SOURCE,source_price_column='DiscountPrice' if price==sale else 'Price'))
    return pd.DataFrame(rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default=str(ROOT/'data/external/price_candidates/chinmayshanbhag/BigBasket.csv'))
    parser.add_argument('--output',default=str(ROOT/'data/bigbasket_quantity'))
    parser.add_argument('--download',action='store_true',help='Download public dataset version 1 before importing')
    args=parser.parse_args();output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    if args.download:
        import urllib.request,zipfile,io
        payload=urllib.request.urlopen('https://www.kaggle.com/api/v1/datasets/download/chinmayshanbhag/big-basket-products?datasetVersionNumber=1',timeout=60).read()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            name=next(name for name in archive.namelist() if Path(name).name=='BigBasket.csv')
            contents=archive.read(name)
        expected='8305d0d882200e4ed03c1464ad4610ef9f694901b678b49b90b5fdab390b761d'
        if hashlib.sha256(contents).hexdigest()!=expected:
            raise ValueError('Downloaded source checksum differs from the verified dataset. Review before importing.')
        target=Path(args.input);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(contents)
    data=pd.read_csv(args.input);products=normalize_products(data)
    products.to_csv(output/'product_catalog.csv',index=False)
    report=dict(source=SOURCE,version=1,publisher_last_updated='2022-08-21',source_rows=len(data),valid_mass_priced_food_listings=len(products),
                source_sha256=hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),
                exclusions='Non-food categories, volume/piece/multipack quantities, invalid prices or URLs; no inferred mass.',
                license='Unconfirmed; local educational inspection only, source data not redistributed.')
    (output/'import_summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
