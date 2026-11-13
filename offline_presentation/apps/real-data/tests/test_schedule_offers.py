import unittest
import pandas as pd
from schedule_offers import recipe_fits_schedule, schedule_offer_matches
from offer_publishing import promotion_id

class ScheduleOfferTests(unittest.TestCase):
    def test_time_boundaries_and_missing_data(self):
        self.assertTrue(recipe_fits_schedule({'minutes':30},'Busy / short break'))
        self.assertFalse(recipe_fits_schedule({'minutes':31},'Busy / short break'))
        self.assertTrue(recipe_fits_schedule({'minutes':20},'Late study/work'))
        self.assertFalse(recipe_fits_schedule({},'Late study/work'))
        self.assertFalse(recipe_fits_schedule({},'Family meal'))
        self.assertTrue(recipe_fits_schedule({'servings':2},'Family meal'))
        self.assertTrue(recipe_fits_schedule({'ingredients':['LENTILS']},'After workout'))

    def test_offer_requires_all_bundle_ingredients_in_a_matching_recipe(self):
        offers=[dict(items=['rice','onion'],batch_ids=['r','o']),dict(items=['rice','chicken'],batch_ids=['r','c'])]
        recipes=pd.DataFrame([dict(name='Fast rice',ingredients=['rice','onion'],minutes=20),dict(name='Slow chicken',ingredients=['rice','chicken'],minutes=50)])
        matched=schedule_offer_matches(offers,recipes,'Busy / short break')
        self.assertEqual(matched,{promotion_id(offers[0]):['Fast rice']})
        self.assertEqual(schedule_offer_matches(offers,recipes,'No schedule preference'),{})
