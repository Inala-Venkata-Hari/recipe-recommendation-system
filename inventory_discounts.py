"""Inventory-aware combo discount calculations for seller promotions."""
from itertools import combinations
import pandas as pd
import math
from ingredient_normalization import normalize_ingredient


def classification_parameters(classified):
    """Derive markdown multipliers from measured recipe coverage.

    Category labels in input are not trusted over numeric coverage. Conflicting
    duplicate ingredients are omitted so CSV order cannot change the policy.
    """
    lookup = {}
    if classified is None or not {"ingredient_name", "frequency_ratio"}.issubset(classified.columns):
        return lookup
    grouped = {}
    for row in classified.to_dict("records"):
        name = normalize_ingredient(row["ingredient_name"]) if pd.notna(row["ingredient_name"]) else ""
        ratio = pd.to_numeric(row["frequency_ratio"], errors="coerce")
        if not name or pd.isna(ratio) or not math.isfinite(float(ratio)) or not 0 <= ratio <= 1:
            continue
        grouped.setdefault(name, set()).add(float(ratio))
    for name, ratios in grouped.items():
        if len(ratios) != 1:
            continue
        ratio = next(iter(ratios))
        if ratio >= .25:
            category, multiplier = "Common", 1.0
        elif ratio >= .10:
            category, multiplier = "Moderately common", 1.1
        elif ratio >= .03:
            category, multiplier = "Specialized", 1.2
        else:
            category, multiplier = "Rare / recipe-specific", 1.3
        lookup[name] = (ratio, category, multiplier)
    return lookup



def score_inventory(inventory, today=None, classified=None, scoring_mode='rules', model_path=None):
    """Score batches; missing signals are omitted and weights renormalized.

    Expiry dates are exclusive: a batch expiring today is not offered.
    Quantity, daily sales, cost and price must use the same stock unit.
    """
    if inventory is None or not REQUIRED.issubset(inventory.columns):
        return pd.DataFrame()
    today = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    parameters = classification_parameters(classified)
    rows = []
    for row in inventory.to_dict("records"):
        def number(key):
            value = pd.to_numeric(row.get(key), errors="coerce")
            return float(value) if pd.notna(value) and math.isfinite(float(value)) else None

        values = {key: number(key) for key in REQUIRED - {"ingredient_name"}}
        reason = ""
        if any(v is None or v < 0 for v in values.values()):
            reason = "Invalid stock, cost or price"
        stock = values["stock_qty"] or 0
        price = values["unit_price"] or 0
        cost = values["unit_cost"] or 0
        received = pd.to_datetime(row.get("received_date"), errors="coerce")
        expiry = pd.to_datetime(row.get("expiry_date"), errors="coerce")
        for key, parsed in (("received_date", received), ("expiry_date", expiry)):
            raw = row.get(key)
            if pd.notna(raw) and str(raw).strip() and pd.isna(parsed):
                reason = "Invalid inventory date"
        if pd.notna(received) and received.normalize() > today:
            reason = "Received date is in the future"
        if pd.notna(expiry) and expiry.normalize() <= today:
            reason = "Expired or expires today"
        if pd.notna(received) and pd.notna(expiry) and expiry <= received:
            reason = "Expiry must follow received date"
        if stock < 1:
            reason = reason or "Insufficient stock for one whole stock unit"
        if price <= cost:
            reason = reason or "No positive margin"
        signals = []
        age_score = expiry_score = None
        age = None
        remaining = None
        target = number("target_holding_days")
        window = number("markdown_window_days")
        sales = number("avg_daily_sales")
        if pd.notna(received) and target is not None and target > 0:
            age = max(0, (today - received.normalize()).days)
            age_score = min(1, age / target)
            signals.append((0.35, age_score))
        if pd.notna(expiry):
            remaining = (expiry.normalize() - today).days
            if window is not None and window > 0:
                expiry_score = max(0, min(1, 1 - remaining / window))
                signals.append((0.40, expiry_score))
        surplus = max(0, (stock - (values["required_qty"] or 0)) / stock) if stock else 0
        if sales is not None and sales >= 0 and remaining is not None:
            excess = max(0, min(1, (stock - sales * max(0, remaining)) / stock)) if stock else 0
        else:
            excess = surplus
        signals.append((0.25, excess))
        urgency = sum(w * v for w, v in signals) / sum(w for w, v in signals)
        ratio, category, multiplier = parameters.get(
            normalize_ingredient(str(row["ingredient_name"])), (None, "Unclassified", 1.0))
        discount_priority = min(1.0, urgency * multiplier)
        row.update(age_score=age_score, expiry_score=expiry_score, excess_score=excess)
        row.update(frequency_ratio=ratio, classification_category=category,
                   classification_multiplier=multiplier, discount_priority=discount_priority)
        row.update(values)
        row.update(urgency_score=urgency, surplus_score=surplus, days_in_stock=age,
                   days_remaining=remaining, eligible=not reason and urgency > 0,
                   exclusion_reason=reason or ("No markdown urgency" if urgency == 0 else ""))
        rows.append(row)
    result=pd.DataFrame(rows)
    if scoring_mode not in {'rules','ml'}:raise ValueError('Unknown inventory scoring mode.')
    if scoring_mode=='ml' and not result.empty:
        from ml_inventory import load_model,predict_risk
        model=load_model(model_path)
        result['rule_priority']=result['discount_priority']
        result['predicted_unsold_fraction']=predict_risk(result.to_dict('records'),model)
        result['discount_priority']=result['predicted_unsold_fraction']
        result['urgency_score']=result['predicted_unsold_fraction']
        result['scoring_origin']=model['training_origin']
        genuine_exclusion=~result.exclusion_reason.isin(['','No markdown urgency'])
        result['eligible']=~genuine_exclusion & result.predicted_unsold_fraction.gt(0)
        result.loc[~genuine_exclusion,'exclusion_reason']=''
    return result


REQUIRED = {"ingredient_name", "stock_qty", "required_qty", "unit_cost", "unit_price"}


def generate_combo_offers(inventory, max_discount=15, min_items=2, max_items=4,
                          base_discount=3, surplus_scale=12, minimum_margin_pct=5, today=None, classified=None, scoring_mode='rules', model_path=None):
    """Score urgency and cap one-unit combo discounts at the margin floor.

    base_discount and surplus_scale are retained for call compatibility only.
    """
    if inventory is None or inventory.empty or not REQUIRED.issubset(inventory.columns):
        return []
    data = score_inventory(inventory, today=today, classified=classified, scoring_mode=scoring_mode, model_path=model_path)
    eligible = data[data["eligible"]].copy()
    # Offer only the earliest-expiring eligible batch of each ingredient.
    eligible["_expiry"] = pd.to_datetime(eligible.get("expiry_date", pd.Series(index=eligible.index, dtype=object)), errors="coerce")
    eligible["_received"] = pd.to_datetime(eligible.get("received_date", pd.Series(index=eligible.index, dtype=object)), errors="coerce")
    eligible = eligible.sort_values(["_expiry", "_received"], na_position="last").drop_duplicates("ingredient_name")
    rows = eligible.to_dict("records")
    offers = []
    for size in range(min_items, min(max_items, len(rows)) + 1):
        for combo in combinations(rows, size):
            ratios = [(x["stock_qty"] - x["required_qty"]) / max(x["stock_qty"], 1) for x in combo]
            avg_surplus = sum(ratios) / size
            urgency = sum(x["urgency_score"] for x in combo) / size
            priority = sum(x["discount_priority"] for x in combo) / size
            proposed = max(0, min(100, float(max_discount))) * priority
            revenue = sum(x["unit_price"] for x in combo)
            cost = sum(x["unit_cost"] for x in combo)
            minimum_margin = min(max(float(minimum_margin_pct), 0.0), 99.0) / 100
            # Preserve the requested margin on the discounted selling price.
            minimum_revenue_after_discount = cost / (1 - minimum_margin)
            margin_cap = max(0.0, (revenue - minimum_revenue_after_discount) / revenue * 100)
            discount = min(proposed, margin_cap)
            if discount < 0.1:
                continue
            applied_discount = math.floor(discount * 10) / 10
            # Round selling price upward to cents so currency rounding cannot break the margin floor.
            offer_price = math.ceil(round(revenue * (1 - applied_discount / 100), 10) * 100) / 100
            details = []
            for item in combo:
                signals = [("age", item["age_score"]), ("expiry", item["expiry_score"]), ("excess", item["excess_score"])]
                detail = ", ".join(f"{name} {value:.0%}" for name, value in signals if value is not None)
                details.append(f"{item['ingredient_name']}: {detail}; classification ×{item['classification_multiplier']:.1f}")
            offers.append({"items": [str(x["ingredient_name"]) for x in combo],
                           "batch_ids": [str(x.get("batch_id", "")) for x in combo],
                           "discount_priority": priority,
                           "classifications": [x["classification_category"] for x in combo],
                           "original_price": round(revenue, 2), "offer_price": offer_price,
                           "cost": round(cost, 2), "profit": round(offer_price - cost, 2),
                           "margin_pct": (offer_price - cost) / offer_price * 100,
                           "savings": round(revenue - offer_price, 2),
                           "margin_limited": margin_cap < proposed,
                           "quantity_description": " + ".join(f"1 {x.get('stock_unit', 'stock unit')} {x['ingredient_name']}" for x in combo),
                           "breakdown": "; ".join(details),
                           "discount_pct": applied_discount, "urgency_score": urgency, "surplus_score": avg_surplus,
                           "reason": f"Age/stock urgency: {urgency:.0%}; classification-adjusted priority: {priority:.0%}; one stock unit per ingredient; minimum margin retained."})
    if scoring_mode=='ml':
        for offer in offers:
            offer['scoring_mode']='ml'
            offer['reason']='ML predicted unsold fraction; model trained on simulated outcomes. Seller discount maximum and margin constraints remain rules.'
    return sorted(offers, key=lambda x: (-x["discount_priority"], -len(x["items"]), x["items"]))
