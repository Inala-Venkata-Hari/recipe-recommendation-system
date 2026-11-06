import unittest
import pandas as pd
from catalog_import import merge_catalog

class CatalogImportTests(unittest.TestCase):
    def test_merge_preserves_unmentioned_rows_and_omitted_calories(self):
        base=pd.DataFrame([dict(ingredient_name='rice',price_per_100g=6,kcal_per_100g=350),dict(ingredient_name='onion',price_per_100g=4,kcal_per_100g=40)])
        result=merge_catalog(base,pd.DataFrame({'ingredient_name':[' RICE ','lentils'],'price_per_100g':[8,12]})).set_index('ingredient_name')
        self.assertEqual(result.loc['rice','price_per_100g'],8)
        self.assertEqual(result.loc['rice','kcal_per_100g'],350)
        self.assertEqual(result.loc['onion','price_per_100g'],4)
        self.assertIn('lentils',result.index)

    def test_invalid_inputs_rejected(self):
        for values in [[-1],['oops'],[float('inf')]]:
            with self.assertRaises(ValueError):
                merge_catalog(pd.DataFrame(),pd.DataFrame({'ingredient_name':['rice'],'price_per_100g':values}))
        with self.assertRaises(ValueError):
            merge_catalog(pd.DataFrame(),pd.DataFrame({'ingredient_name':['rice',' RICE '],'price_per_100g':[1,2]}))

    def test_blank_price_clears_value(self):
        base=pd.DataFrame({'ingredient_name':['rice'],'price_per_100g':[6],'kcal_per_100g':[350]})
        result=merge_catalog(base,pd.DataFrame({'ingredient_name':['rice'],'price_per_100g':['']}))
        self.assertTrue(pd.isna(result.iloc[0].price_per_100g))
