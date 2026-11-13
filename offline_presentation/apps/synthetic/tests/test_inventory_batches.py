import unittest
import pandas as pd
from inventory_batches import create_batch
from inventory_discounts import score_inventory

class BatchCreationTests(unittest.TestCase):
    def setUp(self):
        self.catalog=pd.DataFrame({'ingredient_name':['rice'],'price_per_100g':[6]})
        self.args=[self.catalog,pd.DataFrame(),' RICE ','NEW-1',50,10,4,'2026-11-01','2026-11-10',2,7,7,'2026-11-05']

    def test_price_unit_and_frequency_integration(self):
        row=create_batch(*self.args)
        self.assertEqual(row['unit_price'],6)
        self.assertEqual(row['stock_unit'],'100 g pack')
        classified=pd.DataFrame({'ingredient_name':['rice'],'frequency_ratio':[.02]})
        scored=score_inventory(pd.DataFrame([row]),today='2026-11-05',classified=classified)
        self.assertEqual(scored.iloc[0].classification_multiplier,1.3)

    def test_duplicate_expired_and_no_margin_rejected(self):
        for index,value in [(3,''),(6,6),(8,'2026-11-05')]:
            args=list(self.args);args[index]=value
            with self.assertRaises(ValueError):create_batch(*args)
        args=list(self.args);args[1]=pd.DataFrame({'batch_id':['NEW-1']})
        with self.assertRaises(ValueError):create_batch(*args)
