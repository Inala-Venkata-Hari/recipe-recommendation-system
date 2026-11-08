import unittest
from usda_workflow import recipe_availability,purchase_plan

class RecipeAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.recipe={'ingredients':[{'food_code':1,'grams':120},{'food_code':2,'grams':180}]}
    def test_names_alone_do_not_mean_ready(self):
        result=recipe_availability(self.recipe,{1:100,2:200})
        self.assertFalse(result['ready'])
        self.assertEqual(result['shortages'][0]['shortfall_g'],20)
    def test_full_packs_satisfy_recipe(self):
        plan=purchase_plan({1:120,2:180},{1:500,2:200})
        self.assertTrue(recipe_availability(self.recipe,{r['food_code']:r['purchased_g'] for r in plan})['ready'])
    def test_missing_and_duplicate_components(self):
        self.assertFalse(recipe_availability(self.recipe,{1:500})['ready'])
        repeated={'ingredients':[{'food_code':1,'grams':60},{'food_code':1,'grams':70}]}
        self.assertFalse(recipe_availability(repeated,{1:100})['ready'])
        self.assertTrue(recipe_availability(repeated,{1:130})['ready'])
        self.assertFalse(recipe_availability({'ingredients':[]},{})['ready'])

    def test_clear_cart_keeps_seller_settings(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import pandas as pd
        from streamlit.testing.v1 import AppTest
        root=Path(__file__).resolve().parents[1]
        catalog_path=root/'data/usda_trial/food_catalog.csv'
        if not catalog_path.exists():self.skipTest('Import USDA data first')
        code=int(pd.read_csv(catalog_path).iloc[0].food_code)
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'USDA_WORK_DIR':folder}):
            path=Path(folder)/'pack_sizes.csv'
            path.write_text(f'food_code,pack_size_g\n{code},500\n')
            before=path.read_bytes()
            app=AppTest.from_file(str(root/'usda_trial.py')).run(timeout=30)
            app.multiselect(key='usda_selected').set_value([code]).run(timeout=30)
            next(b for b in app.button if b.label=='Confirm simulated checkout').click().run(timeout=30)
            self.assertTrue(app.session_state['usda_receipt'])
            app.button(key='usda_clear_cart').click().run(timeout=30)
            self.assertFalse(app.exception)
            self.assertEqual(app.multiselect(key='usda_selected').value,[])
            self.assertNotIn('usda_receipt',app.session_state)
            self.assertEqual(path.read_bytes(),before)
