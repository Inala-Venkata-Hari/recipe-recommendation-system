import json
import unittest
import tempfile
from pathlib import Path
import pandas as pd
from import_real_recipes import parse_recipe, import_recipes
from recipe_costs import add_recipe_cost_estimates

class RealRecipeTests(unittest.TestCase):
    def row(self,ingredients):
        return dict(recipe_name='Example',source='Publisher',url='https://example.org/recipe',servings=2,calories=500,cuisine_type='["indian"]',ingredients=json.dumps(ingredients))

    def test_duplicate_weights_combined_and_unknown_metadata_not_invented(self):
        row=parse_recipe(self.row([{'food':' Onion ','weight':50},{'food':'onion','weight':25}]))
        import ast
        self.assertEqual(ast.literal_eval(row['ingredient_quantities']),[{'name':'onion','quantity_g':75}])
        self.assertIsNone(row['minutes'])
        self.assertIsNone(row['calories_per_serving'])
        self.assertEqual(row['source_calories'],500)

    def test_missing_weight_does_not_become_partial_cost(self):
        row=parse_recipe(self.row([{'food':'onion','weight':50},{'food':'onion','weight':0}]))
        self.assertFalse(row['quantity_complete'])
        import ast
        row['ingredient_quantities']=ast.literal_eval(row['ingredient_quantities'])
        recipes=pd.DataFrame([row])
        catalog=pd.DataFrame({'ingredient_name':['onion'],'price_per_100g':[10]})
        self.assertTrue(pd.isna(add_recipe_cost_estimates(recipes,catalog).iloc[0].estimated_cost))

    def test_import_deduplicates_and_preserves_seller_prices(self):
        row=self.row([{'food':'onion','weight':100}])
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);source=path/'source.csv';output=path/'output'
            pd.DataFrame([row,row]).to_csv(source,index=False)
            report=import_recipes(source,output)
            self.assertEqual(report['usable_unique_recipes'],1)
            catalog=pd.read_csv(output/'ingredient_catalog.csv');catalog['price_per_100g']=5
            catalog.to_csv(output/'ingredient_catalog.csv',index=False)
            import_recipes(source,output)
            self.assertEqual(pd.read_csv(output/'ingredient_catalog.csv').iloc[0].price_per_100g,5)
            self.assertTrue(pd.read_csv(output/'seller_inventory.csv').empty)
