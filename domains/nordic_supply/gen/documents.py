"""Domain documents: seeded widgets, the case 2 e-mails, the placeholder photo."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import math
import os
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Optional

from .customers import _phone
from dsgen.model import D, TS, first_of_month, iso, months_back
from .ctx import Ctx

def gen_saved_widgets(ctx: Ctx):
    lm = months_back(ctx.as_of, 1)
    tm = first_of_month(ctx.as_of)
    month_name = lm.strftime("%B %Y")
    test_user = next(u["id"] for u in ctx.tables["users"] if u["username"] == "test.user")
    ctx.tables["saved_widgets"].append({
        "id": 1, "user_id": test_user, "title": f"Late shipments, {month_name}",
        "description": f"Shipments dispatched after the order's promised ship date in {month_name}, counted per ISO week.",
        "widget_type": "CHART",
        "query_sql": ("SELECT 'W' || wk AS week, n AS late_shipments FROM ("
                      "SELECT ISO_WEEK(CAST(s.shipped_at AS DATE)) AS wk, COUNT(*) AS n "
                      "FROM shipments s JOIN orders o ON o.id = s.order_id "
                      f"WHERE CAST(s.shipped_at AS DATE) > o.promised_ship_date AND s.shipped_at >= DATE '{iso(lm)}' "
                      f"AND s.shipped_at < DATE '{iso(tm)}' GROUP BY ISO_WEEK(CAST(s.shipped_at AS DATE))) ORDER BY wk"),
        "state_json": "", "position": 0, "created_at": iso(TS.combine(ctx.as_of, dt.time(9, 12))),
        "updated_at": iso(TS.combine(ctx.as_of, dt.time(9, 12)))})
    ctx.tables["saved_widgets"].append({
        "id": 2, "user_id": test_user, "title": "Claims open for over 7 days",
        "description": "Claims not yet resolved, closed or rejected that were opened more than 7 days ago, oldest first.",
        "widget_type": "GRID",
        "query_sql": ("SELECT c.claim_number, cu.name AS customer, c.claim_type, c.status, c.priority, c.opened_at, "
                      "DATEDIFF('DAY', c.opened_at, CURRENT_TIMESTAMP) AS days_open, c.claimed_amount "
                      "FROM claims c JOIN customers cu ON cu.id = c.customer_id "
                      "WHERE c.status NOT IN ('RESOLVED', 'CLOSED', 'REJECTED') "
                      "AND c.opened_at < DATEADD('DAY', -7, CURRENT_TIMESTAMP) ORDER BY c.opened_at"),
        "state_json": "", "position": 1, "created_at": iso(TS.combine(ctx.as_of, dt.time(9, 20))),
        "updated_at": iso(TS.combine(ctx.as_of, dt.time(9, 20)))})

def _fmt_lines(lines):
    return "\n".join(f">   {l['qty']:>3} x {l['product']}  ({l['sku']})  @ {l['unit_price']} EUR" for l in lines)


def document_context(ctx, key, a):
    """Fields the e-mail templates in documents/emails/*.tmpl use, computed from the anchor record `a`
    and the in-memory indexes. Anything a template needs that is not a plain anchor field goes here."""
    cust = next(c for c in ctx.customers if c["id"] == a["customer_id"])
    contacts = ctx.contacts_by_customer[cust["id"]]
    first = a["lines"][0]
    d = {"customer_street": cust["street"], "customer_postal_code": cust["postal_code"], "customer_city": cust["city"],
         "contact_role": contacts[0]["role"], "contact_first": a["contact"].split()[0],
         "placed_date": a["placed_at"][:10], "delivered_date": (a.get("delivered_at") or "")[:10],
         "lines_block": _fmt_lines(a["lines"]), "first_product": first["product"], "first_qty": first["qty"],
         "first_sku": first["sku"], "first_brand": first["product"].split()[0]}
    if key == "A1_damaged_pallet":
        p2 = a["pallet_2_lines"]
        tents = [n for n in p2 if "Tent" in n] or p2
        d["pallet2_tents"] = " and ".join(tents)
        d["first_pallet2_line"] = p2[0] if p2 else ""
    elif key == "A2_missing_cartons":
        d["boots_size"] = first["product"].split("EU ")[1].split()[0] if "EU " in first["product"] else "boot"
    elif key == "A3_wrong_colour":
        d["ordered_colour_short"] = a["ordered_colour"].split()[-1].lower()
        d["received_colour_short"] = a["received_colour"].split()[-1].lower()
    elif key == "A4_late_delivery":
        mgr = contacts[-1]
        d["manager_name"] = f"{mgr['first_name']} {mgr['last_name']}"
        d["late_days"] = (D.fromisoformat(a["delivered_at"][:10]) - D.fromisoformat(a["promised_delivery"])).days if a.get("delivered_at") else "several"
        d["personal_mobile"] = _phone(ctx.rng, "SE")
        am = next(u for u in ctx.tables["users"] if u["id"] == cust["account_manager_id"])
        d["account_manager_email"] = am["email"]
    elif key == "A5_quality_defect_sv":
        d["remaining_qty"] = first["qty"] - a["defective_qty"]
    elif key == "A6_pricing_dispute":
        ap = contacts[-1]
        d["ap_name"] = f"{ap['first_name']} {ap['last_name']}"
        d["ap_email"] = ap["email"]
        d["ap_first"] = ap["first_name"]
        d["price_diff_total"] = f"{(float(a['invoiced_unit_price']) - float(a['expected_promo_price'])) * first['qty']:.2f}"
    return d
