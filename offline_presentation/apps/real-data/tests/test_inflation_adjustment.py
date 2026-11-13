import unittest
import pandas as pd
from inflation_adjustment import inflation_reference,SNAPSHOT
from usda_workflow import effective_catalog

class InflationTests(unittest.TestCase):
    def test_reference_adjusted_once_and_source_preserved(self):
        source=pd.DataFrame([{'food_code':1,'price_per_100g_usd':2}])
        result=inflation_reference(source)
        self.assertAlmostEqual(result.iloc[0].price_per_100g_usd,2*336.940/248.1135)
        self.assertEqual(source.iloc[0].price_per_100g_usd,2)
        self.assertEqual(inflation_reference(result).iloc[0].price_per_100g_usd,result.iloc[0].price_per_100g_usd)
        self.assertEqual(result.iloc[0].source_price_per_100g_usd,2)
        self.assertEqual(inflation_reference(source,False).iloc[0].price_per_100g_usd,2)
    def test_seller_price_not_inflated(self):
        source=pd.DataFrame([{'food_code':1,'price_per_100g_usd':2},{'food_code':2,'price_per_100g_usd':1}])
        overrides=pd.DataFrame([{'food_code':1,'selling_price_per_100g_usd':3.49}])
        result=effective_catalog(inflation_reference(source),overrides)
        self.assertEqual(result.iloc[0].price_per_100g_usd,3.49)
        self.assertEqual(result.iloc[0].price_basis,'Seller-entered price')
        self.assertIn('CPI-adjusted',result.iloc[1].price_basis)
    def test_invalid_index(self):
        with self.assertRaises(ValueError):inflation_reference(pd.DataFrame({'price_per_100g_usd':[1]}),snapshot={**SNAPSHOT,'base_index':0})
