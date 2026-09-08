"""Nordic Supply domain checks (run by dsgen.verify after the generic checks). SQLite dialect.
Signature: run(con, manifest, check, q, one) -> summaries dict for verification.json / FACTS.md."""
from __future__ import annotations

import datetime as dt
import json
import os



def _ean_ok(ean: str) -> bool:
    if not (ean and len(ean) == 13 and ean.isdigit()):
        return False
    digits = [int(c) for c in ean]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == digits[12]


def run(con, manifest, check, q, one):
    as_of = manifest["as_of"]
    report = {"summaries": {}}
    # --- chronology
    check("shipped after placed", one("SELECT COUNT(*) FROM shipments s JOIN orders o ON o.id=s.order_id WHERE date(s.shipped_at) < date(o.placed_at)") == 0)
    check("delivered after shipped", one("SELECT COUNT(*) FROM shipments WHERE delivered_at IS NOT NULL AND delivered_at < shipped_at") == 0)
    check("nothing shipped after as_of", one("SELECT COUNT(*) FROM shipments WHERE date(shipped_at) > ?", as_of) == 0)
    check("nothing delivered after as_of", one("SELECT COUNT(*) FROM shipments WHERE date(delivered_at) > ?", as_of) == 0)
    late_ev = q("SELECT event_type, COUNT(*) FROM delivery_events WHERE date(event_time) > ? GROUP BY 1", as_of)
    check("no events after as_of", not late_ev, str(late_ev))
    check("no orders placed after as_of", one("SELECT COUNT(*) FROM orders WHERE date(placed_at) > ?", as_of) == 0)
    check("claims opened after delivery", one("SELECT COUNT(*) FROM claims c JOIN shipments s ON s.id=c.shipment_id WHERE date(c.opened_at) < date(s.delivered_at)") == 0)
    check("claims resolved after opened", one("SELECT COUNT(*) FROM claims WHERE resolved_at IS NOT NULL AND resolved_at < opened_at") == 0)
    check("terminal claims have resolved_at", one("SELECT COUNT(*) FROM claims WHERE status IN ('RESOLVED','CLOSED','REJECTED') AND resolved_at IS NULL") == 0)
    check("open claims have no resolved_at", one("SELECT COUNT(*) FROM claims WHERE status NOT IN ('RESOLVED','CLOSED','REJECTED') AND resolved_at IS NOT NULL") == 0)
    check("no open claim older than 120 days", one("SELECT COUNT(*) FROM claims WHERE status NOT IN ('RESOLVED','CLOSED','REJECTED') AND julianday(?) - julianday(opened_at) > 120", as_of) == 0)
    check("DELAYED events precede DELIVERED", one("SELECT COUNT(*) FROM delivery_events d JOIN delivery_events v ON v.shipment_id=d.shipment_id AND v.event_type='DELIVERED' WHERE d.event_type='DELAYED' AND d.event_time >= v.event_time") == 0)
    check("DELIVERY_ATTEMPTED follows DISPATCHED", one("SELECT COUNT(*) FROM delivery_events a JOIN delivery_events s ON s.shipment_id=a.shipment_id AND s.event_type='DISPATCHED' WHERE a.event_type='DELIVERY_ATTEMPTED' AND a.event_time <= s.event_time") == 0)
    check("DAMAGE_REPORTED follows DELIVERED", one("SELECT COUNT(*) FROM delivery_events a JOIN delivery_events s ON s.shipment_id=a.shipment_id AND s.event_type='DELIVERED' WHERE a.event_type='DAMAGE_REPORTED' AND a.event_time < s.event_time") == 0)
    check("HUB_SCAN and OUT_FOR_DELIVERY lie between DISPATCHED and DELIVERED", one("SELECT COUNT(*) FROM delivery_events e JOIN delivery_events s ON s.shipment_id=e.shipment_id AND s.event_type='DISPATCHED' LEFT JOIN delivery_events v ON v.shipment_id=e.shipment_id AND v.event_type='DELIVERED' WHERE e.event_type IN ('HUB_SCAN','OUT_FOR_DELIVERY') AND (e.event_time < s.event_time OR (v.event_time IS NOT NULL AND e.event_time > v.event_time))") == 0)
    check("no order line after the product was discontinued", one("SELECT COUNT(*) FROM order_lines ol JOIN orders o ON o.id=ol.order_id JOIN products p ON p.id=ol.product_id WHERE p.discontinued_on IS NOT NULL AND date(o.placed_at) > p.discontinued_on") == 0)
    check("anchor quantities are multiples of the case pack", one("SELECT COUNT(*) FROM order_lines ol JOIN orders o ON o.id=ol.order_id JOIN products p ON p.id=ol.product_id WHERE o.order_number IN (SELECT value FROM json_each(?)) AND ol.quantity % p.case_pack <> 0", json.dumps([a["order_number"] for a in manifest["anchors"]["case2"].values()])) == 0)
    check("delivered shipments have DELIVERED event", one("SELECT COUNT(*) FROM shipments s WHERE s.delivered_at IS NOT NULL AND NOT EXISTS (SELECT 1 FROM delivery_events e WHERE e.shipment_id=s.id AND e.event_type='DELIVERED')") == 0)
    check("in-transit shipments have no DELIVERED event", one("SELECT COUNT(*) FROM shipments s WHERE s.delivered_at IS NULL AND EXISTS (SELECT 1 FROM delivery_events e WHERE e.shipment_id=s.id AND e.event_type='DELIVERED')") == 0)
    check("shipped lines have a shipment line", one("SELECT COUNT(*) FROM order_lines ol WHERE ol.status='SHIPPED' AND NOT EXISTS (SELECT 1 FROM shipment_lines sl WHERE sl.order_line_id=ol.id)") == 0)
    check("unshipped lines have no shipment line", one("SELECT COUNT(*) FROM order_lines ol WHERE ol.status<>'SHIPPED' AND EXISTS (SELECT 1 FROM shipment_lines sl WHERE sl.order_line_id=ol.id)") == 0)
    check("shipped qty = line qty", one("SELECT COUNT(*) FROM order_lines ol JOIN shipment_lines sl ON sl.order_line_id=ol.id WHERE sl.quantity<>ol.quantity") == 0)
    check("order total = sum of lines", one("SELECT COUNT(*) FROM orders o WHERE ABS(o.total_net - (SELECT COALESCE(SUM(line_total),0) FROM order_lines l WHERE l.order_id=o.id)) > 0.05") == 0)
    check("DELIVERED orders fully delivered", one("SELECT COUNT(*) FROM orders o WHERE o.status='DELIVERED' AND EXISTS (SELECT 1 FROM shipments s WHERE s.order_id=o.id AND s.delivered_at IS NULL)") == 0)
    check("DELIVERED orders have no open lines", one("SELECT COUNT(*) FROM orders o WHERE o.status='DELIVERED' AND EXISTS (SELECT 1 FROM order_lines l WHERE l.order_id=o.id AND l.status<>'SHIPPED')") == 0)
    check("CANCELLED orders have no shipments", one("SELECT COUNT(*) FROM orders o WHERE o.status='CANCELLED' AND EXISTS (SELECT 1 FROM shipments s WHERE s.order_id=o.id)") == 0)
    check("pallet numbers within pallet_count", one("SELECT COUNT(*) FROM shipment_lines sl JOIN shipments s ON s.id=sl.shipment_id WHERE (s.pallet_count=0 AND sl.pallet_number IS NOT NULL) OR (s.pallet_count>0 AND (sl.pallet_number IS NULL OR sl.pallet_number > s.pallet_count))") == 0)

    # --- prices and promotions
    check("one current price per product",
          one("SELECT COUNT(*) FROM products p WHERE (SELECT COUNT(*) FROM price_history h WHERE h.product_id=p.id AND h.valid_from <= ? AND (h.valid_to IS NULL OR h.valid_to >= ?)) <> 1", as_of, as_of) == 0)
    check("price history contiguous, no overlaps",
          one("SELECT COUNT(*) FROM price_history a JOIN price_history b ON a.product_id=b.product_id AND a.id<>b.id AND a.valid_from < b.valid_from AND (a.valid_to IS NULL OR a.valid_to >= b.valid_from)") == 0)
    check("promotions end after they start", one("SELECT COUNT(*) FROM promotions WHERE ends_on < starts_on") == 0)
    check("promo price below list price", one("SELECT COUNT(*) FROM promotions pr WHERE pr.promo_price >= (SELECT h.list_price FROM price_history h WHERE h.product_id=pr.product_id AND h.valid_from <= pr.starts_on ORDER BY h.valid_from DESC LIMIT 1)") == 0)
    check("line unit price = promo or list price", one("SELECT COUNT(*) FROM order_lines WHERE (promotion_applied=1 AND unit_price >= list_price) OR (promotion_applied=0 AND unit_price <> list_price)") == 0)
    check("EAN-13 check digits valid", one("SELECT COUNT(*) FROM products WHERE length(ean) <> 13") == 0 and all(_ean_ok(e) for (e,) in q("SELECT ean FROM products")))

    # --- inventory vs backorders
    check("backordered products have no free stock in the shipping warehouse",
          one("SELECT COUNT(*) FROM order_lines ol JOIN orders o ON o.id=ol.order_id LEFT JOIN inventory i ON i.product_id=ol.product_id AND i.warehouse_id=o.warehouse_id "
              "WHERE ol.status='BACKORDERED' AND (i.id IS NULL OR i.on_hand - i.reserved > 0 OR i.next_inbound_date IS NULL)") == 0)
    check("no product is short everywhere without an inbound date", one("SELECT COUNT(*) FROM inventory WHERE on_hand < reorder_point AND next_inbound_date IS NULL") == 0)

    # --- case 3 anchor
    fjv = q("SELECT cat.name, COUNT(*) FROM products p JOIN suppliers s ON s.id=p.supplier_id JOIN categories cat ON cat.id=p.category_id WHERE s.name='Fjellvind AS' AND p.active=1 GROUP BY cat.name")
    check("case 3: Fjellvind has 240 active products", sum(n for _, n in fjv) == 240, str(fjv))
    check("case 3: across exactly 3 categories", len(fjv) == 3)
    nm = manifest["first_of_next_month"]
    promo_today = one("SELECT COUNT(DISTINCT pr.product_id) FROM promotions pr JOIN products p ON p.id=pr.product_id JOIN suppliers s ON s.id=p.supplier_id WHERE s.name='Fjellvind AS' AND ? BETWEEN pr.starts_on AND pr.ends_on", as_of)
    promo_nm = one("SELECT COUNT(DISTINCT pr.product_id) FROM promotions pr JOIN products p ON p.id=pr.product_id JOIN suppliers s ON s.id=p.supplier_id WHERE s.name='Fjellvind AS' AND ? BETWEEN pr.starts_on AND pr.ends_on", nm)
    layout = manifest["anchors"]["case3_promotions"]
    exp_today = layout["active_today_and_on_first_of_next_month"] + layout["active_today_but_ends_before_first_of_next_month"]
    exp_nm = layout["active_today_and_on_first_of_next_month"] + layout["starts_after_today_before_first_of_next_month"]
    check(f"case 3: Fjellvind promotions active today = {exp_today}", promo_today == exp_today, str(promo_today))
    check(f"case 3: Fjellvind promotions active on 1st of next month = {exp_nm}", promo_nm == exp_nm, str(promo_nm))
    check("case 3: the two readings of 'already on promotion' differ", promo_today != promo_nm)
    check("case 3: Fjellvind has no scheduled future price", one("SELECT COUNT(*) FROM price_history h JOIN products p ON p.id=h.product_id JOIN suppliers s ON s.id=p.supplier_id WHERE s.name='Fjellvind AS' AND h.valid_from > ?", as_of) == 0)
    report["summaries"]["case3"] = {"active_products_by_category": dict(fjv), "on_promotion_today": promo_today,
                                    "on_promotion_first_of_next_month": promo_nm,
                                    "affected_if_excluding_today": 240 - promo_today, "affected_if_excluding_next_month": 240 - promo_nm}

    # --- case 1 anchors and summaries
    y, mth = int(as_of[:4]), int(as_of[5:7])
    lm_y, lm_m = (y, mth - 1) if mth > 1 else (y - 1, 12)
    lm = f"{lm_y:04d}-{lm_m:02d}"
    rows = q("SELECT date(s.shipped_at), date(s.shipped_at) > o.promised_ship_date FROM shipments s JOIN orders o ON o.id=s.order_id WHERE strftime('%Y-%m', s.shipped_at)=?", lm)
    wk_tot, wk_late = {}, {}
    for d, late in rows:
        w = f"W{dt.date.fromisoformat(d).isocalendar()[1]:02d}"
        wk_tot[w] = wk_tot.get(w, 0) + 1
        wk_late[w] = wk_late.get(w, 0) + (late or 0)
    weeks = [(w, wk_tot[w], wk_late[w]) for w in sorted(wk_tot)]
    check("case 1: late shipments in every week of last month", all(w[2] > 0 for w in weeks) and len(weeks) >= 4, str(weeks))
    spike = max(weeks, key=lambda w: w[2] / w[1])
    check("case 1: a visible spike week (rate > 35%)", spike[2] / spike[1] > 0.35, f"week {spike[0]}: {spike[2]}/{spike[1]}")
    open7 = one("SELECT COUNT(*) FROM claims WHERE status NOT IN ('RESOLVED','CLOSED','REJECTED') AND julianday(?) - julianday(opened_at) > 7", as_of + " 12:00:00")
    scale = manifest.get("scale", 1.0)
    check("case 1: claims open over 7 days (scale-adjusted 12..250)", 12 * scale <= open7 <= 250 * scale, str(open7))
    bo = q("SELECT cat.name, COUNT(*) FROM order_lines ol JOIN products p ON p.id=ol.product_id JOIN categories cat ON cat.id=p.category_id WHERE ol.status='BACKORDERED' GROUP BY cat.name ORDER BY 2 DESC")
    check("case 1: backorder lines in several categories", len(bo) >= 5, str(bo[:3]))
    by_cust = q("SELECT c.name, COUNT(DISTINCT o.id) FROM shipments s JOIN orders o ON o.id=s.order_id JOIN customers c ON c.id=o.customer_id "
                "WHERE date(s.shipped_at) > o.promised_ship_date AND strftime('%Y-%m', s.shipped_at)=? GROUP BY c.name ORDER BY 2 DESC, 1 LIMIT 10", lm)
    late_orders = one("SELECT COUNT(DISTINCT o.id) FROM shipments s JOIN orders o ON o.id=s.order_id WHERE date(s.shipped_at) > o.promised_ship_date AND strftime('%Y-%m', s.shipped_at)=?", lm)
    late_customers = one("SELECT COUNT(DISTINCT o.customer_id) FROM shipments s JOIN orders o ON o.id=s.order_id WHERE date(s.shipped_at) > o.promised_ship_date AND strftime('%Y-%m', s.shipped_at)=?", lm)
    check("case 1: the document's example query has a spread of customers", late_customers >= 20, str(late_customers))
    report["summaries"]["case1"] = {"last_month": lm, "late_by_week": [{"week": w[0], "shipments": w[1], "late": w[2]} for w in weeks],
                                    "late_orders": late_orders, "late_customers": late_customers, "late_by_customer": by_cust,
                                    "claims_open_over_7_days": open7, "backorder_lines_by_category": dict(bo)}
    # --- e-mail facts that must agree with the records
    A2 = manifest["anchors"]["case2"]["A2_missing_cartons"]
    check("e-mail 02: boots really come in cartons of six", one("SELECT case_pack FROM products WHERE sku=?", A2["lines"][0]["sku"]) == A2["cartons_of"])
    A3 = manifest["anchors"]["case2"]["A3_wrong_colour"]
    check("e-mail 03: the received colour exists as a real SKU", one("SELECT COUNT(*) FROM products WHERE sku=? AND colour=?", A3["received_sku"], A3["received_colour"]) == 1)
    check("e-mail 03: the received SKU has a current price", one("SELECT COUNT(*) FROM price_history ph JOIN products p ON p.id=ph.product_id WHERE p.sku=? AND ph.valid_to IS NULL", A3["received_sku"]) == 1)
    A6 = manifest["anchors"]["case2"]["A6_pricing_dispute"]
    check("e-mail 06: the promotion it names covered the order date", one("SELECT COUNT(*) FROM promotions pr JOIN products p ON p.id=pr.product_id WHERE p.sku=? AND pr.name=? AND pr.starts_on<=? AND pr.ends_on>=?",
          A6["lines"][0]["sku"], A6["promo_name"], A6["placed_at"][:10], A6["placed_at"][:10]) == 1)
    report["summaries"]["distributions"] = {
        "order_status": dict(q("SELECT status, COUNT(*) FROM orders GROUP BY status ORDER BY 2 DESC")),
        "claim_status": dict(q("SELECT status, COUNT(*) FROM claims GROUP BY status ORDER BY 2 DESC")),
        "claim_type": dict(q("SELECT claim_type, COUNT(*) FROM claims GROUP BY claim_type ORDER BY 2 DESC")),
        "orders_per_month": dict(q("SELECT strftime('%Y-%m', placed_at), COUNT(*) FROM orders GROUP BY 1 ORDER BY 1")),
        "late_ship_rate_per_month": {r[0]: round(r[1], 3) for r in q("SELECT strftime('%Y-%m', s.shipped_at), AVG(date(s.shipped_at) > o.promised_ship_date) FROM shipments s JOIN orders o ON o.id=s.order_id GROUP BY 1 ORDER BY 1")},
        "late_delivery_rate_by_carrier_last_month": {r[0]: [r[1], round(r[2], 3)] for r in q("SELECT s.carrier, COUNT(*), AVG(date(s.delivered_at) > o.promised_delivery_date) FROM shipments s JOIN orders o ON o.id=s.order_id WHERE s.delivered_at IS NOT NULL AND strftime('%Y-%m', s.delivered_at)=? GROUP BY 1 ORDER BY 2 DESC", lm)},
        "customers_by_country": dict(q("SELECT country, COUNT(*) FROM customers GROUP BY 1 ORDER BY 2 DESC")),
        "products_by_category": dict(q("SELECT c.name, COUNT(*) FROM products p JOIN categories c ON c.id=p.category_id GROUP BY 1 ORDER BY 2 DESC")),
        "avg_lines_per_order": round(one("SELECT 1.0*COUNT(*)/(SELECT COUNT(*) FROM orders) FROM order_lines"), 2),
        "orders_with_multiple_shipments": one("SELECT COUNT(*) FROM (SELECT order_id FROM shipments GROUP BY order_id HAVING COUNT(*)>1)"),
        "pallet_shipments": one("SELECT COUNT(*) FROM shipments WHERE pallet_count>0"),
    }
    return report["summaries"]
