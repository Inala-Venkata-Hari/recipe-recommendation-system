"""Session-only checkout: no payment, reservation or persistent stock mutation."""
import math
import re
from ingredient_normalization import normalize_ingredient


def offer_key(offer):
    return tuple(zip(offer['items'], offer['batch_ids']))


def validate_bundles(chosen, current_offers, inventory, quantities):
    current = {offer_key(o): o for o in current_offers}
    used = set()
    validated = []
    for saved in chosen:
        offer = current.get(offer_key(saved))
        if offer is None or offer['offer_price'] != saved['offer_price'] or offer['discount_pct'] != saved['discount_pct'] or offer.get('quantities_g',{}) != saved.get('quantities_g',{}):
            raise ValueError('An offer changed or expired. Remove it and choose a current offer.')
        names = {normalize_ingredient(n) for n in offer['items']}
        if used & names:
            raise ValueError('Overlapping combos cannot discount the same ingredient twice.')
        for name, batch in zip(offer['items'], offer['batch_ids']):
            rows = inventory[inventory.ingredient_name == name]
            if 'batch_id' in rows:
                rows = rows[rows.batch_id.astype(str) == batch]
            unit=re.fullmatch(r'([0-9]+(?:\.[0-9]+)?) g pack',str(rows.iloc[0].get('stock_unit',''))) if len(rows)==1 else None
            grams=float(offer.get('quantities_g',{}).get(name,100))
            if unit is None or float(unit.group(1))!=grams:
                raise ValueError('Checkout requires a unique batch and a defined 100 g pack unit.')
            if float(rows.iloc[0].stock_qty) < 1:
                raise ValueError('Not enough stock for this combo.')
            if quantities.get(normalize_ingredient(name), 0)+1e-8 < grams:
                raise ValueError('Keep at least one full pack of each combo ingredient in the cart.')
        used |= names
        validated.append(offer)
    return validated


def checkout_lines(quantities, rates, chosen, current_offers, inventory, currency="INR"):
    if currency not in {"INR", "USD"}:
        raise ValueError("Unsupported checkout currency.")
    validated = validate_bundles(chosen, current_offers, inventory, quantities)
    remaining = dict(quantities)
    lines = []
    for offer in validated:
        for name in offer['items']:
            remaining[normalize_ingredient(name)] -= float(offer.get('quantities_g',{}).get(name,100))
        lines.append({'Item': ' + '.join(offer['items']), 'Quantity': offer['quantity_description'],
                      f'Regular ({currency})': offer['original_price'], f'Payable ({currency})': offer['offer_price'],
                      f'Savings ({currency})': offer['savings'], 'Batches': ', '.join(offer['batch_ids']), 'Pack weights':offer.get('quantities_g',{})})
    for name, grams in remaining.items():
        if not math.isfinite(grams) or grams < 0:
            raise ValueError('Cart quantities must be finite and positive.')
        if grams == 0:
            continue
        rate = rates.get(name)
        if rate is None or not math.isfinite(rate) or rate < 0:
            raise ValueError(f'Price unavailable for {name}; checkout total cannot be calculated.')
        amount = round(rate * grams / 100, 2)
        lines.append({'Item': name, 'Quantity': f'{grams:g} g', f'Regular ({currency})': amount,
                      f'Payable ({currency})': amount, f'Savings ({currency})': 0.0, 'Batches': ''})
    return lines


def best_missing_combos(items, offers, inventory, chosen=()):
    """Exact maximum-savings selection of disjoint bundles on eligible items."""
    missing = {normalize_ingredient(n) for n in items}
    occupied = {normalize_ingredient(n) for o in chosen for n in o['items']}
    quantities = {n: 100.0 for n in missing}
    states = {frozenset(): (0, [])}
    for offer in offers:
        names = frozenset(normalize_ingredient(n) for n in offer['items'])
        if not names or not names.issubset(missing) or names & occupied:
            continue
        try:
            validate_bundles([offer], offers, inventory, {**quantities,**offer.get('quantities_g',{})})
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


def relevant_recipe_offers(required_items,missing_items,offers):
    """Useful offers cover a missing item without introducing unrelated ingredients."""
    required={normalize_ingredient(str(item)) for item in required_items}
    missing={normalize_ingredient(str(item)) for item in missing_items}
    return sorted([offer for offer in offers
                   if {normalize_ingredient(str(item)) for item in offer['items']}.issubset(required)
                   and {normalize_ingredient(str(item)) for item in offer['items']}.intersection(missing)],
                  key=lambda offer:(-offer['savings'],tuple(str(i) for i in offer['items'])))
