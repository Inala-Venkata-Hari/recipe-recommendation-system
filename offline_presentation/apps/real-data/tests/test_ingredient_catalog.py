import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from preprocess import update_ingredient_catalog


class IngredientCatalogGenerationTests(unittest.TestCase):
    def test_adds_new_items_and_preserves_existing_prices(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            existing = pd.DataFrame([
                {"ingredient_name": "rice", "price_per_100g": 6.5, "kcal_per_100g": 130},
            ])
            existing.to_csv(data_dir / "ingredient_catalog.csv", index=False)

            with patch("preprocess.DATA_DIR", data_dir):
                added = update_ingredient_catalog(["rice", "tomato", "onion"])

            catalog = pd.read_csv(data_dir / "ingredient_catalog.csv").set_index("ingredient_name")
            self.assertEqual(added, 2)
            self.assertEqual(catalog.loc["rice", "price_per_100g"], 6.5)
            self.assertTrue(pd.isna(catalog.loc["tomato", "price_per_100g"]))
            self.assertTrue(pd.isna(catalog.loc["onion", "price_per_100g"]))

    def test_normalized_existing_name_prevents_duplicate_row(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            pd.DataFrame([
                {"ingredient_name": "white-rice", "price_per_100g": 5, "kcal_per_100g": 120},
            ]).to_csv(data_dir / "ingredient_catalog.csv", index=False)

            with patch("preprocess.DATA_DIR", data_dir):
                added = update_ingredient_catalog(["white rice"])

            catalog = pd.read_csv(data_dir / "ingredient_catalog.csv")
            self.assertEqual(added, 0)
            self.assertEqual(len(catalog), 1)


if __name__ == "__main__":
    unittest.main()
