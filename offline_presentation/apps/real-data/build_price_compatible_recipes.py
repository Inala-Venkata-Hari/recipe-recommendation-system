"""Retain only recipes fully supported by observed, mass-normalized BigBasket prices."""
import ast
import json
import math
from pathlib import Path
from collections import Counter
import pandas as pd
from ingredient_normalization import normalize_ingredient
from import_bigbasket import pack_grams

ROOT=Path(__file__).resolve().parent
# Explicit recipe-base mappings to these actual source products. Not fuzzy matches.
# Generic peanut butter does not specify smooth/chunky; the listed variant is retained for transparency.
PRODUCT_ALIASES={
    'Olicoop Olives - Green (Sliced) 450 gm Jar': ['green olives'],
    'American Garden Peanut Butter - Chunky 510 gm Jar': ['peanut butter'],
}


def build_price_catalog(products, ingredient_names):
    known={normalize_ingredient(name) for name in ingredient_names}
    reviewed_aliases=json.loads((ROOT/'product_ingredient_aliases.json').read_text())
    blocked_products=json.loads((ROOT/"product_mapping_exclusions.json").read_text())
    candidates=[]
    for row in products.to_dict('records'):
        if row.get('product_url','') in blocked_products:
            continue
        if str(row.get('grocery_candidate','')).lower() not in {'true','1'}:
            continue
        quantity_verified=str(row.get('quantity_verified','')).lower() in {'true','1'}
        grams=float(row['pack_grams']) if quantity_verified and pd.notna(row.get('pack_grams')) else pack_grams(row['product_name'])
        try: price=float(row['sale_price'])
        except (TypeError,ValueError):continue
        if grams is None or not math.isfinite(grams) or grams<=0 or not math.isfinite(price) or price<=0:
            continue
        # A literal recipe ingredient/product-name match is also acceptable.
        names=reviewed_aliases.get(row['product_name'], PRODUCT_ALIASES.get(row['product_name'],[normalize_ingredient(row['product_name'])]))
        for name in names:
            name=normalize_ingredient(name)
            if name not in known:continue
            candidates.append(dict(ingredient_name=name,price_per_100g=price*100/grams,
                kcal_per_100g=None,source_product_id=str(row['source_product_id']),source_product=row['product_name'],
                brand=row.get('brand',''),listed_pack_price=price,pack_grams=grams,
                price_source='Historical third-party BigBasket snapshot',source=row.get('source',''),
                product_url=row.get('product_url',''),original_quantity=row.get('original_quantity',''),
                mapping_method='Explicit named-product mapping' if row['product_name'] in PRODUCT_ALIASES or row['product_name'] in reviewed_aliases else 'Literal name match'))
    columns=['ingredient_name','price_per_100g','kcal_per_100g','source_product_id','source_product','brand','listed_pack_price','pack_grams','price_source','source','mapping_method','product_url','original_quantity']
    result=pd.DataFrame(candidates,columns=columns)
    if not result.empty:
        result=result.sort_values(['price_per_100g','source_product_id']).drop_duplicates('ingredient_name')
    return result


def filter_recipes(recipes,catalog):
    prices={normalize_ingredient(row.ingredient_name):float(row.price_per_100g) for row in catalog.itertuples()
            if pd.notna(row.price_per_100g) and math.isfinite(float(row.price_per_100g)) and row.price_per_100g>=0}
    quality_exclusions=json.loads((ROOT/"recipe_quality_exclusions.json").read_text())
    missing=Counter();exclusions=[];kept=[]
    for index,row in recipes.iterrows():
        names=set(ast.literal_eval(row.ingredients)) if isinstance(row.ingredients,str) else set(row.ingredients)
        names={normalize_ingredient(name) for name in names}
        needed=sorted(names-set(prices))
        quantities=ast.literal_eval(row.ingredient_quantities) if isinstance(row.ingredient_quantities,str) else row.ingredient_quantities
        measured=set()
        invalid=False
        for item in quantities:
            try:weight=float(item['quantity_g'])
            except (ValueError,TypeError,KeyError):invalid=True;continue
            if not math.isfinite(weight) or weight<=0:invalid=True;continue
            measured.add(normalize_ingredient(item['name']))
        complete=not invalid and names==measured and bool(names)
        quality_reason=quality_exclusions.get(row.get("source_url", ""), "")
        if not needed and complete and not quality_reason:
            kept.append(index)
        else:
            missing.update(needed)
            exclusions.append(dict(id=row.id,name=row['name'],missing_price_ingredients=json.dumps(needed),
                                   missing_or_invalid_quantity=not complete,quality_exclusion=quality_reason))
    return recipes.loc[kept].copy(),pd.DataFrame(exclusions,columns=['id','name','missing_price_ingredients','missing_or_invalid_quantity','quality_exclusion']),missing


def build(source_dir=None,output_dir=None,products_file=None):
    source_dir=Path(source_dir or ROOT/'data/real_recipes')
    output=Path(output_dir or ROOT/'data/price_compatible_recipes');output.mkdir(parents=True,exist_ok=True)
    products=pd.read_csv(products_file or ROOT/'data/bigbasket_quantity/product_catalog.csv')
    recipes=pd.read_csv(source_dir/'recipes_cleaned.csv')
    all_names=pd.read_csv(source_dir/'ingredient_catalog.csv').ingredient_name
    catalog=build_price_catalog(products,all_names)
    kept,excluded,missing=filter_recipes(recipes,catalog)
    kept.to_csv(output/'recipes_cleaned.csv',index=False)
    catalog.to_csv(output/'ingredient_catalog.csv',index=False)
    excluded.to_csv(output/'excluded_recipes.csv',index=False)
    pd.DataFrame(missing.most_common(),columns=['ingredient_name','recipes_blocked']).to_csv(output/'missing_prices.csv',index=False)
    frequencies=Counter(name for value in kept.ingredients for name in set(ast.literal_eval(value)))
    classified=[]
    for name,count in frequencies.items():
        ratio=count/len(kept)
        category='Common' if ratio>=.25 else 'Moderately common' if ratio>=.10 else 'Specialized' if ratio>=.03 else 'Rare / recipe-specific'
        classified.append(dict(ingredient_name=name,recipe_frequency=count,frequency_ratio=ratio,ingredient_frequency_category=category))
    pd.DataFrame(classified,columns=['ingredient_name','recipe_frequency','frequency_ratio','ingredient_frequency_category']).to_csv(output/'ingredients_classified.csv',index=False)
    for name,cols in [('seller_inventory.csv',['ingredient_name','stock_qty','required_qty','unit_cost','unit_price']),('pantry_ingredients.csv',['ingredient_name','enabled','notes']),('pantry_candidates.csv',['ingredient_name','recipe_frequency','frequency_ratio'])]:
        if not (output/name).exists():pd.DataFrame(columns=cols).to_csv(output/name,index=False)
    manifest=dict(dataset='BigBasket-priced DataHive subset',source_recipe_count=len(recipes),usable_unique_recipes=len(kept),
                  excluded_recipes=len(excluded),quality_exclusions=int(excluded.quality_exclusion.ne('').sum()),priced_ingredients=len(catalog),price_policy='Every ingredient must have an observed price with unambiguous mass and a valid recipe gram quantity; no pantry exceptions.',
                  calorie_policy='Unknown calorie basis remains unknown; prices do not supply nutrition.',
                  source_archive=str(source_dir),price_source='https://www.kaggle.com/datasets/chinmayshanbhag/big-basket-products',price_snapshot='2022-08-21 (publisher update; observation dates not supplied)',top_missing_prices=missing.most_common(20))
    (output/'dataset_manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest

if __name__=='__main__':print(json.dumps(build(),indent=2))
