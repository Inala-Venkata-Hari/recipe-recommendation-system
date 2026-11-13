import unittest
import pandas as pd
from import_bigbasket import pack_grams
from build_price_compatible_recipes import filter_recipes,build_price_catalog

class RealPriceCompatibilityTests(unittest.TestCase):
    def test_ambiguous_packages_are_rejected(self):
        for value in ['Rice 500 g + Dal 500 g','Carrot 500 g each','Baby pants 12-17 kg','20g Whey Protein Bar','Cookies 100 g + 20 g free','Mutton 8-10 Kgs']:
            self.assertIsNone(pack_grams(value),value)
        self.assertEqual(pack_grams('Peanut Butter - Chunky 510 gm Jar'),510)
        self.assertIsNone(pack_grams('Milk 500 ml'))

    def test_all_ingredients_need_prices_and_weights(self):
        recipes=pd.DataFrame([
            dict(id='ok',name='Fully priced',ingredients="['rice']",ingredient_quantities="[{'name':'rice','quantity_g':100}]"),
            dict(id='missing',name='Unpriced salt',ingredients="['rice','salt']",ingredient_quantities="[{'name':'rice','quantity_g':100},{'name':'salt','quantity_g':1}]"),
            dict(id='unknown',name='Unknown weight',ingredients="['rice']",ingredient_quantities="[{'name':'rice','quantity_g':None}]"),
        ])
        catalog=pd.DataFrame({'ingredient_name':['rice'],'price_per_100g':[6]})
        kept,excluded,missing=filter_recipes(recipes,catalog)
        self.assertEqual(kept.id.tolist(),['ok'])
        self.assertEqual(len(excluded),2)
        self.assertEqual(missing['salt'],1)

    def test_catalog_uses_observed_pack_price_not_synthetic_rates(self):
        products=pd.DataFrame([dict(product_name='American Garden Peanut Butter - Chunky 510 gm Jar',grocery_candidate=True,sale_price=399,source_product_id='123')])
        catalog=build_price_catalog(products,['peanut butter','rice'])
        self.assertEqual(catalog.ingredient_name.tolist(),['peanut butter'])
        self.assertAlmostEqual(catalog.iloc[0].price_per_100g,399*100/510)
        self.assertTrue(pd.isna(catalog.iloc[0].kcal_per_100g))
