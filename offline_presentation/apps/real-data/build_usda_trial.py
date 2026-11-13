"""Build a code-joined USD trial; never infer prices for SR/NDB ingredient codes."""
import argparse
import json
import math
from pathlib import Path
from datetime import datetime,timezone
import pandas as pd

ROOT=Path(__file__).resolve().parent
PRICE_URL='https://www.ers.usda.gov/media/6557/purchase-to-plate-national-average-prices-for-nhanes-csv-format.zip?v=19590'
FOOD_URL='https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_survey_food_json_2021-10-28.zip'


def energy(food):
    return next((float(n['amount']) for n in food.get('foodNutrients',[]) if n.get('nutrient',{}).get('number')=='208' and n.get('nutrient',{}).get('unitName')=='kcal'),None)


def join_sources(foods,prices):
    # Modification codes apply only to 2011/12, not 2017/18.
    selected=prices[prices.year=='2017/2018'].copy()
    selected['food_code']=selected.food_code.astype(int)
    if selected.food_code.duplicated().any():raise ValueError('Duplicate price food codes in selected period.')
    catalog={}
    lookup={int(f['foodCode']):f for f in foods}
    for row in selected.to_dict('records'):
        code=row['food_code'];food=lookup.get(code)
        price=float(row['price_100gm'])
        if food is None or not math.isfinite(price) or price<=0:continue
        kcal=energy(food)
        if kcal is None or not math.isfinite(kcal) or kcal<0:continue
        catalog[code]=dict(food_code=code,name=food['description'],price_per_100g_usd=price,
                           kcal_per_100g=kcal,protein_per_100g=next((float(n['amount']) for n in food.get('foodNutrients',[]) if n.get('nutrient',{}).get('number')=='203' and n.get('nutrient',{}).get('unitName')=='g'),None),price_method=row.get('method_description',''),
                           fdc_id=food.get('fdcId'),source_url=f"https://fdc.nal.usda.gov/food-details/{food.get('fdcId')}/nutrients")
    formulations=[]
    for food in foods:
        inputs=food.get('inputFoods',[])
        if len(inputs)<=1:continue
        # Keep recorded ingredient components, combining repeated identical food codes.
        grams={};valid=True
        for item in inputs:
            code=int(item['ingredientCode']);weight=float(item.get('ingredientWeight',0))
            if code not in catalog or not math.isfinite(weight) or weight<=0:
                valid=False;break
            grams[code]=grams.get(code,0)+weight
        if not valid or len(grams)<2:continue
        ingredients=[dict(food_code=code,name=catalog[code]['name'],grams=weight,
                          price_per_100g_usd=catalog[code]['price_per_100g_usd'],
                          batch_cost_usd=weight/100*catalog[code]['price_per_100g_usd']) for code,weight in grams.items()]
        formulations.append(dict(food_code=int(food['foodCode']),name=food['description'],
            kcal_per_100g=energy(food),protein_per_100g=next((float(n['amount']) for n in food.get('foodNutrients',[]) if n.get('nutrient',{}).get('number')=='203' and n.get('nutrient',{}).get('unitName')=='g'),None),ingredients=ingredients,ingredient_count=len(ingredients),
            ingredient_batch_grams=sum(grams.values()),ingredient_batch_cost_usd=sum(i['batch_cost_usd'] for i in ingredients),
            prepared_food_price_per_100g_usd=catalog.get(int(food['foodCode']),{}).get('price_per_100g_usd'),
            fdc_id=food.get('fdcId')))
    return pd.DataFrame(catalog.values()),formulations


def rank_formulations(formulations,selected,preference='Fewest additional items'):
    chosen={int(code) for code in selected}
    rows=[]
    for formulation in formulations:
        items={int(i['food_code']) for i in formulation['ingredients']}
        matches=items&chosen
        if chosen and not matches:continue
        rows.append(dict(formulation,matched_count=len(matches),additional_count=len(items-chosen)))
    if preference=='Budget-friendly (per 100 g input)':
        tie=lambda f:f['ingredient_batch_cost_usd']/f['ingredient_batch_grams']*100
    elif preference=='Lowest ingredient batch cost':
        tie=lambda f:f['ingredient_batch_cost_usd']
    elif preference=='Lowest calories per 100 g':
        tie=lambda f:f['kcal_per_100g'] if f['kcal_per_100g'] is not None else float('inf')
    else:
        tie=lambda f:f['name'].casefold()
    return sorted(rows,key=lambda f:(-f['matched_count'],f['additional_count'],tie(f),f['food_code']))


def build(source_dir=None,output_dir=None):
    source=Path(source_dir or ROOT/'data/external/usda_pair')
    output=Path(output_dir or ROOT/'data/usda_trial');output.mkdir(parents=True,exist_ok=True)
    foods=json.loads((source/'FoodData_Central_survey_food_json_2021-10-28.json').read_text())['SurveyFoods']
    prices=pd.read_csv(source/'pp_national_average_prices_csv.csv',encoding='cp1252')
    catalog,formulations=join_sources(foods,prices)
    catalog.to_csv(output/'food_catalog.csv',index=False)
    (output/'formulations.json').write_text(json.dumps(formulations,indent=2))
    manifest=dict(currency='USD',period='2017/2018',food_records=len(foods),matched_price_and_calorie_records=len(catalog),fully_ingredient_priced_formulations=len(formulations),
                  price_url=PRICE_URL,food_url=FOOD_URL,created_at=datetime.now(timezone.utc).isoformat(),
                  price_basis='Historical national-average estimates per 100 edible grams, not current retailer quotes.',
                  formulation_basis='Recorded ingredient weights; not final cooked yield or standard servings.')
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2));return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--download',action='store_true');args=parser.parse_args()
    if args.download:
        import urllib.request,zipfile,io
        source=ROOT/'data/external/usda_pair';source.mkdir(parents=True,exist_ok=True)
        for url in [PRICE_URL,FOOD_URL]:
            payload=urllib.request.urlopen(url,timeout=60).read()
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                for name in archive.namelist():
                    if name.lower().endswith(('.csv','.json')):(source/Path(name).name).write_bytes(archive.read(name))
    print(json.dumps(build(),indent=2))
