import unittest
from pathlib import Path
import pandas as pd
from build_usda_trial import join_sources,rank_formulations

class USDATrialTests(unittest.TestCase):
    def food(self,code,name,inputs=None):
        return dict(foodCode=code,description=name,fdcId=code,foodNutrients=[{'nutrient':{'number':'208','unitName':'kcal'},'amount':100}],inputFoods=inputs or [])

    def test_exact_join_period_and_rejection_of_unpriced_ingredient_codes(self):
        foods=[self.food(101,'Ingredient A'),self.food(102,'Ingredient B'),self.food(200,'Dish',[{'ingredientCode':101,'ingredientWeight':100},{'ingredientCode':102,'ingredientWeight':50}]),self.food(201,'Unpriced',[{'ingredientCode':101,'ingredientWeight':10},{'ingredientCode':999,'ingredientWeight':10}])]
        prices=pd.DataFrame([{'year':'2017/2018','food_code':101,'price_100gm':2},{'year':'2017/2018','food_code':102,'price_100gm':4},{'year':'2015/2016','food_code':101,'price_100gm':99}])
        catalog,records=join_sources(foods,prices)
        self.assertEqual(len(catalog),2)
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]['ingredient_batch_cost_usd'],4)
        self.assertEqual(records[0]['kcal_per_100g'],100)
        self.assertEqual(records[0]['ingredient_batch_grams'],150)
        self.assertIsNone(records[0]['prepared_food_price_per_100g_usd'])

    def test_matching_counts_override_price_tiebreak(self):
        rows=[dict(food_code=1,name='More matches',ingredients=[{'food_code':10},{'food_code':20},{'food_code':30}],ingredient_batch_cost_usd=10,kcal_per_100g=100),dict(food_code=2,name='Cheaper',ingredients=[{'food_code':10}],ingredient_batch_cost_usd=1,kcal_per_100g=50)]
        result=rank_formulations(rows,[10,20],'Lowest ingredient batch cost')
        self.assertEqual(result[0]['food_code'],1)
        self.assertEqual(result[0]['additional_count'],1)

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'data/usda_trial/manifest.json').exists(),'Import USDA data first')
    def test_trial_load_and_example_selection(self):
        from streamlit.testing.v1 import AppTest
        root=Path(__file__).resolve().parents[1]
        app=AppTest.from_file(str(root/'usda_trial.py')).run(timeout=30)
        self.assertFalse(app.exception)
        next(b for b in app.button if b.label=='Load example ingredients').click().run(timeout=30)
        self.assertFalse(app.exception)
        self.assertTrue(app.multiselect(key='usda_selected').value)
        self.assertTrue(any(m.label=='Selected ingredient total (USD)' for m in app.metric))
        self.assertTrue(any('You have picked all' in s.value for s in app.success))
        next(b for b in app.button if b.label=='Reset USDA trial').click().run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(app.multiselect(key='usda_selected').value,[])
