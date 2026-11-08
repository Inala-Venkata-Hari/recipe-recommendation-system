import unittest
from datetime import date
import pandas as pd
from usda_workflow import validate_cart_stock,customer_lines,draft_offers,frequency_table
from inventory_batches import create_batch
from invoice import render_invoice

class StockAndPackTests(unittest.TestCase):
    def setUp(self):
        self.inventory=pd.DataFrame([dict(ingredient_name='1',food_code=1,batch_id='a',stock_qty=1,stock_unit='100 g pack',received_date='2026-11-01',expiry_date='2026-11-10')])
    def test_all_quantities_checked_and_expiry_excluded(self):
        with self.assertRaisesRegex(ValueError,'Insufficient stock'):
            validate_cart_stock({1:1000},self.inventory,assessment_date='2026-11-08')
        validate_cart_stock({1:100},self.inventory,assessment_date='2026-11-08')
        with self.assertRaises(ValueError):validate_cart_stock({1:100},self.inventory,assessment_date='2026-11-10')
        later=self.inventory.copy();later['received_date']='2026-11-09'
        with self.assertRaises(ValueError):validate_cart_stock({1:100},later,assessment_date='2026-11-08')
    def test_aggregate_batches_and_whole_packs(self):
        other=self.inventory.copy();other['batch_id']='b'
        validate_cart_stock({1:200},pd.concat([self.inventory,other]),assessment_date='2026-11-08')
        fractional=self.inventory.copy();fractional['stock_qty']=.5
        with self.assertRaises(ValueError):validate_cart_stock({1:50},fractional)
    def test_nonstandard_pack_combo_checkout_and_invoice(self):
        catalog=pd.DataFrame([dict(food_code=c,name=f'Food {c}',price_per_100g_usd=1) for c in [1,2]])
        batch_catalog=pd.DataFrame([dict(ingredient_name=str(c),price_per_100g=1) for c in [1,2]])
        inventory=pd.DataFrame()
        for code,size in [(1,500),(2,200)]:
            row=create_batch(batch_catalog,inventory,str(code),str(code),20,2,size/100*.4,date(2026,11,1),date(2026,11,10),1,7,7,date(2026,11,8),pack_size_g=size)
            row.update(food_code=code,inventory_origin='Test fixture')
            inventory=pd.concat([inventory,pd.DataFrame([row])],ignore_index=True)
        forms=[dict(ingredients=[dict(food_code=c) for c in [1,2]])]
        offers,_,_=draft_offers(inventory,frequency_table(forms),catalog,date(2026,11,8),min_items=2,max_items=2)
        self.assertTrue(offers)
        offer=offers[0]
        self.assertEqual(offer['quantities_g'],{'1':500,'2':200})
        lines=customer_lines({1:120,2:180},[offer],offers,inventory,catalog,pack_sizes={1:500,2:200},assessment_date='2026-11-08')
        self.assertEqual(len(lines),2)
        self.assertEqual(lines[0]['Discounted quantity'],'500 g')
        self.assertAlmostEqual(sum(r['Payable (USD)'] for r in lines),offer['offer_price'])
        html=render_invoice(lines,date(2026,11,8),currency='USD')
        self.assertIn('Combo discount covers 500 g',html)
        with self.assertRaises(ValueError):customer_lines({1:11000,2:180},[offer],offers,inventory,catalog,pack_sizes={1:500,2:200},assessment_date='2026-11-08')
    def test_mismatched_pack_stock_is_not_available(self):
        with self.assertRaises(ValueError):
            validate_cart_stock({1:100},self.inventory,assessment_date='2026-11-08',pack_sizes={1:500})

    def test_published_pack_offer_in_streamlit(self):
        import os,json,tempfile
        from pathlib import Path
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest
        from usda_workflow import simulated_batches,save_frame
        root=Path(__file__).resolve().parents[1]
        source=root/'data/usda_trial'
        if not (source/'manifest.json').exists():self.skipTest('Build USDA profile first')
        forms=json.loads((source/'formulations.json').read_text())
        record=next(f for f in forms if f['name']=='Beans and brown rice')
        catalog=pd.read_csv(source/'food_catalog.csv')
        sizes={int(i['food_code']):size for i,size in zip(record['ingredients'],[500,200])}
        inventory=simulated_batches(record,catalog,date(2026,11,8))
        for index,row in inventory.iterrows():
            size=sizes[int(row.food_code)]
            inventory.loc[index,'stock_unit']=f'{size} g pack'
            inventory.loc[index,'unit_cost']=float(row.unit_cost)*size/100
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'USDA_WORK_DIR':folder}):
            save_frame(Path(folder)/'seller_inventory.csv',inventory)
            save_frame(Path(folder)/'pack_sizes.csv',pd.DataFrame([{'food_code':c,'pack_size_g':s} for c,s in sizes.items()]))
            app=AppTest.from_file(str(root/'usda_trial.py')).run(timeout=30)
            next(w for w in app.checkbox if w.label=='Select all draft offers for publishing').check().run(timeout=30)
            next(w for w in app.button if w.label=='Publish selected offers').click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(next(w.value for w in app.metric if w.label=='Active published offers'),'1')
            app.multiselect(key='usda_selected').set_value([next(iter(sizes))]).run(timeout=30)
            app.button(key=f"usda_missing_{record['food_code']}").click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(len(app.session_state['usda_chosen_combos']),1)
            next(w for w in app.button if w.label=='Confirm simulated checkout').click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertIn(b'Combo discount covers 500 g',app.session_state['usda_receipt'])
