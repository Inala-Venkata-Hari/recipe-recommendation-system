import unittest
import pandas as pd
from inventory_discounts import score_inventory, generate_combo_offers

TODAY = '2026-11-05'

def batch(name='a', **kwargs):
    return dict(ingredient_name=name, stock_qty=100, required_qty=20,
                unit_cost=7, unit_price=10, **kwargs)

class AgeDiscountTests(unittest.TestCase):
    def test_older_stock_has_higher_urgency(self):
        rows = [batch('old', received_date='2026-10-20', target_holding_days=20),
                batch('new', received_date='2026-11-04', target_holding_days=20)]
        scores = score_inventory(pd.DataFrame(rows), TODAY)
        self.assertGreater(scores.iloc[0].urgency_score, scores.iloc[1].urgency_score)

    def test_expired_today_future_receipts_and_invalid_dates_excluded(self):
        rows = [batch('expired', expiry_date=TODAY),
                batch('future', received_date='2026-11-06'),
                batch('invalid', expiry_date='oops')]
        self.assertFalse(score_inventory(pd.DataFrame(rows), TODAY).eligible.any())
        self.assertEqual(generate_combo_offers(pd.DataFrame(rows), today=TODAY), [])

    def test_zero_sales_and_no_surplus_can_still_need_markdown(self):
        row = batch(expiry_date='2026-11-06', avg_daily_sales=0, markdown_window_days=5)
        row['required_qty'] = 100
        scores = score_inventory(pd.DataFrame([row]), TODAY)
        self.assertTrue(scores.iloc[0].eligible)
        self.assertAlmostEqual(scores.iloc[0].urgency_score, (.4*.8+.25)/.65)

    def test_rounding_preserves_margin(self):
        rows = [batch('a'), batch('b')]
        offers = generate_combo_offers(pd.DataFrame(rows), max_discount=90, minimum_margin_pct=17, today=TODAY)
        for offer in offers:
            revenue = 20*(1-offer['discount_pct']/100)
            self.assertGreaterEqual((revenue-14)/revenue, .17)

    def test_earliest_expiry_batch_used_once(self):
        rows = [batch('a', batch_id='late', expiry_date='2026-12-01'),
                batch('a', batch_id='early', expiry_date='2026-11-06'), batch('b')]
        offers = generate_combo_offers(pd.DataFrame(rows), today=TODAY)
        self.assertEqual(len(offers), 1)
        self.assertIn('early', offers[0]['batch_ids'])
        self.assertNotIn('late', offers[0]['batch_ids'])

    def test_nonfinite_numeric_data_excluded(self):
        row = batch()
        row['stock_qty'] = float('inf')
        self.assertFalse(score_inventory(pd.DataFrame([row]), TODAY).iloc[0].eligible)
