"""Build seller batches using catalog prices per 100 g."""
import math
import pandas as pd
from ingredient_normalization import normalize_ingredient


def create_batch(catalog, inventory, ingredient, batch_id, stock, required, cost,
                 received, expiry, sales, holding_days, markdown_days, assessment_date, pack_size_g=100):
    if not math.isfinite(float(pack_size_g)) or pack_size_g<=0:
        raise ValueError("Pack size must be finite and positive.")
    name = normalize_ingredient(ingredient)
    matches = catalog[catalog.ingredient_name.map(normalize_ingredient) == name]
    if len(matches) != 1:
        raise ValueError('Choose an ingredient with one unique catalog entry.')
    price = pd.to_numeric(matches.iloc[0].price_per_100g, errors='coerce')
    if pd.isna(price) or not math.isfinite(float(price)) or price <= 0:
        raise ValueError('Set a positive catalog price for this ingredient first.')
    price=float(price)*pack_size_g/100
    batch_id = str(batch_id).strip()
    if not batch_id:
        raise ValueError('Batch ID is required.')
    if 'batch_id' in inventory and inventory.batch_id.astype(str).str.strip().eq(batch_id).any():
        raise ValueError('Batch ID already exists. Use a unique ID.')
    values = [stock, required, cost, sales, holding_days, markdown_days]
    if any(not math.isfinite(float(v)) or v < 0 for v in values):
        raise ValueError('Quantities, costs and timing inputs must be finite and non-negative.')
    if stock < 1 or holding_days <= 0 or markdown_days <= 0:
        raise ValueError('Stock must be at least one pack; holding and markdown days must be positive.')
    if cost >= price:
        raise ValueError('Acquisition cost must be below the catalog selling price.')
    received, expiry, assessment = map(pd.Timestamp, [received, expiry, assessment_date])
    if any(pd.isna(value) for value in [received, expiry, assessment]):
        raise ValueError("Receipt, expiry and assessment dates are required.")
    if received > assessment or expiry <= assessment or expiry <= received:
        raise ValueError('Receipt must not be in the future, and expiry must follow receipt and assessment dates.')
    return dict(ingredient_name=name, batch_id=batch_id, stock_qty=stock, required_qty=required,
                unit_cost=cost, unit_price=float(price), stock_unit=f'{pack_size_g:g} g pack',
                received_date=received.date().isoformat(), expiry_date=expiry.date().isoformat(),
                avg_daily_sales=sales, target_holding_days=holding_days, markdown_window_days=markdown_days)
