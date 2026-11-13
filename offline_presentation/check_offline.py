"""Exercise demo workflows with outbound Python socket connections blocked."""
import json,os,socket,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
name=sys.argv[1];folder=ROOT/'apps'/name
os.chdir(folder);sys.path.insert(0,str(folder))
original_connect=socket.socket.connect
blocked=[]
def offline_connect(sock,address):
    if isinstance(address,tuple) and address[0] not in ('127.0.0.1','localhost','::1'):
        blocked.append(str(address));raise OSError('Offline presentation verification: internet disabled')
    return original_connect(sock,address)
socket.socket.connect=offline_connect
if name=='synthetic':os.environ['RECIPE_DATA_DIR']=str(folder/'data/synthetic_demo')
if name=='real-data':os.environ.update(USDA_DATA_DIR=str(folder/'data/usda_trial'),USDA_WORK_DIR=str(folder/'data/usda_trial/workspace'))
from streamlit.testing.v1 import AppTest
import pandas as pd
entry='usda_trial.py' if name=='real-data' else 'app.py'
app=AppTest.from_file(str(folder/entry)).run(timeout=45)
assert not app.exception,[(e.message) for e in app.exception]
report={'demo':name,'initial_render':'PASS','external_connection_attempts':blocked}
if name=='original':
    import ast
    records=pd.read_csv(folder/'data/recipes_cleaned.csv')
    ingredients=ast.literal_eval(records.iloc[0].ingredients)
    options=app.multiselect(key='cart_ingredients').options
    selected=[i for i in ingredients if i in options][:5]
    if len(selected)<3:selected=options[:3]
    app.multiselect(key='cart_ingredients').set_value(selected).run(timeout=45)
    assert not app.exception
    assert not any('Select '+str(i)+' more item' in m.value for m in app.info for i in [1,2,3])
    report['recommendation_selection']=selected
elif name=='synthetic':
    app.multiselect(key='cart_ingredients').set_value(['rice','tomato','onion']).run(timeout=45)
    assert not app.exception
    active=next(m.value for m in app.metric if m.label=='Active published offers');assert int(active)>0
    button=next(b for b in app.button if b.label=='Add this published combo' and not b.disabled)
    button.click().run(timeout=45);assert not app.exception
    next(b for b in app.button if b.label=='Confirm simulated checkout').click().run(timeout=45)
    assert not app.exception
    assert b'<!DOCTYPE html>' in app.session_state['demo_receipt']
    (ROOT/'sample-invoices').mkdir(exist_ok=True)
    (ROOT/'sample-invoices/synthetic-invoice.html').write_bytes(app.session_state['demo_receipt'])
    report.update(published_offers=active,combo_checkout='PASS',html_invoice='PASS')
else:
    forms=json.loads((folder/'data/usda_trial/formulations.json').read_text())
    example=next(f for f in forms if f['name']=='Beans and brown rice')
    app.multiselect(key='usda_selected').set_value([example['ingredients'][0]['food_code']]).run(timeout=45)
    assert not app.exception
    active=next(m.value for m in app.metric if m.label=='Active published offers');assert int(active)>0
    app.button(key=f"usda_missing_{example['food_code']}").click().run(timeout=45);assert not app.exception
    assert app.session_state['usda_chosen_combos']
    next(b for b in app.button if b.label=='Confirm simulated checkout').click().run(timeout=45)
    assert not app.exception
    assert b'Currency: USD' in app.session_state['usda_receipt']
    (ROOT/'sample-invoices').mkdir(exist_ok=True)
    (ROOT/'sample-invoices/real-data-invoice.html').write_bytes(app.session_state['usda_receipt'])
    report.update(published_offers=active,add_missing_and_auto_discount='PASS',html_invoice='PASS')
assert not blocked,blocked
(ROOT/'checks').mkdir(exist_ok=True)
(ROOT/'checks'/f'{name}.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
