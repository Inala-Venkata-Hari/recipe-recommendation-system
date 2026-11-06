"""Validate and merge uploaded per-100g catalog data."""
import pandas as pd
import math
from ingredient_normalization import normalize_ingredient


def merge_catalog(existing, uploaded):
    required = {'ingredient_name', 'price_per_100g'}
    if not required.issubset(uploaded.columns) or uploaded.empty:
        raise ValueError('CSV needs ingredient_name and price_per_100g columns and at least one row.')
    columns = ['ingredient_name','price_per_100g','kcal_per_100g']
    data = uploaded[[c for c in columns if c in uploaded]].copy()
    data['ingredient_name'] = data.ingredient_name.fillna('').map(normalize_ingredient)
    if data.ingredient_name.eq('').any():
        raise ValueError('Every row needs an ingredient name.')
    if data.ingredient_name.duplicated().any():
        raise ValueError('Duplicate ingredient names after normalization; keep one row per ingredient.')
    for column in columns[1:]:
        if column not in data:
            continue
        raw = data[column]
        numbers = pd.to_numeric(raw, errors='coerce')
        blank = raw.isna() | raw.astype(str).str.strip().eq('')
        invalid = (~blank & numbers.isna()) | numbers.map(lambda n: pd.notna(n) and (not math.isfinite(float(n)) or n < 0))
        if invalid.any():
            raise ValueError(f'{column} must contain finite non-negative numbers or blanks.')
        data[column] = numbers
    base = existing.reindex(columns=columns).copy()
    base['ingredient_name'] = base.ingredient_name.fillna('').map(normalize_ingredient)
    base = base.drop_duplicates('ingredient_name').set_index('ingredient_name')
    for row in data.to_dict('records'):
        name = row.pop('ingredient_name')
        if name not in base.index:
            base.loc[name] = [float('nan'),float('nan')]
        for column,value in row.items():
            base.loc[name,column] = value
    return base.reset_index()[columns]
