"""Exercise seller publication through customer checkout in an isolated dataset."""
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from datetime import date
import pandas as pd
from streamlit.testing.v1 import AppTest
from inventory_discounts import generate_combo_offers
from offer_publishing import promotion_id, promotion_history

ROOT=Path(__file__).resolve().parents[1]

class PromotionFlowTests(unittest.TestCase):
    def test_publish_browse_checkout_and_pause(self):
        with tempfile.TemporaryDirectory() as folder:
            shutil.copytree(ROOT/'data/synthetic_demo',folder,dirs_exist_ok=True)
            # Ignore any existing local publications copied from the demonstration.
            for filename in ['published_offers.json','offer_history.json']:
                (Path(folder)/filename).unlink(missing_ok=True)
            with patch.dict(os.environ,{'RECIPE_DATA_DIR':folder}):
                app=AppTest.from_file(str(ROOT/'app.py')).run(timeout=30)
                next(w for w in app.date_input if w.label=='Inventory assessment date').set_value(date(2026,11,5)).run(timeout=30)
                self.assertFalse(app.exception)
                self.assertEqual(next(m for m in app.metric if m.label=='Active published offers').value,'0')
                offers=generate_combo_offers(pd.read_csv(Path(folder)/'seller_inventory.csv'),today='2026-11-05',classified=pd.read_csv(Path(folder)/'ingredients_classified.csv'))
                key=promotion_id(offers[0])
                app.multiselect(key='publish_draft_ids').set_value([key]).run(timeout=30)
                next(b for b in app.button if b.label=='Publish selected offers').click().run(timeout=30)
                self.assertFalse(app.exception)
                app.button(key=f'browse_combo_{key}').click().run(timeout=30)
                self.assertFalse(app.exception)
                self.assertEqual(len(app.session_state['chosen_combos']),1)
                next(b for b in app.button if b.label=='Confirm simulated checkout').click().run(timeout=30)
                self.assertTrue(app.session_state['demo_receipt'])
                next(w for w in app.multiselect if w.label=='Published offers to pause').set_value([key]).run(timeout=30)
                next(b for b in app.button if b.label=='Pause selected offers').click().run(timeout=30)
                self.assertFalse(app.exception)
                self.assertEqual(next(m for m in app.metric if m.label=='Active published offers').value,'0')
                self.assertTrue(any('offer changed or expired' in e.value for e in app.error))
                self.assertFalse(any(b.label=='Confirm simulated checkout' for b in app.button))
                self.assertEqual([e['action'] for e in promotion_history(Path(folder)/'published_offers.json')],['Published','Paused'])
                next(w for w in app.checkbox if w.label=='Select all draft offers for publishing').check().run(timeout=30)
                self.assertFalse(app.exception)
                self.assertTrue(app.multiselect(key='publish_draft_ids').disabled)
                next(b for b in app.button if b.label=='Publish selected offers').click().run(timeout=30)
                self.assertFalse(app.exception)
                self.assertEqual(int(next(m for m in app.metric if m.label=='Active published offers').value),len(offers))
