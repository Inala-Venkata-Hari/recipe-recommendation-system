"""Session-only checkout: no payment, reservation or persistent stock mutation."""
import math
from ingredient_normalization import normalize_ingredient


def offer_key(offer):
    return tuple(zip(offer['items'], offer['batch_ids']))


def validate_bundles(chosen, current_offers, inventory, quantities):
    current = {offer_key(o): o for o in current_offers}
    used = set()
    validated = []
    for saved in chosen:
        offer = current.get(offer_key(saved))
        if offer is None or offer['offer_price'] != saved['offer_price'] or offer['discount_pct'] != saved['discount_pct']:
            raise ValueError('An offer changed or expired. Remove it and choose a current offer.')
        names = {normalize_ingredient(n) for n in offer['items']}
        if used & names:
            raise ValueError('Overlapping combos cannot discount the same ingredient twice.')
        for name, batch in zip(offer['items'], offer['batch_ids']):
            rows = inventory[inventory.ingredient_name == name]
            if 'batch_id' in rows:
                rows = rows[rows.batch_id.astype(str) == batch]
            if len(rows) != 1 or str(rows.iloc[0].get('stock_unit', '')) != '100 g pack':
                raise ValueError('Checkout requires a unique batch and a defined 100 g pack unit.')
            if float(rows.iloc[0].stock_qty) < 1:
                raise ValueError('Not enough stock for this combo.')
            if quantities.get(normalize_ingredient(name), 0) < 100:
                raise ValueError('Keep at least 100 g of each combo ingredient in the cart.')
        used |= names
        validated.append(offer)
    return validated


def checkout_lines(quantities, rates, chosen, current_offers, inventory):
    validated = validate_bundles(chosen, current_offers, inventory, quantities)
    remaining = dict(quantities)
    lines = []
    for offer in validated:
        for name in offer['items']:
            remaining[normalize_ingredient(name)] -= 100
        lines.append({'Item': ' + '.join(offer['items']), 'Quantity': offer['quantity_description'],
                      'Regular (INR)': offer['original_price'], 'Payable (INR)': offer['offer_price'],
                      'Savings (INR)': offer['savings'], 'Batches': ', '.join(offer['batch_ids'])})
    for name, grams in remaining.items():
        if not math.isfinite(grams) or grams < 0:
            raise ValueError('Cart quantities must be finite and positive.')
        if grams == 0:
            continue
        rate = rates.get(name)
        if rate is None or not math.isfinite(rate) or rate < 0:
            raise ValueError(f'Price unavailable for {name}; checkout total cannot be calculated.')
        amount = round(rate * grams / 100, 2)
        lines.append({'Item': name, 'Quantity': f'{grams:g} g', 'Regular (INR)': amount,
                      'Payable (INR)': amount, 'Savings (INR)': 0.0, 'Batches': ''})
    return lines


def best_missing_combos(items, offers, inventory, chosen=()):
    """Exact maximum-savings selection of disjoint bundles on missing items only."""
    missing = {normalize_ingredient(n) for n in items}
    occupied = {normalize_ingredient(n) for o in chosen for n in o['items']}
    quantities = {n: 100.0 for n in missing}
    states = {frozenset(): (0, [])}
    for offer in offers:
        names = frozenset(normalize_ingredient(n) for n in offer['items'])
        if not names or not names.issubset(missing) or names & occupied:
            continue
        try:
            validate_bundles([offer], offers, inventory, quantities)
        except ValueError:
            continue
        saving = round(offer['savings'] * 100)
        if saving <= 0:
            continue
        for used, (total, bundles) in list(states.items()):
            if used & names:
                continue
            combined = used | names
            if total + saving > states.get(combined, (-1, []))[0]:
                states[combined] = (total + saving, bundles + [offer])
    return max(states.values(), key=lambda value: value[0])[1]
