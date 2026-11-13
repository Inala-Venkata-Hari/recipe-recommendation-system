"""Build isolated, offline-ready snapshots without switching presentation branches."""
import io,json,shutil,subprocess,tarfile
from pathlib import Path
BASE=Path(__file__).resolve().parent
PROJECT=BASE.parent
REPO=PROJECT/'recipe-recommendation-small-test'
PYTHON=PROJECT/'recipe-recommendation-system/.venv/bin/python'
branches={'original':'main','synthetic':'small-test','real-data':'small-test-big-data'}
manifest={}
for name,branch in branches.items():
    target=BASE/'apps'/name
    if target.exists():raise SystemExit(f'{target} already exists; refusing to overwrite demo state.')
    target.mkdir(parents=True)
    archive=subprocess.check_output(['git','-C',str(REPO),'archive',branch])
    with tarfile.open(fileobj=io.BytesIO(archive)) as handle:handle.extractall(target,filter='data')
    manifest[name]={'branch':branch,'commit':subprocess.check_output(['git','-C',str(REPO),'rev-parse',branch],text=True).strip()}
real=BASE/'apps/real-data'
for filename in ['food_catalog.csv','formulations.json','manifest.json']:
    source=REPO/'data/usda_trial'/filename
    destination=real/'data/usda_trial'/filename
    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
# Only the isolated presentation copy uses today's date. Repository code stays unchanged.
p=real/'usda_trial.py';p.write_text(p.read_text().replace('DEFAULT_DATE=date(2026,11,8)','DEFAULT_DATE=date(2026,11,12)'))
seed_script='''
import json,sys
from datetime import date,timedelta
from pathlib import Path
import pandas as pd
from inventory_discounts import generate_combo_offers
from offer_publishing import publish_snapshot,save_promotions
if sys.argv[1]=='synthetic':
    folder=Path('data/synthetic_demo')
    inventory=pd.read_csv(folder/'seller_inventory.csv')
    classified=pd.read_csv(folder/'ingredients_classified.csv')
    day=date(2026,11,5)
    offers=generate_combo_offers(inventory,max_discount=15,minimum_margin_pct=5,min_items=2,max_items=4,today=day,classified=classified)
    # Favor a comprehensible Tomato Rice demonstration, then show other supported offers.
    preferred={'rice','tomato','onion','garlic','cumin'}
    offers.sort(key=lambda o:(not set(o['items'])<=preferred,-o['savings']))
    selected=offers[:20]
    save_promotions(folder/'published_offers.json',publish_snapshot(selected,inventory,day+timedelta(days=7),day))
    print('Synthetic published offers:',len(selected))
else:
    from usda_workflow import simulated_batches,draft_offers,frequency_table,effective_catalog,save_frame
    from inflation_adjustment import inflation_reference
    folder=Path('data/usda_trial');work=folder/'workspace';work.mkdir(exist_ok=True)
    catalog=effective_catalog(inflation_reference(pd.read_csv(folder/'food_catalog.csv')),pd.DataFrame())
    records=json.loads((folder/'formulations.json').read_text());day=date(2026,11,12)
    examples=[f for f in records if f['name'] in ['Beans and brown rice','Black beans with meat','Chicken curry with rice']]
    inventory=pd.concat([simulated_batches(f,catalog,day) for f in examples],ignore_index=True).drop_duplicates('batch_id')
    save_frame(work/'seller_inventory.csv',inventory)
    offers,_,_=draft_offers(inventory,frequency_table(records),catalog,day,min_items=2,max_items=2)
    offers=[o for o in offers if any(set(o['items'])<={str(i['food_code']) for i in f['ingredients']} for f in records)]
    save_promotions(work/'published_offers.json',publish_snapshot(offers,inventory,day+timedelta(days=7),day))
    print('Real-data reference demo: simulated batches',len(inventory),'published offers',len(offers))
'''
for name in ['synthetic','real-data']:
    folder=BASE/'apps'/name
    subprocess.run([str(PYTHON),'-c',seed_script,name],cwd=folder,check=True)
seed=BASE/'seed'
shutil.copytree(BASE/'apps/synthetic/data/synthetic_demo',seed/'synthetic')
shutil.copytree(real/'data/usda_trial/workspace',seed/'real-data')
shutil.copy2(REPO/'presentations/dsf_smart_cart_presentation.html',BASE/'slides.html')
manifest['assessment_dates']={'synthetic':'2026-11-05 (fixed historical scenario)','real-data':'2026-11-12 (simulated inventory)'}
(BASE/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('Offline snapshots prepared at',BASE)
