import unittest
from cart_categories import product_category,recipe_cart_codes

class CartCategoryTests(unittest.TestCase):
    def test_snacks_do_not_match_recipes(self):
        for name in ['Biscuit packet','Cookies, chocolate chip','Potato chips','Cake, chocolate','Ice cream, vanilla']:
            self.assertEqual(product_category(name),'Ready-made snack')
        self.assertEqual(recipe_cart_codes([1,2],{1:'Ready-made snack',2:'Recipe ingredient'}),[2])

    def test_categories_and_explicit_override(self):
        self.assertEqual(product_category('Pizza, cheese'),'Ready-made food')
        self.assertEqual(product_category('Dishwashing soap'),'Utility item')
        self.assertEqual(product_category('Rice, cooked'),'Recipe ingredient')
        self.assertEqual(product_category('Biscuits','Recipe ingredient'),'Recipe ingredient')

    def test_snack_remains_in_checkout_without_recipe_match(self):
        import os
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import pandas as pd
        from streamlit.testing.v1 import AppTest
        root=Path(__file__).resolve().parents[1]
        path=root/'data/usda_trial/food_catalog.csv'
        if not path.exists():self.skipTest('Import USDA data first')
        catalog=pd.read_csv(path)
        snack=next(int(r.food_code) for r in catalog.itertuples() if product_category(r.name)=='Ready-made snack')
        with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'USDA_WORK_DIR':folder}):
            app=AppTest.from_file(str(root/'usda_trial.py')).run(timeout=30)
            app.multiselect(key='usda_selected').set_value([snack]).run(timeout=30)
            self.assertFalse(app.exception)
            self.assertTrue(any(b.label=='Confirm simulated checkout' for b in app.button))
            self.assertFalse(any('selected items**' in w.value for w in app.markdown))
            frames=[d.value for d in app.dataframe]
            self.assertTrue(any('Cart category' in f and 'Ready-made snack' in list(f['Cart category']) for f in frames))
