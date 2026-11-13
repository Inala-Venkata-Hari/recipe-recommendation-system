"""Validate local imported data when present; raw sources are not redistributed."""
import ast
import json
from pathlib import Path
import unittest
import pandas as pd
from recipe_costs import add_recipe_cost_estimates
from build_price_compatible_recipes import filter_recipes

DATA=Path(__file__).resolve().parents[1]/'data/price_compatible_recipes'

@unittest.skipUnless((DATA/'recipes_cleaned.csv').exists(),'Run source imports to validate local real-data profile')
class PricedProfileTests(unittest.TestCase):
    def test_every_retained_recipe_has_full_price_and_quantity_coverage(self):
        recipes=pd.read_csv(DATA/'recipes_cleaned.csv')
        catalog=pd.read_csv(DATA/'ingredient_catalog.csv')
        self.assertFalse(recipes.empty)
        kept,excluded,_=filter_recipes(recipes,catalog)
        self.assertEqual(len(kept),len(recipes))
        self.assertTrue(excluded.empty)
        recipes['ingredient_quantities']=recipes.ingredient_quantities.map(ast.literal_eval)
        priced=add_recipe_cost_estimates(recipes,catalog)
        self.assertTrue(priced.estimated_cost.notna().all())
        self.assertTrue((priced.estimated_cost>0).all())
        self.assertTrue(recipes.calories_per_serving.isna().all())

    def test_catalog_retains_verifiable_pack_price_provenance(self):
        catalog=pd.read_csv(DATA/'ingredient_catalog.csv')
        self.assertTrue(catalog.product_url.str.startswith('https://www.bigbasket.com/').all())
        expected=catalog.listed_pack_price*100/catalog.pack_grams
        self.assertTrue((expected-catalog.price_per_100g).abs().lt(1e-8).all())
        self.assertTrue(catalog.mapping_method.isin(['Explicit named-product mapping','Literal name match']).all())
