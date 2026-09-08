"""Claims and claim lines."""
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

from dsgen.model import D, TS, cfg, iso, money, weighted_choice
from .ctx import Ctx
from .orders import next_seq, to_weekday, ts_on
from .pools import CLAIM_TYPES, CLAIM_TYPE_WEIGHTS, DEFECTS, RESOLUTION_FOR

def gen_claims(ctx: Ctx):
    rng = ctx.rng
    agents = ctx.users_by_role["SUPPORT_AGENT"]
    orders = [o for o in ctx.tables["orders"] if "_lines" in o and not o.get("_no_claim") and o["status"] not in ("CANCELLED", "OPEN", "CONFIRMED")]
    ships_by_order = defaultdict(list)
    for s in ctx.tables["shipments"]:
        ships_by_order[s["order_id"]].append(s)
    lines_by_ship = defaultdict(list)
    for sl in ctx.tables["shipment_lines"]:
        lines_by_ship[sl["shipment_id"]].append(sl)
    line_by_id = {l["id"]: l for l in ctx.tables["order_lines"]}

    for o in orders:
        delivered = [s for s in ships_by_order[o["id"]] if s["delivered_at"]]
        if not delivered:
            continue
        s = rng.choice(delivered)
        deliv_day = s["_delivered_date"]
        promised_delivery = D.fromisoformat(o["promised_delivery_date"])
        late_days = (deliv_day - promised_delivery).days
        C = cfg("claims")
        p_claim = C["base_rate"] + (C["late_bonus_3d"] if late_days >= 3 else C["late_bonus_1d"] if late_days >= 1 else 0.0)
        if rng.random() > p_claim:
            continue
        ctype = "LATE_DELIVERY" if (late_days >= 1 and rng.random() < 0.5) else weighted_choice(rng, CLAIM_TYPES, CLAIM_TYPE_WEIGHTS)
        if ctype == "LATE_DELIVERY" and late_days < 1:
            ctype = "DAMAGED"
        opened_day = to_weekday(deliv_day + dt.timedelta(days=rng.choice([0, 1, 1, 2, 3, 5, 7, 12] if ctype != "QUALITY_DEFECT" else [10, 14, 21, 30, 45])))
        if opened_day > ctx.as_of:
            continue
        opened_at = ts_on(rng, opened_day, 7, 18)
        age = (ctx.as_of - opened_day).days
        status = _claim_status(rng, age)
        resolved_at = None
        if status in ("RESOLVED", "CLOSED", "REJECTED"):
            resolved_at = ts_on(rng, to_weekday(min(ctx.as_of, opened_day + dt.timedelta(days=rng.randint(1, min(25, max(1, age)))))), 8, 17)
        # affected lines
        sl = lines_by_ship[s["id"]]
        n_aff = 1 if ctype in ("PRICING_DISPUTE", "LATE_DELIVERY") else min(len(sl), rng.choice([1, 1, 1, 2, 2, 3]))
        affected = rng.sample(sl, n_aff) if ctype not in ("LATE_DELIVERY",) else []
        claimed = 0.0
        claim_lines = []
        product_names = []
        for a in affected:
            ol = line_by_id[a["order_line_id"]]
            qty_aff = a["quantity"] if ctype in ("WRONG_ITEM", "PRICING_DISPUTE") else max(1, int(a["quantity"] * rng.choice([0.1, 0.25, 0.5, 0.5, 1.0])))
            unit = float(ol["unit_price"])
            amount = round(qty_aff * unit if ctype != "PRICING_DISPUTE" else qty_aff * unit * 0.12, 2)
            claimed += amount
            product_names.append((ol["_p"]["name"], qty_aff, a["quantity"], a["pallet_number"]))
            claim_lines.append((ol, qty_aff, a["pallet_number"], amount))
        if ctype == "LATE_DELIVERY":
            claimed = round(float(o["total_net"]) * rng.choice([0.05, 0.10, 0.10, 0.15]), 2)
        description, requested = _claim_text(rng, ctype, product_names, o, s, late_days)
        if rng.random() < cfg("pii", "free_text_share"):
            pc = rng.choice(ctx.contacts_by_customer[o["customer_id"]])
            description += rng.choice([f" Customer contact: {pc['first_name']} {pc['last_name']}, {pc['phone']}.",
                                       f" Reported by {pc['first_name']} {pc['last_name']} ({pc['email']}).",
                                       f" Call back {pc['first_name']} on {pc['phone']}."])
        needed_by = to_weekday(opened_day + dt.timedelta(days=rng.randint(2, 10))) if (ctype in ("DAMAGED", "MISSING_ITEMS", "WRONG_ITEM") and rng.random() < 0.4) else None
        priority = "URGENT" if (needed_by and (needed_by - opened_day).days <= 3) else \
                   "HIGH" if (claimed > 2000 or ctype == "DAMAGED" and claimed > 800) else \
                   "LOW" if ctype in ("PRICING_DISPUTE", "RETURN_REQUEST") and rng.random() < 0.5 else "NORMAL"
        approved = None
        if status in ("APPROVED", "RESOLVED", "CLOSED"):
            approved = round(claimed * rng.choice([1.0, 1.0, 1.0, 0.5, 0.75]), 2)
        elif status == "REJECTED":
            approved = 0.0
        cid = len(ctx.tables["claims"]) + 1
        contact = rng.choice(ctx.contacts_by_customer[o["customer_id"]])
        ctx.tables["claims"].append({
            "id": cid, "claim_number": f"CL-{opened_day.year}-{next_seq(ctx, f'CL{opened_day.year}'):05d}",
            "customer_id": o["customer_id"], "order_id": o["id"], "shipment_id": s["id"],
            "claim_type": ctype, "status": status, "priority": priority,
            "source": weighted_choice(rng, ["EMAIL", "PORTAL", "PHONE"], [55, 35, 10]),
            "reported_by_contact_id": contact["id"],
            "assigned_to": "" if (status == "NEW" and rng.random() < 0.6) else rng.choice(agents),
            "opened_at": iso(opened_at), "resolved_at": iso(resolved_at),
            "needed_by": iso(needed_by), "requested_resolution": requested,
            "claimed_amount": money(claimed), "approved_amount": money(approved) if approved is not None else "",
            "description": description,
            "resolution_note": _resolution_note(rng, ctype, status) if resolved_at else "",
        })
        for ol, qty_aff, pallet, amount in claim_lines:
            ctx.tables["claim_lines"].append({"id": len(ctx.tables["claim_lines"]) + 1, "claim_id": cid,
                                              "order_line_id": ol["id"], "product_id": ol["product_id"],
                                              "quantity_affected": qty_aff, "pallet_number": pallet if pallet != "" else "",
                                              "amount": money(amount),
                                              "issue_note": _line_note(rng, ctype)})
        if ctype == "DAMAGED" and rng.random() < 0.5:
            ctx.tables["delivery_events"].append({"id": len(ctx.tables["delivery_events"]) + 1, "shipment_id": s["id"],
                                                  "event_time": iso(max(TS.fromisoformat(s["delivered_at"]) + dt.timedelta(hours=1),
                                                                        min(opened_at + dt.timedelta(hours=rng.randint(1, 30)),
                                                                            TS.combine(ctx.as_of, dt.time(17, 0))))),
                                                  "event_type": "DAMAGE_REPORTED", "location": o["_customer"]["city"],
                                                  "note": f"Receiver reports damage, claim {ctx.tables['claims'][-1]['claim_number']}"})

def _claim_status(rng, age):
    if age <= 2:
        return weighted_choice(rng, ["NEW", "UNDER_REVIEW"], [70, 30])
    if age <= 7:
        return weighted_choice(rng, ["NEW", "UNDER_REVIEW", "AWAITING_CUSTOMER", "APPROVED", "RESOLVED"], [15, 45, 15, 15, 10])
    if age <= 21:
        return weighted_choice(rng, ["NEW", "UNDER_REVIEW", "AWAITING_CUSTOMER", "APPROVED", "RESOLVED", "REJECTED", "CLOSED"],
                               [4, 22, 16, 12, 28, 8, 10])
    if age <= 60:
        return weighted_choice(rng, ["UNDER_REVIEW", "AWAITING_CUSTOMER", "APPROVED", "RESOLVED", "REJECTED", "CLOSED"],
                               [4, 6, 5, 40, 12, 33])
    if age <= 120:
        return weighted_choice(rng, ["AWAITING_CUSTOMER", "RESOLVED", "REJECTED", "CLOSED"], [1, 28, 12, 59])
    return weighted_choice(rng, ["RESOLVED", "REJECTED", "CLOSED"], [28, 12, 60])

def _claim_text(rng, ctype, names, order, ship, late_days):
    first = names[0] if names else None
    if ctype == "DAMAGED":
        pal = f" on pallet {first[3]}" if first and first[3] not in ("", None) else ""
        txt = f"{first[1]} x {first[0]}{pal} arrived with crushed cartons and torn packaging." if first else "Goods arrived damaged."
        if len(names) > 1:
            txt += f" Also affected: {', '.join(n[0] for n in names[1:])}."
        txt += " " + rng.choice(["Photos attached.", "Driver noted the damage on the CMR.", "Outer wrap was torn on arrival.", ""])
    elif ctype == "MISSING_ITEMS":
        txt = f"Packing list shows {first[2]} x {first[0]}, customer counted {first[2] - first[1]}. {first[1]} missing." if first else "Items missing from delivery."
        txt += " " + rng.choice(["Carton count on the pallet matched the label.", "One carton short against the packing list.", ""])
    elif ctype == "WRONG_ITEM":
        txt = f"Received a different variant instead of {first[0]} ({first[1]} pcs). Customer asks for exchange." if first else "Wrong item delivered."
    elif ctype == "LATE_DELIVERY":
        txt = (f"Delivery promised {order['promised_delivery_date']} arrived {ship['delivered_at'][:10]} ({late_days} days late). "
               + rng.choice(["Customer missed a weekend campaign and requests a goodwill credit.",
                             "Store had to postpone its season opening display.",
                             "Customer requests compensation for the delay.",
                             "Second late delivery this quarter, customer escalates."]))
    elif ctype == "QUALITY_DEFECT":
        txt = f"{first[1]} x {first[0]} returned by end customers: {rng.choice(DEFECTS)}." if first else "Quality complaint."
        txt += rng.choice([" Customer asks whether the whole batch is affected.", " Remaining stock put on hold in store.", ""])
    elif ctype == "PRICING_DISPUTE":
        txt = f"Invoice price for {first[0]} does not match the agreed price. Customer expected the {rng.choice(['promotion', 'pre-order', 'contract'])} price." if first else "Invoice price disputed."
    else:
        txt = f"Customer wants to return {first[1]} x {first[0]}, unsold season stock; asks for a return authorisation." if first else "Return requested."
    return txt.strip(), rng.choice(RESOLUTION_FOR[ctype])

def _line_note(rng, ctype):
    return {"DAMAGED": rng.choice(["Carton crushed", "Wet packaging", "Torn outer wrap", "Product scratched", "Contents leaked"]),
            "MISSING_ITEMS": rng.choice(["Short against packing list", "Carton missing", "Inner pack incomplete"]),
            "WRONG_ITEM": rng.choice(["Wrong colour", "Wrong size", "Wrong model"]),
            "QUALITY_DEFECT": rng.choice(DEFECTS), "PRICING_DISPUTE": "Unit price disputed",
            "RETURN_REQUEST": "Unsold stock", "LATE_DELIVERY": ""}[ctype]

def _resolution_note(rng, ctype, status):
    if status == "REJECTED":
        return rng.choice(["Damage not reported within 48 h of delivery.", "Delivered on the promised date per POD.",
                           "Price matches the signed order confirmation.", "Return window exceeded."])
    return rng.choice(["Replacement shipped, credit note for freight.", "Credit note issued.", "Redelivery completed, customer confirmed.",
                       "Goodwill credit agreed with account manager.", "Return authorised, goods received back.",
                       "Repair completed by supplier."])
