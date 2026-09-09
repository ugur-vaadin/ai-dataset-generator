"""Nordic Supply sections of FACTS.md (rendered by dsgen.facts after the generic header)."""
from __future__ import annotations


def sections(m, v) -> str:
    s = v["summaries"]
    A = m["anchors"]["case2"]
    c3 = s["case3"]
    L = []
    L.append("## Case 1 — dashboard\n")
    c1 = s["case1"]
    L.append(f"Late dispatches in {c1['last_month']} by ISO week (dispatched after the promised ship date):\n")
    L.append("| Week | Shipments | Late | Rate |\n|---|---:|---:|---:|")
    for w in c1["late_by_week"]:
        L.append(f"| {w['week']} | {w['shipments']} | {w['late']} | {w['late'] / w['shipments']:.0%} |")
    L.append(f"\nThe document's example, \"orders shipped after the promised date last month, by customer\": "
             f"**{c1['late_orders']}** orders from **{c1['late_customers']}** customers. Top ten:\n")
    L.append("| Customer | Late orders |\n|---|---:|")
    for name, n in c1["late_by_customer"]:
        L.append(f"| {name} | {n} |")
    L.append(f"\nClaims open for more than 7 days: **{c1['claims_open_over_7_days']}** "
             f"(open in total: {sum(s['distributions']['claim_status'].get(k, 0) for k in ('NEW', 'UNDER_REVIEW', 'AWAITING_CUSTOMER', 'APPROVED'))}).\n")
    L.append("Backorder lines by category:\n")
    L.append("| Category | Lines |\n|---|---:|")
    for k, n in c1["backorder_lines_by_category"].items():
        L.append(f"| {k} | {n} |")
    L.append(f"\nLate deliveries by carrier in {c1['last_month']}:\n")
    L.append("| Carrier | Deliveries | Late rate |\n|---|---:|---:|")
    for k, (n, r) in s["distributions"]["late_delivery_rate_by_carrier_last_month"].items():
        L.append(f"| {k} | {n} | {r:.0%} |")
    L.append("\n## Case 2 — the six messages\n")
    L.append("| File | Customer | Order | Shipment | Delivered | Contact | Key facts |\n|---|---|---|---|---|---|---|")
    files = {"A1_damaged_pallet": "01-damaged-pallet.eml", "A2_missing_cartons": "02-missing-cartons.eml",
             "A3_wrong_colour": "03-wrong-colour-portal.txt", "A4_late_delivery": "04-late-delivery.eml",
             "A5_quality_defect_sv": "05-quality-defect-sv.eml", "A6_pricing_dispute": "06-pricing-dispute.eml"}
    for key, a in A.items():
        facts = []
        if key == "A1_damaged_pallet":
            facts.append(f"Tuesday {a['tuesday']}, {a['pallet_count']} pallets; pallet 2 = " + "; ".join(a["pallet_2_lines"]) + f"; needed by {a['needed_by']}")
        elif key == "A2_missing_cartons":
            facts.append(f"no order number in the text; Friday {a['friday']}; {a['boots_ordered']} ordered, {a['boots_received']} received")
        elif key == "A3_wrong_colour":
            facts.append(f"ordered {a['ordered_colour']}, received {a['received_colour']} ({a['received_sku']}, a real SKU)")
        elif key == "A4_late_delivery":
            facts.append(f"promised {a['promised_delivery']}, season opening {a['season_opening']}; personal data in the text")
        elif key == "A5_quality_defect_sv":
            facts.append(f"Swedish; {a['defective_qty']} of {a['lines'][0]['qty']} defective")
        elif key == "A6_pricing_dispute":
            facts.append(f"invoiced {a['invoiced_unit_price']} vs '{a['promo_name']}' promo {a['expected_promo_price']} on {a['lines'][0]['qty']} pcs")
        L.append(f"| {files[key]} | {a['customer']} ({a['customer_number']}) | {a['order_number']} | {a.get('shipment_number', '')} | "
                 f"{(a.get('delivered_at') or '')[:10]} | {a['contact']} | {'; '.join(facts)} |")
    L.append("\nOrder lines behind each message:\n")
    for key, a in A.items():
        L.append(f"* **{a['order_number']}** ({a['customer']}): " + "; ".join(
            f"{l['qty']} × {l['product']}" + (f" [pallet {l['pallet']}]" if l.get('pallet') else "") for l in a["lines"]))
    L.append("\n## Case 3 — bulk price change\n")
    c3s = m["anchors"]["case3_supplier"]
    L.append("| Fact | Value |\n|---|---|")
    L.append(f"| Supplier | {c3s['name']} (id {c3s['supplier_id']}) |")
    L.append(f"| Active products | {c3s['active_products']}: " + ", ".join(f"{k} {n}" for k, n in c3["active_products_by_category"].items()) + " |")
    L.append(f"| On promotion today ({m['as_of']}) | {c3['on_promotion_today']} → {c3['affected_if_excluding_today']} rows to change |")
    L.append(f"| On promotion on {m['first_of_next_month']} | {c3['on_promotion_first_of_next_month']} → {c3['affected_if_excluding_next_month']} rows to change |")
    p = m["anchors"]["case3_promotions"]
    L.append(f"| Promotion layout | {p['active_today_and_on_first_of_next_month']} run now and past the 1st; {p['active_today_but_ends_before_first_of_next_month']} run now but end before; "
             f"{p['starts_after_today_before_first_of_next_month']} start after today but before the 1st; {p['ended_before_today']} ended earlier |")
    L.append(f"| Scheduled future prices (other suppliers) | {m['anchors'].get('scheduled_future_prices', 0)} |")
    a = s.get("aftersales", {})
    if a:
        L.append("\n## After-sales and stock\n")
        L.append("Return authorisations by status: " + ", ".join(f"{k} {n}" for k, n in a["rma_by_status"].items()))
        L.append(f"\nCredit notes: {a['credit_notes_total']} in total; issued in {c1['last_month']} by reason: "
                 + (", ".join(f"{k} {v:,.2f} EUR" for k, v in a["credit_notes_last_month_by_reason"].items()) or "none"))
        L.append("\nStock movements: " + ", ".join(f"{k} {n:,}" for k, n in a["movements_by_type"].items())
                 + f"; the last balance per product and warehouse equals inventory.on_hand; {a['restocked_units']} units came back into stock from returns.")
        mz = a.get("messy") or {}
        L.append("\nMessy-data pass: " + ("**on** — " + ", ".join(f"{k} {v}" for k, v in mz.items() if k not in ("enabled", "share")) if mz.get("enabled")
                 else "off (enable with `--config domains/nordic_supply/config-messy.toml`)."))
    L.append("\n## Distributions\n")
    d = s["distributions"]
    L.append("Order status: " + ", ".join(f"{k} {n:,}" for k, n in d["order_status"].items()))
    L.append("\nClaim status: " + ", ".join(f"{k} {n}" for k, n in d["claim_status"].items()))
    L.append("\nClaim type: " + ", ".join(f"{k} {n}" for k, n in d["claim_type"].items()))
    L.append("\nLate-dispatch rate per month: " + ", ".join(f"{k} {r:.0%}" for k, r in d["late_ship_rate_per_month"].items()))
    L.append(f"\nCustomers by country: " + ", ".join(f"{k} {n}" for k, n in d["customers_by_country"].items())
             + f". Customers with no order in the history: {d['customers_without_orders']} (dormant accounts, intended: a Customers view should show them).")
    L.append(f"\nAverage lines per order {d['avg_lines_per_order']}; orders with several shipments {d['orders_with_multiple_shipments']}; pallet shipments {d['pallet_shipments']}.")
    return "\n".join(L)
