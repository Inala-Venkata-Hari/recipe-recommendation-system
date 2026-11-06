"""Published offers remain snapshots; changed draft offers require republishing."""
import json
import hashlib
from pathlib import Path
import pandas as pd


def promotion_id(offer):
    pairs = sorted(zip(offer['items'], offer['batch_ids']))
    return hashlib.sha256(json.dumps(pairs).encode()).hexdigest()[:16]


def publish_snapshot(offers, inventory, until, today):
    until = pd.Timestamp(until).normalize()
    if until <= pd.Timestamp(today).normalize():
        raise ValueError('Offer end date must follow the assessment date.')
    result = []
    for offer in offers:
        expiry_dates = []
        for name, batch in zip(offer['items'], offer['batch_ids']):
            rows = inventory[inventory.ingredient_name == name]
            if 'batch_id' in rows:
                rows = rows[rows.batch_id.astype(str) == batch]
            if len(rows) != 1:
                raise ValueError('Publishing requires uniquely identifiable inventory batches.')
            expiry = pd.to_datetime(rows.iloc[0].get('expiry_date'), errors='coerce')
            if pd.notna(expiry):
                expiry_dates.append(expiry.normalize())
        end = min([until] + expiry_dates)
        if end <= pd.Timestamp(today).normalize():
            raise ValueError('Cannot publish expired inventory.')
        result.append(dict(offer, promotion_id=promotion_id(offer), valid_until=end.date().isoformat(), paused=False))
    return result


def active_promotions(published, drafts, today):
    current = {promotion_id(o): o for o in drafts}
    active = []
    for offer in published:
        draft = current.get(offer['promotion_id'])
        if offer.get('paused') or pd.Timestamp(offer['valid_until']) <= pd.Timestamp(today).normalize():
            continue
        if draft is None:
            continue
        if any(offer.get(field) != draft.get(field) for field in ['offer_price','discount_pct','original_price','cost','quantity_description']):
            continue
        active.append(offer)
    return active


def save_promotions(path, offers):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(offers, indent=2))
    temporary.replace(path)


def load_promotions(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return []


def promotion_history(path):
    history_path = Path(path).with_name('offer_history.json')
    try:
        return json.loads(history_path.read_text())
    except FileNotFoundError:
        return []


def record_promotion_changes(path, before, after, action, assessment_date):
    """Record changed promotions; repeated identical publication is not a new event."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    previous = {o['promotion_id']: o for o in before}
    changed = [o for o in after if previous.get(o['promotion_id']) != o]
    if not changed:
        return
    events = promotion_history(path)
    timestamp = datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(timespec='seconds')
    for offer in changed:
        events.append(dict(timestamp=timestamp, assessment_date=str(assessment_date), action=action,
                           promotion_id=offer['promotion_id'], items=' + '.join(offer['items']),
                           price=offer['offer_price'], discount_pct=offer['discount_pct'],
                           valid_until=offer['valid_until']))
    history_path = Path(path).with_name('offer_history.json')
    temporary = history_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(events, indent=2))
    temporary.replace(history_path)


def browse_promotions(offers, query='', sort_by='Highest savings'):
    """Search ingredient names and order only the active offers supplied by caller."""
    query = query.strip().casefold()
    result = [o for o in offers if not query or query in ' '.join(o['items']).casefold()]
    if sort_by == 'Lowest bundle price':
        return sorted(result, key=lambda o: (o['offer_price'], promotion_id(o)))
    if sort_by == 'Ending soon':
        return sorted(result, key=lambda o: (o['valid_until'], -o['savings'], promotion_id(o)))
    return sorted(result, key=lambda o: (-o['savings'], o['offer_price'], promotion_id(o)))
