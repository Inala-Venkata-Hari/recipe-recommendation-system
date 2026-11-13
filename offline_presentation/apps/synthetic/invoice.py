"""Self-contained, printable invoice for simulated checkout."""
from html import escape
from decimal import Decimal
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4


def render_invoice(lines, assessment_date, invoice_number=None):
    number = invoice_number or 'SC-' + uuid4().hex[:10].upper()
    issued = datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%d %b %Y, %I:%M %p IST')
    regular = sum(Decimal(str(row['Regular (INR)'])) for row in lines)
    payable = sum(Decimal(str(row['Payable (INR)'])) for row in lines)
    def money(value):
        return f'₹{Decimal(str(value)):,.2f}'
    rows = []
    for index, row in enumerate(lines, 1):
        batch = escape(str(row.get('Batches', '')))
        detail = f'<small>Batch: {batch}</small>' if batch else ''
        rows.append(f'''<tr><td>{index:02}</td><td><strong>{escape(str(row['Item']))}</strong>{detail}</td>
<td>{escape(str(row['Quantity']))}</td><td class="number">{money(row['Regular (INR)'])}</td>
<td class="number">{money(row['Savings (INR)'])}</td><td class="number">{money(row['Payable (INR)'])}</td></tr>''')
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Cart Invoice {escape(number)}</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#eef2f6;color:#172b3a;font:14px Arial,sans-serif;line-height:1.5}}
.invoice{{max-width:960px;margin:24px auto;background:white;padding:38px;border:1px solid #dde4e9;border-radius:12px}}
header{{display:flex;justify-content:space-between;gap:20px;border-bottom:3px solid #167565;padding-bottom:22px}}
h1{{font-size:27px;margin:0;color:#167565}}h2{{font-size:22px;margin:0}}p{{margin:5px 0}}.muted,small{{color:#596c7a}}small{{display:block;font-size:11px}}.meta{{text-align:right}}
.badge{{display:inline-block;background:#fff2ce;color:#725400;padding:5px 10px;border-radius:5px;font-size:11px;font-weight:bold;letter-spacing:1px}}
.details{{margin:22px 0;display:flex;justify-content:space-between;gap:20px}}table{{width:100%;border-collapse:collapse}}th{{background:#edf6f3;color:#24574c;text-align:left;font-size:11px;text-transform:uppercase;padding:12px 9px}}td{{padding:13px 9px;border-bottom:1px solid #e8edf1;vertical-align:top}}.number{{text-align:right;white-space:nowrap}}
.totals{{width:340px;max-width:100%;margin:24px 0 24px auto}}.total-row{{display:flex;justify-content:space-between;padding:7px 0}}.savings{{color:#167565}}.grand{{font-size:21px;font-weight:bold;border-top:2px solid #167565;padding-top:12px}}
footer{{border-top:1px solid #dde4e9;padding-top:16px;font-size:12px;color:#596c7a}}button{{background:#167565;color:white;border:0;border-radius:6px;padding:11px 18px;cursor:pointer}}.toolbar{{max-width:960px;margin:20px auto;text-align:right}}
@media(max-width:650px){{.invoice{{padding:16px;margin:8px}}header,.details{{flex-direction:column}}.meta{{text-align:left}}.table-wrap{{overflow-x:auto}}}}
@media print{{@page{{size:A4;margin:14mm}}body{{background:white}}.invoice{{border:0;margin:0;padding:0;max-width:none}}.toolbar{{display:none}}thead{{display:table-header-group}}tr{{break-inside:avoid}}footer,.totals{{break-inside:avoid}}}}
</style></head><body><div class="toolbar"><button onclick="window.print()">Print / Save as PDF</button></div>
<main class="invoice"><header><div><h1>SMART CART</h1><p class="muted">Recipe &amp; combo offers</p><span class="badge">SIMULATED CHECKOUT</span></div>
<div class="meta"><h2>INVOICE</h2><p><strong>{escape(number)}</strong></p><p class="muted">Issued {issued}</p></div></header>
<section class="details"><div><strong>Customer</strong><p>Demo customer</p><p class="muted">Currency: INR</p></div><div><strong>Offer assessment date</strong><p>{escape(str(assessment_date))}</p><p class="muted">One confirmed cart snapshot</p></div></section>
<div class="table-wrap"><table><thead><tr><th>#</th><th>Item / combo</th><th>Quantity</th><th class="number">Regular</th><th class="number">Discount</th><th class="number">Amount</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<section class="totals"><div class="total-row"><span>Regular subtotal</span><span>{money(regular)}</span></div><div class="total-row savings"><span>Combo savings</span><span>−{money(regular-payable)}</span></div><div class="total-row grand"><span>Demo total</span><span>{money(payable)}</span></div></section>
<footer><strong>Demonstration document — not a tax invoice or proof of payment.</strong><p>No payment was collected and no inventory was reserved or deducted. Bundle amounts apply to the quantities shown. Other quantities use catalog estimates. Taxes and delivery charges are not calculated.</p></footer></main></body></html>'''
