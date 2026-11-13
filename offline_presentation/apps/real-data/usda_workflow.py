"""USD seller/customer workflow around exact USDA identifiers."""
import math
import re
from datetime import timedelta
from pathlib import Path
from collections import Counter
import pandas as pd
from inventory_discounts import classification_parameters,score_inventory,generate_combo_offers
from checkout import checkout_lines

INVENTORY_COLUMNS=['ingredient_name','food_code','batch_id','stock_qty','required_qty','unit_cost','unit_price','stock_unit','received_date','expiry_date','avg_daily_sales','target_holding_days','markdown_window_days','inventory_origin']


def batch_pack_grams(unit):
    match=re.fullmatch(r'([0-9]+(?:\.[0-9]+)?) g pack',str(unit))
    if not match or float(match.group(1))<=0:raise ValueError('Inventory must specify a positive gram pack size.')
    return float(match.group(1))


def save_frame(path,frame):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp');frame.to_csv(temporary,index=False);temporary.replace(path)


def load_inventory(path):
    if not Path(path).exists():return pd.DataFrame(columns=INVENTORY_COLUMNS)
    return pd.read_csv(path,dtype={'ingredient_name':str,'batch_id':str}).reindex(columns=INVENTORY_COLUMNS)


def frequency_table(formulations):
    counts=Counter(str(i['food_code']) for f in formulations for i in {str(i['food_code']):i for i in f['ingredients']}.values())
    return pd.DataFrame([dict(ingredient_name=code,recipe_frequency=count,frequency_ratio=count/len(formulations)) for code,count in sorted(counts.items())])


def effective_catalog(reference,overrides):
    result=reference.copy()
    if overrides is None or overrides.empty:
        result['price_basis']=result.get('reference_price_basis','USDA historical estimate')
        return result
    checked=validate_price_upload(overrides,reference)
    values=checked.set_index('food_code').selling_price_per_100g_usd.to_dict()
    result['price_basis']=['Seller-entered price' if int(c) in values else basis for c,basis in zip(result.food_code,result.get('reference_price_basis',pd.Series('USDA historical estimate',index=result.index)))]
    result['reference_price_per_100g_usd']=result.price_per_100g_usd
    result['price_per_100g_usd']=[values.get(int(code),price) for code,price in zip(result.food_code,result.price_per_100g_usd)]
    return result


def validate_price_upload(data,reference):
    required={'food_code','selling_price_per_100g_usd'}
    if not required.issubset(data) or data.empty:raise ValueError('CSV requires food_code and selling_price_per_100g_usd with at least one row.')
    result=data[list(sorted(required))].copy()
    codes=pd.to_numeric(result.food_code,errors='coerce');values=pd.to_numeric(result.selling_price_per_100g_usd,errors='coerce')
    if codes.isna().any() or not codes.map(lambda c:math.isfinite(c) and c==int(c)).all():raise ValueError('Food codes must be known whole-number USDA codes.')
    result['food_code']=codes.astype(int)
    if result.food_code.duplicated().any() or not set(result.food_code)<=set(reference.food_code.astype(int)):raise ValueError('Food codes must be unique and present in the USDA catalog.')
    if values.isna().any() or not values.map(lambda v:math.isfinite(v) and v>0).all():raise ValueError('Selling prices must be finite, positive USD amounts per 100 g.')
    result['selling_price_per_100g_usd']=values
    return result


def priced_formulations(formulations,catalog):
    prices=catalog.set_index('food_code').price_per_100g_usd.to_dict()
    result=[]
    for f in formulations:
        items=[dict(i,price_per_100g_usd=prices[int(i['food_code'])],batch_cost_usd=i['grams']/100*prices[int(i['food_code'])]) for i in f['ingredients']]
        result.append(dict(f,ingredients=items,ingredient_batch_cost_usd=sum(i['batch_cost_usd'] for i in items)))
    return result


def inventory_upload(data,catalog):
    required={'food_code','batch_id','stock_qty','required_qty','unit_cost','received_date','expiry_date'}
    if not required.issubset(data) or data.empty:raise ValueError('Inventory needs food_code, batch_id, stock_qty, required_qty, unit_cost, received_date and expiry_date.')
    rows=[];prices=catalog.set_index('food_code').price_per_100g_usd.to_dict()
    for row in data.to_dict('records'):
        try:
            code=float(row['food_code'])
            if not math.isfinite(code) or code!=int(code) or int(code) not in prices:raise ValueError()
            code=int(code)
        except (TypeError,ValueError):raise ValueError('Inventory contains an unknown food code.')
        batch=str(row['batch_id']).strip()
        if not batch or batch.lower()=='nan':raise ValueError('Every row needs a batch ID.')
        out=dict(row,ingredient_name=str(code),food_code=code,batch_id=batch,unit_price=float(prices[code]),stock_unit='100 g pack',inventory_origin='Seller-entered')
        size=float(row['pack_size_g']) if pd.notna(row.get('pack_size_g')) else batch_pack_grams(row.get('stock_unit','100 g pack'))
        if not math.isfinite(size) or size<=0:raise ValueError('Pack weight must be finite and positive.')
        out.update(stock_unit=f'{size:g} g pack',unit_price=float(prices[code])*size/100)
        for name in ['stock_qty','required_qty','unit_cost']:
            try:value=float(row[name])
            except (TypeError,ValueError):raise ValueError(f'{name} must be a finite non-negative number.')
            if not math.isfinite(value) or value<0:raise ValueError(f'{name} must be a finite non-negative number.')
            out[name]=value
        for name in ['avg_daily_sales','target_holding_days','markdown_window_days']:
            raw=row.get(name)
            if raw is None or pd.isna(raw):continue
            try:value=float(raw)
            except (ValueError,TypeError):raise ValueError(f'{name} must be a finite non-negative number when supplied.')
            if not math.isfinite(value) or value<0:raise ValueError(f'{name} must be a finite non-negative number when supplied.')
            out[name]=value
        for name in ['received_date','expiry_date']:
            date=pd.to_datetime(str(row[name]),errors='coerce')
            if pd.isna(date):raise ValueError('Batch dates must be valid dates, for example 2026-11-08.')
            out[name]=date.date().isoformat()
        rows.append(out)
    result=pd.DataFrame(rows).reindex(columns=INVENTORY_COLUMNS)
    if result.batch_id.duplicated().any():raise ValueError('Batch IDs must be unique in the upload.')
    return result


def simulated_batches(formulation,catalog,today):
    prices=catalog.set_index('food_code').price_per_100g_usd.to_dict();today=pd.Timestamp(today).date()
    return pd.DataFrame([dict(ingredient_name=str(i['food_code']),food_code=int(i['food_code']),batch_id=f"DEMO-{i['food_code']}-{today}",stock_qty=50,required_qty=10,
        unit_cost=prices[int(i['food_code'])]*.6,unit_price=prices[int(i['food_code'])],stock_unit='100 g pack',
        received_date=(today-timedelta(days=8)).isoformat(),expiry_date=(today+timedelta(days=2)).isoformat(),
        avg_daily_sales=2,target_holding_days=7,markdown_window_days=7,inventory_origin='SIMULATED scenario — not USDA observed stock') for i in formulation['ingredients']],columns=INVENTORY_COLUMNS)


def draft_offers(inventory,classified,catalog,today,max_discount=30,minimum_margin=5,min_items=2,max_items=4,candidate_limit=12,scoring_mode='rules',model_path=None):
    pricing_inventory=inventory.copy()
    rates={str(int(row.food_code)):float(row.price_per_100g_usd) for row in catalog.itertuples()}
    if not pricing_inventory.empty:
        pricing_inventory['recorded_unit_price']=pricing_inventory['unit_price']
        pricing_inventory['unit_price']=pricing_inventory.ingredient_name.astype(str).map(rates)*pricing_inventory.stock_unit.map(batch_pack_grams)/100
    scored=score_inventory(pricing_inventory,today=today,classified=classified,scoring_mode=scoring_mode,model_path=model_path)
    if scored.empty:return [],scored,0
    eligible=scored[scored.eligible].copy()
    # Pick FEFO first, then cap distinct ingredients by urgency.
    eligible['_expiry']=pd.to_datetime(eligible.expiry_date,errors='coerce')
    eligible['_received']=pd.to_datetime(eligible.received_date,errors='coerce')
    eligible=eligible.sort_values(['_expiry','_received']).drop_duplicates('ingredient_name')
    count=len(eligible)
    eligible=eligible.sort_values(['discount_priority','ingredient_name'],ascending=[False,True]).head(candidate_limit)
    selected=pricing_inventory[pricing_inventory.batch_id.isin(eligible.batch_id)]
    offers=generate_combo_offers(selected,max_discount=max_discount,minimum_margin_pct=minimum_margin,min_items=min_items,max_items=max_items,today=today,classified=classified,scoring_mode=scoring_mode,model_path=model_path)
    # Compare to the same cent-rounded standalone 100 g lines used by checkout.
    for offer in offers:
        weights={code:batch_pack_grams(selected.loc[selected.batch_id==batch,'stock_unit'].iloc[0]) for code,batch in zip(offer['items'],offer['batch_ids'])}
        offer['quantities_g']=weights
        regular=round(sum(round(rates[code]*weights[code]/100,2) for code in offer['items']),2)
        cent_floor=math.ceil(round(regular*(1-max_discount/100),10)*100)/100
        price=max(offer['offer_price'],cent_floor)
        costs=sum(float(selected.loc[selected.batch_id==batch,'unit_cost'].iloc[0]) for batch in offer['batch_ids'])
        offer.update(original_price=regular,offer_price=price,savings=round(regular-price,2),
                     profit=round(price-costs,2),margin_pct=(price-costs)/price*100)
    offers=[o for o in offers if o['savings']>0 and o['offer_price']<o['original_price']]
    names=catalog.set_index('food_code').name.to_dict()
    for offer in offers:
        offer['currency']='USD'
        offer['minimum_margin_pct']=minimum_margin
        offer['effective_discount_pct']=offer['savings']/offer['original_price']*100
        for code in offer['items']:
            offer['breakdown']=offer['breakdown'].replace(f'{code}:', f'{names[int(code)]}:')
        offer['display_name']=' + '.join(names[int(code)] for code in offer['items'])
        offer['quantity_description']=' + '.join(f"{offer['quantities_g'][code]:g} g {names[int(code)]}" for code in offer['items'])
        offer['inventory_origin']='; '.join(sorted(set(selected[selected.batch_id.isin(offer['batch_ids'])].inventory_origin.astype(str))))
    return offers,scored,max(0,count-candidate_limit)



def purchase_plan(quantities,pack_sizes):
    result=[]
    for code,grams in quantities.items():
        grams=float(grams);size=float(pack_sizes.get(int(code),100))
        if not math.isfinite(grams) or grams<=0 or not math.isfinite(size) or size<=0:
            raise ValueError('Required weights and pack sizes must be finite and positive.')
        packs=math.ceil(round(grams/size,10))
        result.append(dict(food_code=int(code),required_g=grams,pack_size_g=size,packs=packs,
                           purchased_g=packs*size,leftover_g=packs*size-grams))
    return result


def validate_cart_stock(quantities,inventory,chosen=(),assessment_date=None,pack_sizes=None):
    """Validate all purchased grams for tracked products, reserving chosen batches first."""
    if inventory.empty:return
    for code,grams in quantities.items():
        rows=inventory[inventory.ingredient_name.astype(str)==str(code)].copy()
        if rows.empty:continue  # Catalog-only products have no asserted stock quantity.
        usable=rows.copy()
        if pack_sizes is not None:
            usable=usable[usable.stock_unit.map(batch_pack_grams)==float(pack_sizes.get(int(code),100))]
        if assessment_date is not None:
            received=pd.to_datetime(usable.received_date,errors='coerce')
            expiry=pd.to_datetime(usable.expiry_date,errors='coerce')
            day=pd.Timestamp(assessment_date).normalize()
            usable=usable[(received<=day)&(expiry>day)]
        available=sum(math.floor(max(0,float(r.stock_qty)))*batch_pack_grams(r.stock_unit) for r in usable.itertuples() if math.isfinite(float(r.stock_qty)))
        if float(grams)>available+1e-8:
            raise ValueError(f'Insufficient stock for food {code}: need {float(grams):g} g; usable stock {available:g} g.')
        for offer in chosen:
            if str(code) not in offer['items']:continue
            batch=offer['batch_ids'][offer['items'].index(str(code))]
            matching=usable[usable.batch_id.astype(str)==str(batch)]
            if len(matching)!=1 or float(matching.iloc[0].stock_qty)<1:
                raise ValueError('Selected combo batch is unavailable or expired.')


def customer_lines(quantities,chosen,active,inventory,catalog,pack_sizes=None,assessment_date=None):
    plan=purchase_plan(quantities,pack_sizes) if pack_sizes is not None else None
    if plan is not None:
        quantities={r['food_code']:r['purchased_g'] for r in plan}
        if any(float(pack_sizes.get(int(c),100))!=float(o.get('quantities_g',{}).get(c,100)) for o in chosen for c in o['items']):
            raise ValueError('This combo does not match the configured retail pack. Remove it and choose a current offer.')
    validate_cart_stock(quantities,inventory,chosen,assessment_date,pack_sizes)
    rates={str(int(r.food_code)):float(r.price_per_100g_usd) for r in catalog.itertuples()}
    if any(o.get('currency')!='USD' for o in chosen):raise ValueError('Selected offer does not belong to the USD workspace.')
    raw=checkout_lines({str(int(c)):g for c,g in quantities.items()},rates,chosen,active,inventory,currency='USD')
    lines=consolidate_cart_lines(raw,{str(int(k)):float(v) for k,v in quantities.items()},rates,
                                 catalog.set_index('food_code').name.to_dict())
    if plan is not None:
        for line,row in zip(lines,plan):
            line['Quantity']=f"{row['packs']} × {row['pack_size_g']:g} g ({row['purchased_g']:g} g)"
    return lines


def consolidate_cart_lines(raw,quantities,rates,names):
    """One row per product; distribute bundle discounts in cents, preserving totals."""
    totals={code:{'regular':0,'savings':0,'batches':set(),'discounted_g':0} for code in quantities}
    for line in raw:
        codes=line['Item'].split(' + ')
        regular_cents=round(line['Regular (USD)']*100)
        discount_cents=round(line['Savings (USD)']*100)
        weights=[round(rates[c]*float(line.get('Pack weights',{}).get(c,100))) for c in codes] if len(codes)>1 else [1]
        weight_total=sum(weights)
        # Largest remainder allocation prevents penny drift in the invoice totals.
        def allocate(cents):
            exact=[cents*w/weight_total for w in weights] if weight_total else [cents/len(codes)]*len(codes)
            allocated=[int(v) for v in exact]
            order=sorted(range(len(codes)),key=lambda i:exact[i]-allocated[i],reverse=True)
            for i in order[:cents-sum(allocated)]:allocated[i]+=1
            return allocated
        regular=allocate(regular_cents);discount=allocate(discount_cents)
        batches=line.get('Batches','').split(', ')
        for i,code in enumerate(codes):
            totals[code]['regular']+=regular[i];totals[code]['savings']+=discount[i]
            if len(codes)>1:totals[code]['discounted_g']+=float(line.get('Pack weights',{}).get(code,100))
            if line.get('Batches'):totals[code]['batches'].add(batches[i] if len(batches)==len(codes) else line['Batches'])
    return [{'Item':names[int(code)],'Quantity':f'{quantities[code]:g} g',
             'Regular (USD)':value['regular']/100,'Savings (USD)':value['savings']/100,
             'Payable (USD)':(value['regular']-value['savings'])/100,
             'Batches':', '.join(sorted(value['batches'])),
             'Discounted quantity':f"{value['discounted_g']:g} g"} for code,value in totals.items()]


def schedule_fit(formulation,context,menu=None):
    menu=menu or {}
    if context=='No schedule preference':return False
    if context in {'Busy / short break','Late study/work'}:
        limit=30 if context=='Busy / short break' else 20
        value=menu.get('minutes')
        return value is not None and math.isfinite(float(value)) and 0<float(value)<=limit
    if context=='Family meal':return menu.get('servings') is not None and float(menu['servings'])>=2
    if context=='After workout':
        protein=formulation.get('protein_per_100g')
        return protein is not None and math.isfinite(float(protein)) and float(protein)>=10
    return False


def offer_schedule_matches(offers,formulations,context,menu):
    from offer_publishing import promotion_id
    matches={}
    for offer in offers:
        items={int(c) for c in offer['items']}
        supporting=[f['name'] for f in formulations if items<={int(i['food_code']) for i in f['ingredients']} and schedule_fit(f,context,menu.get(str(f['food_code']),{}))]
        if supporting:matches[promotion_id(offer)]=supporting
    return matches


def custom_formulation(name,quantities,catalog,record_id=None):
    """A user-entered meal of priced components; nutrition is an input-weighted estimate."""
    from uuid import uuid4
    name=str(name).strip()
    if not name or len({int(c) for c in quantities})<2:raise ValueError('Enter a meal name and at least two priced components.')
    lookup={int(r['food_code']):r for r in catalog.to_dict('records')}
    ingredients=[];calories=protein=0.0;protein_complete=True
    for code,weight in quantities.items():
        if int(code) not in lookup:raise ValueError('Use components from the code-linked catalog.')
        weight=float(weight)
        if not math.isfinite(weight) or weight<=0:raise ValueError('Component weights must be finite and positive.')
        row=lookup[int(code)]
        ingredients.append(dict(food_code=int(code),name=row['name'],grams=weight,price_per_100g_usd=row['price_per_100g_usd'],batch_cost_usd=weight/100*row['price_per_100g_usd']))
        calories+=weight/100*float(row['kcal_per_100g'])
        value=row.get('protein_per_100g')
        if value is None or pd.isna(value):protein_complete=False
        else:protein+=weight/100*float(value)
    total=sum(i['grams'] for i in ingredients)
    return dict(food_code=record_id if record_id is not None else -int(uuid4().hex[:12],16),name=name,ingredients=ingredients,ingredient_count=len(ingredients),
                ingredient_batch_grams=total,ingredient_batch_cost_usd=sum(i['batch_cost_usd'] for i in ingredients),
                kcal_per_100g=calories/total*100,protein_per_100g=protein/total*100 if protein_complete else None,
                calorie_basis='Component-weighted input estimate per 100 g; cooking changes are not modeled.',
                origin='User-entered component meal',prepared_food_price_per_100g_usd=None,fdc_id=None)


def validate_inventory_edits(edited,original,catalog):
    if len(edited)!=len(original) or set(edited.batch_id)!=set(original.batch_id):raise ValueError('Use the batch form to add batches; existing IDs cannot be changed here.')
    identities=original.set_index('batch_id')
    for row in edited.itertuples():
        if int(row.food_code)!=int(identities.loc[row.batch_id,'food_code']):raise ValueError('A batch’s food identity cannot be changed.')
    result=inventory_upload(edited,catalog)
    result['unit_price']=result.batch_id.map(identities.unit_price)
    result['inventory_origin']=result.batch_id.map(identities.inventory_origin)
    return result


def one_serving_formulation(record, servings=None, portion_grams=300):
    """Scale input quantities using declared servings or an explicit input-weight estimate."""
    total=sum(float(i['grams']) for i in record['ingredients'])
    value=float(servings if servings is not None else portion_grams)
    if not math.isfinite(value) or value<=0 or total<=0:
        raise ValueError('Serving count and portion weight must be finite and positive.')
    factor=1/value if servings is not None else value/total
    items=[dict(i,grams=i['grams']*factor,batch_cost_usd=i['batch_cost_usd']*factor) for i in record['ingredients']]
    return dict(record,ingredients=items,ingredient_batch_grams=sum(i['grams'] for i in items),
                ingredient_batch_cost_usd=sum(i['batch_cost_usd'] for i in items),
                serving_basis=(f'Seller-declared batch yields {value:g} servings.' if servings is not None
                               else f'Estimated portion: {value:g} g of ingredient inputs; cooked yield is unknown.'))


def pack_price_rate(pack_weight_g,pack_price_usd):
    weight=float(pack_weight_g);price=float(pack_price_usd)
    if not math.isfinite(weight) or weight<=0 or not math.isfinite(price) or price<=0:
        raise ValueError('Pack weight and price must be finite and positive.')
    return price*100/weight


def recipe_availability(record,purchased_quantities):
    """Check one serving independently, aggregating repeated component codes."""
    required=Counter()
    for item in record['ingredients']:
        grams=float(item['grams'])
        if not math.isfinite(grams) or grams<=0:raise ValueError('Recipe weights must be finite and positive.')
        required[int(item['food_code'])]+=grams
    available={int(k):float(v) for k,v in purchased_quantities.items()}
    if any(not math.isfinite(v) or v<0 for v in available.values()):
        raise ValueError('Available weights must be finite and nonnegative.')
    shortages=[{'food_code':code,'required_g':grams,'available_g':available.get(code,0),
                'shortfall_g':grams-available.get(code,0)}
               for code,grams in required.items() if available.get(code,0)+1e-8<grams]
    return {'ready':bool(required) and not shortages,'shortages':shortages}
