"""Import pinned DataHive recipe snapshot; retain source attribution, never invent prices."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from collections import Counter
import pandas as pd
from ingredient_normalization import normalize_ingredient

ROOT = Path(__file__).resolve().parent
SOURCE_REPO = 'datahiveai/recipes-with-nutrition'
SOURCE_REVISION = '33ff70ba3dc1a1a77395fc477934b4ffb18a347d'
SOURCE_URL = f'https://huggingface.co/datasets/{SOURCE_REPO}/resolve/{SOURCE_REVISION}/recipes-with-nutrition.csv'
COLUMNS = ['recipe_name','source','url','servings','calories','ingredients','cuisine_type']


def positive(value):
    try:
        value = float(value)
        return value if math.isfinite(value) and value > 0 else None
    except (ValueError, TypeError):
        return None


def parse_recipe(row):
    try:
        source_items = json.loads(row['ingredients'])
    except (ValueError, TypeError):
        return None
    if not isinstance(source_items, list) or not source_items:
        return None
    quantities = {}
    complete = True
    for item in source_items:
        if not isinstance(item, dict) or not isinstance(item.get('food'), str):
            return None
        name = normalize_ingredient(item['food'])
        if not name:
            return None
        weight = positive(item.get('weight'))
        if weight is None:
            complete = False
        # A missing duplicate weight makes that ingredient's full quantity unknown.
        if name not in quantities:
            quantities[name] = weight
        elif quantities[name] is None or weight is None:
            quantities[name] = None
        else:
            quantities[name] += weight
    title = str(row.get('recipe_name', '')).strip()
    url = str(row.get('url', '')).strip()
    if not title or title == 'nan' or not url.startswith(('http://','https://')):
        return None
    try:
        tags = json.loads(row.get('cuisine_type', '[]'))
        tags = tags if isinstance(tags,list) else []
    except (ValueError,TypeError):
        tags = []
    return dict(id='DH-' + hashlib.sha256(url.encode()).hexdigest()[:20],name=title,
                ingredients=repr(list(quantities)),n_ingredients=len(quantities),
                ingredient_quantities=repr([dict(name=name,quantity_g=weight) for name,weight in quantities.items()]),
                servings=positive(row.get('servings')),minutes=None,calories_per_serving=None,
                source_calories=positive(row.get('calories')),calorie_basis='Unverified source basis; not used as per-serving calories',
                tags=repr(tags),steps='[]',nutrition='[]',quantity_complete=complete,
                source=str(row.get('source','')),source_url=url,dataset=SOURCE_REPO,
                quantity_basis='Publisher-provided gram weights; may be estimated')


def import_recipes(source, output):
    output = Path(output)
    raw = pd.read_csv(source,usecols=COLUMNS)
    parsed = [recipe for row in raw.to_dict('records') if (recipe := parse_recipe(row)) is not None]
    recipes = pd.DataFrame(parsed).drop_duplicates('source_url').reset_index(drop=True)
    if recipes.empty or recipes.id.duplicated().any():
        raise ValueError('No usable recipes or non-unique IDs.')
    output.mkdir(parents=True,exist_ok=True)
    recipes.to_csv(output/'recipes_cleaned.csv',index=False)
    # Count once per recipe using the normalized ingredient list.
    import ast
    frequencies=Counter(name for value in recipes.ingredients for name in ast.literal_eval(value))
    records=[]
    for name,count in sorted(frequencies.items()):
        ratio=count/len(recipes)
        category='Common' if ratio>=.25 else 'Moderately common' if ratio>=.10 else 'Specialized' if ratio>=.03 else 'Rare / recipe-specific'
        records.append(dict(ingredient_name=name,recipe_frequency=count,frequency_ratio=ratio,ingredient_frequency_category=category))
    classified=pd.DataFrame(records)
    classified.to_csv(output/'ingredients_classified.csv',index=False)
    # Preserve any seller-entered prices on subsequent imports.
    catalog_file=output/'ingredient_catalog.csv'
    catalog=pd.DataFrame({'ingredient_name':list(sorted(frequencies)),'price_per_100g':float('nan'),'kcal_per_100g':float('nan')})
    if catalog_file.exists():
        existing=pd.read_csv(catalog_file)
        catalog=pd.concat([existing,catalog]).drop_duplicates('ingredient_name',keep='first')
    catalog.to_csv(catalog_file,index=False)
    for filename,columns in [('seller_inventory.csv',['ingredient_name','stock_qty','required_qty','unit_cost','unit_price','batch_id','stock_unit','received_date','expiry_date','avg_daily_sales','target_holding_days','markdown_window_days']),('pantry_ingredients.csv',['ingredient_name','enabled','notes'])]:
        if not (output/filename).exists():
            pd.DataFrame(columns=columns).to_csv(output/filename,index=False)
    classified[classified.frequency_ratio>=.25][['ingredient_name','recipe_frequency','frequency_ratio']].to_csv(output/'pantry_candidates.csv',index=False)
    manifest=dict(dataset=SOURCE_REPO,revision=SOURCE_REVISION,download_url=SOURCE_URL,
                  license='CC BY-NC 4.0 (publisher declaration)',source_rows=len(raw),usable_unique_recipes=len(recipes),
                  complete_weight_recipes=int(recipes.quantity_complete.sum()),unique_ingredients=len(frequencies),
                  source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                  unknown_fields=['cooking time','verified calorie basis','ingredient prices','seller stock/cost/expiry'],
                  attribution='DataHive AI; underlying recipe sources and URLs retained per record.')
    (output/'dataset_manifest.json').write_text(json.dumps(manifest,indent=2))
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',default=str(ROOT/'data/external/nutrition_recipes.csv'))
    parser.add_argument('--output',default=str(ROOT/'data/real_recipes'))
    parser.add_argument('--download', action='store_true', help='Download the pinned publisher CSV to --input first')
    args=parser.parse_args()
    if args.download:
        import urllib.request
        target = Path(args.input)
        target.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(SOURCE_URL, target)
    print(json.dumps(import_recipes(args.input,args.output),indent=2))
