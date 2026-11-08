import unittest
import pandas as pd
from import_bigbasket_quantity import quantity_grams,normalize_products
from build_price_compatible_recipes import build_price_catalog

class QuantityPriceSourceTests(unittest.TestCase):
    def row(self,**changes):
        data=dict(ProductName='Onion (Loose)',Brand='Fresho',Price=69.75,DiscountPrice=52.0,Quantity='2 kg',Category='Fruits & Vegetables',Absolute_Url='https://www.bigbasket.com/pd/123/onion/')
        data.update(changes);return data

    def test_quantity_field_not_nutrition_claim_controls_mass(self):
        self.assertEqual(quantity_grams('1.5 Kg'),1500)
        for value in ['1 L','6 pcs','2x500 g','500 g each','1-2 kg','0 kg']:
            self.assertIsNone(quantity_grams(value))
        products=normalize_products(pd.DataFrame([self.row()]))
        catalog=build_price_catalog(products,['onion','onions','salt'])
        self.assertEqual(set(catalog.ingredient_name),{'onion','onions'})
        self.assertTrue((catalog.price_per_100g==2.6).all())
        self.assertTrue(catalog.product_url.str.startswith('https://').all())

    def test_nonfood_invalid_price_and_volume_excluded(self):
        rows=[self.row(Category='Beauty & Hygiene'),self.row(DiscountPrice=float('inf')),self.row(Quantity='500 ml')]
        self.assertTrue(normalize_products(pd.DataFrame(rows)).empty)

    def test_title_keywords_never_create_flavour_false_matches(self):
        products=normalize_products(pd.DataFrame([self.row(ProductName='Onion Flavoured Chips')]))
        self.assertTrue(build_price_catalog(products,['onion']).empty)

    def test_misleading_product_name_is_blocked_by_source_context(self):
        product=self.row(ProductName='Pineapple',Quantity='50 g',Category='Gourmet & World Food',Absolute_Url='https://www.bigbasket.com/pd/40076825/fresho-signature-dry-fruit-pineapple-50-g/')
        products=normalize_products(pd.DataFrame([product]))
        self.assertTrue(build_price_catalog(products,['pineapple']).empty)
