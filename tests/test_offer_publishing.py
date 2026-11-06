import unittest
import pandas as pd
from offer_publishing import publish_snapshot, active_promotions

class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.offer=dict(items=['rice','tomato'],batch_ids=['r','t'],offer_price=10,discount_pct=10,original_price=12,cost=8,quantity_description='one pack each')
        self.inventory=pd.DataFrame([dict(ingredient_name='rice',batch_id='r',expiry_date='2026-12-01'),dict(ingredient_name='tomato',batch_id='t',expiry_date='2026-11-07')])

    def test_publish_caps_expiry_and_pause_blocks(self):
        saved=publish_snapshot([self.offer],self.inventory,'2026-11-10','2026-11-05')
        self.assertEqual(saved[0]['valid_until'],'2026-11-07')
        self.assertEqual(len(active_promotions(saved,[self.offer],'2026-11-05')),1)
        self.assertEqual(active_promotions(saved,[self.offer],'2026-11-07'),[])
        saved[0]['paused']=True
        self.assertEqual(active_promotions(saved,[self.offer],'2026-11-05'),[])

    def test_draft_price_changes_require_republishing(self):
        saved=publish_snapshot([self.offer],self.inventory,'2026-11-10','2026-11-05')
        draft=dict(self.offer,offer_price=9)
        self.assertEqual(active_promotions(saved,[draft],'2026-11-05'),[])
        self.assertEqual(active_promotions([], [self.offer], '2026-11-05'),[])
        with self.assertRaises(ValueError):publish_snapshot([self.offer],self.inventory,'2026-11-05','2026-11-05')

class PromotionHistoryTests(unittest.TestCase):
    def test_history_records_changes_once_and_search_sorts(self):
        import tempfile
        from pathlib import Path
        from offer_publishing import record_promotion_changes, promotion_history, browse_promotions
        offer=dict(promotion_id='one',items=['rice','tomato'],batch_ids=['r','t'],offer_price=10,savings=3,discount_pct=20,valid_until='2026-11-07')
        other=dict(offer,promotion_id='two',items=['onion'],batch_ids=['o'],offer_price=5,savings=1,valid_until='2026-11-06')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'published_offers.json'
            record_promotion_changes(path,[],[offer],'Published','2026-11-05')
            record_promotion_changes(path,[offer],[offer],'Published','2026-11-05')
            paused=dict(offer,paused=True)
            record_promotion_changes(path,[offer],[paused],'Paused','2026-11-05')
            self.assertEqual([e['action'] for e in promotion_history(path)],['Published','Paused'])
        self.assertEqual(browse_promotions([offer,other],' TOMATO '),[offer])
        self.assertEqual(browse_promotions([other,offer])[0],offer)
        self.assertEqual(browse_promotions([offer,other],sort_by='Ending soon')[0],other)
