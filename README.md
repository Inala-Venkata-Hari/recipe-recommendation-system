# Smart Cart Recipe Recommendation System

A prototype that recommends recipes from ingredients selected in a smart shopping cart. Built with Python, pandas, and Streamlit.

## Run locally

Python 3.10+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
streamlit run app.py
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Dataset

Place the Food.com `RAW_recipes.csv` file beside `preprocess.py` and run `python preprocess.py`. This generates `data/recipes_cleaned.csv` (up to 5,000 recipes) and `data/ingredients_classified.csv` (unique ingredients and frequency categories). The raw dataset is not included.

## Prototype behaviour

- At least 3 selected ingredients are required before recommendations appear.
- Recipes matching at least one selected cart ingredient are included; recipes with zero overlap are excluded.
- Primary ranking: recipes using more selected cart items appear first.
- Tie-breaker: among recipes matching the same number of cart items, recipes requiring fewer additional ingredients appear first.
- Further tie-breaker: recipes with shorter cooking time appear first; missing cooking times are placed last.
- Each recipe displays the matched cart items, the match count, and the number of additional ingredients required.
- The cart selection is never changed, and missing ingredients are not shown as a shopping list.
- Results update when cart ingredients or preference change.
- Ingredient names are normalized consistently across preprocessing, loaded data, and matching: case, repeated whitespace, and common hyphen/dash variants are standardized; duplicate normalized ingredients are counted once.
- Normalization intentionally preserves descriptive words and other punctuation, so ingredients such as `rice` and `white rice` remain distinct.
- Run matching tests with `python -m unittest discover -s tests`.
- Preferences: Low calorie (up to 500 kcal), Quick meal (up to 30 minutes), Balanced meal (up to 600 kcal and 45 minutes), Budget-friendly (informational placeholder; price data is not available).
- Calories come from the first nutrition value in the source list and should be verified before health-critical use.

## Ingredient frequency categories

- Common: >=25% of sampled recipes
- Moderately common: >=10%
- Specialized: >=3%
- Rare / recipe-specific: below 3%

## Roadmap

- `v0.1.0`: initial prototype
- `v0.2.0`: improve matching and ranking
- `v0.3.0`: improve dataset and preprocessing
- `v0.4.0`: tests and error handling
- `v0.5.0`: interface and documentation improvements
- `v1.0.0`: first stable release

Research/learning prototype; not medical or price-verified advice.
