import unittest
from usda_workflow import purchase_plan

class PurchasePlanTests(unittest.TestCase):
    def test_round_up_and_leftovers(self):
        row=purchase_plan({1:120},{1:500})[0]
        self.assertEqual((row['packs'],row['purchased_g'],row['leftover_g']),(1,500,380))
        self.assertEqual(purchase_plan({1:501},{1:500})[0]['packs'],2)
        self.assertEqual(purchase_plan({1:500},{1:500})[0]['packs'],1)
    def test_invalid_values(self):
        for required,size in [(0,100),(100,0),(float('nan'),100),(100,float('inf'))]:
            with self.assertRaises(ValueError):purchase_plan({1:required},{1:size})
    def test_checkout_charges_full_pack(self):
        import pandas as pd
        from usda_workflow import customer_lines
        catalog=pd.DataFrame([{'food_code':1,'name':'Rice','price_per_100g_usd':2}])
        lines=customer_lines({1:120},[],[],pd.DataFrame(),catalog,pack_sizes={1:500})
        self.assertEqual(lines[0]['Payable (USD)'],10)
        self.assertEqual(lines[0]['Quantity'],'1 × 500 g (500 g)')
    def test_seller_pack_price_reaches_checkout(self):
        import pandas as pd
        from usda_workflow import pack_price_rate,customer_lines,effective_catalog
        reference=pd.DataFrame([{'food_code':1,'name':'Rice','price_per_100g_usd':2}])
        override=pd.DataFrame([{'food_code':1,'selling_price_per_100g_usd':pack_price_rate(500,3.49)}])
        catalog=effective_catalog(reference,override)
        lines=customer_lines({1:120},[],[],pd.DataFrame(),catalog,pack_sizes={1:500})
        self.assertEqual(lines[0]['Payable (USD)'],3.49)
        self.assertEqual(catalog.iloc[0].price_basis,'Seller-entered price')
        for weight,price in [(0,2),(500,-1),(500,float('nan'))]:
            with self.assertRaises(ValueError):pack_price_rate(weight,price)
