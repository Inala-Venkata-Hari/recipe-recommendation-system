import unittest
from pathlib import Path
from datetime import date
import numpy as np
import pandas as pd
from ml_inventory import load_model,predict_risk
from inventory_discounts import score_inventory,generate_combo_offers

class InventoryMLTests(unittest.TestCase):
    def test_heldout_metrics_and_provenance(self):
        model=load_model()
        self.assertIn('SYNTHETIC',model['training_origin'])
        self.assertEqual(model['training_rows'],7560)
        metrics=model['evaluation']['test']
        self.assertLess(metrics['mae'],metrics['constant_baseline_mae'])
        self.assertEqual(metrics['rows'],1620)
    def test_prediction_uses_stock_and_sales(self):
        base=dict(stock_qty=100,avg_daily_sales=2,days_remaining=3,days_in_stock=5,target_holding_days=7,frequency_ratio=.2)
        risks=predict_risk([base,dict(base,avg_daily_sales=30)],load_model())
        self.assertTrue(np.isfinite(risks).all())
        self.assertTrue(((risks>=0)&(risks<=1)).all())
        self.assertGreater(risks[0],risks[1])
    def test_ml_pipeline_preserves_expiry_and_margin(self):
        root=Path(__file__).resolve().parents[1]
        inventory=pd.read_csv(root/'data/synthetic_demo/seller_inventory.csv')
        scored=score_inventory(inventory,today='2026-11-05',scoring_mode='ml')
        self.assertIn('rule_priority',scored)
        self.assertIn('predicted_unsold_fraction',scored)
        self.assertTrue(np.allclose(scored.discount_priority,scored.predicted_unsold_fraction))
        expired=pd.to_datetime(scored.expiry_date)<=pd.Timestamp('2026-11-05')
        self.assertFalse(scored.loc[expired,'eligible'].any())
        offers=generate_combo_offers(inventory,today=date(2026,11,5),scoring_mode='ml',minimum_margin_pct=5,max_discount=15)
        self.assertTrue(offers)
        self.assertTrue(all(o['margin_pct']>=5-1e-8 for o in offers))
        self.assertTrue(all(o['discount_pct']<=15 for o in offers))
        self.assertTrue(all(o['scoring_mode']=='ml' for o in offers))
