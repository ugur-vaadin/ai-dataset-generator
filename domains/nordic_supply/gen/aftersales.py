"""After-sales and stock mechanics added on top of orders, shipments and claims:

* return authorisations and return lines (RMAs) for claims that send goods back,
* credit notes for claims with an approved amount,
* a stock-movement ledger per product and warehouse that reconciles exactly to `inventory.on_hand`
  (receipts, shipments, returns, a rare stock-count adjustment),
* an optional "messy data" pass (config `[messy]`) that roughens master data the way real systems are:
  inconsistent casing and spacing in customer names, mixed phone formats, a few duplicate customers, typos
  in free text. Anchor customers are never touched, so the demo messages still resolve cleanly.

All steps run after every other table is built, so with `[messy] enabled = false` (the default) the earlier
tables are byte-identical to a generation without these steps.
"""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict

from dsgen.model import CFG, D, TS, add_business_days, cfg, iso, money, weighted_choice
from .ctx import Ctx
from .orders import next_seq, to_weekday, ts_on

RETURN_TYPES = {"RETURN_REQUEST", "WRONG_ITEM", "QUALITY_DEFECT", "DAMAGED"}
CREDIT_REASON = {"PRICING_DISPUTE": "PRICE_CORRECTION", "LATE_DELIVERY": "GOODWILL", "RETURN_REQUEST": "RETURN"}


def _rma_status(rng, age_days):
    if age_days <= 3:
        return weighted_choice(rng, ["AUTHORISED", "IN_TRANSIT"], [60, 40])
    if age_days <= 10:
        return weighted_choice(rng, ["AUTHORISED", "IN_TRANSIT", "RECEIVED", "INSPECTED"], [10, 30, 40, 20])
    if age_days <= 30:
        return weighted_choice(rng, ["IN_TRANSIT", "RECEIVED", "INSPECTED", "CLOSED", "CANCELLED"], [5, 15, 30, 45, 5])
    return weighted_choice(rng, ["INSPECTED", "CLOSED", "CANCELLED"], [10, 84, 6])


def gen_returns_credits(ctx: Ctx):
    """RMAs for claims that send goods back (approved or resolved, with claim lines) and credit notes for every
    claim with an approved amount. Dates follow the claim: authorised after opening, credit issued after resolution."""
    rng = ctx.rng
    agents = ctx.users_by_role["SUPPORT_AGENT"]
    orders_by_id = {o["id"]: o for o in ctx.tables["orders"]}
    lines_by_claim = defaultdict(list)
    for cl in ctx.tables["claim_lines"]:
        lines_by_claim[cl["claim_id"]].append(cl)
    for c in ctx.tables["claims"]:
        opened = TS.fromisoformat(c["opened_at"])
        resolved = TS.fromisoformat(c["resolved_at"]) if c["resolved_at"] else None
        order = orders_by_id[c["order_id"]]
        # --- return authorisation
        if c["claim_type"] in RETURN_TYPES and c["status"] in ("APPROVED", "RESOLVED", "CLOSED") and lines_by_claim[c["id"]] \
                and c["requested_resolution"] in ("REPLACEMENT", "RETURN_AUTHORISATION", "REPAIR", "CREDIT") and rng.random() < 0.8:
            auth_day = to_weekday(min(ctx.as_of, opened.date() + dt.timedelta(days=rng.randint(0, 4))))
            authorised_at = ts_on(rng, auth_day, 8, 17)
            if authorised_at < opened:
                authorised_at = opened + dt.timedelta(hours=rng.randint(1, 5))
                auth_day = authorised_at.date()
            age = (ctx.as_of - auth_day).days
            status = _rma_status(rng, age)
            received_at = inspected_at = None
            if status in ("RECEIVED", "INSPECTED", "CLOSED"):
                received_at = ts_on(rng, to_weekday(min(ctx.as_of, auth_day + dt.timedelta(days=rng.randint(2, 9)))), 7, 16)
                if received_at < authorised_at:
                    received_at = authorised_at + dt.timedelta(hours=rng.randint(30, 60))
            if status in ("INSPECTED", "CLOSED") and received_at:
                inspected_at = ts_on(rng, to_weekday(min(ctx.as_of, received_at.date() + dt.timedelta(days=rng.randint(0, 3)))), 8, 17)
                if inspected_at < received_at:
                    inspected_at = received_at + dt.timedelta(hours=rng.randint(1, 6))
            rid = len(ctx.tables["return_authorisations"]) + 1
            ctx.tables["return_authorisations"].append({
                "id": rid, "rma_number": f"RMA-{auth_day.year}-{next_seq(ctx, f'RMA{auth_day.year}'):05d}",
                "claim_id": c["id"], "customer_id": c["customer_id"], "warehouse_id": order["warehouse_id"],
                "status": status, "authorised_at": iso(authorised_at), "received_at": iso(received_at), "inspected_at": iso(inspected_at),
                "authorised_by": c["assigned_to"] or rng.choice(agents),
                "notes": rng.choice(["Return label sent to the store.", "Customer returns with next scheduled pickup.",
                                     "Goods to be inspected before credit.", "", "", "Photos received, return authorised without inspection."]),
            })
            for cl in lines_by_claim[c["id"]]:
                condition = disposition = ""
                if status in ("INSPECTED", "CLOSED"):
                    condition = {"RETURN_REQUEST": "RESALABLE", "WRONG_ITEM": "RESALABLE", "QUALITY_DEFECT": "DEFECTIVE", "DAMAGED": "DAMAGED"}[c["claim_type"]]
                    if condition == "RESALABLE" and rng.random() < 0.1:
                        condition = "DAMAGED"
                    disposition = {"RESALABLE": "RESTOCK", "DAMAGED": "SCRAP", "DEFECTIVE": "RETURN_TO_SUPPLIER"}[condition]
                    if condition == "DEFECTIVE" and rng.random() < 0.3:
                        disposition = "SCRAP"
                ctx.tables["return_lines"].append({
                    "id": len(ctx.tables["return_lines"]) + 1, "return_id": rid, "claim_line_id": cl["id"],
                    "product_id": cl["product_id"], "quantity": cl["quantity_affected"], "condition": condition, "disposition": disposition,
                    "_inspected_at": inspected_at, "_warehouse_id": order["warehouse_id"]})
        # --- credit note
        approved = float(c["approved_amount"]) if c["approved_amount"] not in ("", None) else 0.0
        if approved > 0 and c["status"] in ("APPROVED", "RESOLVED", "CLOSED"):
            base = resolved or opened
            issue_day = to_weekday(min(ctx.as_of, add_business_days(base.date(), rng.randint(0, 3))))
            issued_at = ts_on(rng, issue_day, 8, 17)
            if issued_at < base:
                issued_at = base + dt.timedelta(hours=rng.randint(1, 8))
            if issued_at.date() > ctx.as_of:
                continue
            status = "ISSUED" if c["status"] == "APPROVED" else weighted_choice(rng, ["APPLIED", "ISSUED", "CANCELLED"], [80, 17, 3])
            ctx.tables["credit_notes"].append({
                "id": len(ctx.tables["credit_notes"]) + 1,
                "credit_note_number": f"CN-{issue_day.year}-{next_seq(ctx, f'CN{issue_day.year}'):05d}",
                "customer_id": c["customer_id"], "claim_id": c["id"], "order_id": c["order_id"],
                "issued_at": iso(issued_at), "amount": money(approved), "currency": "EUR",
                "reason": CREDIT_REASON.get(c["claim_type"], "CLAIM"), "status": status,
                "created_by": c["assigned_to"] or rng.choice(agents),
            })
    ctx.anchors["aftersales"] = {"return_authorisations": len(ctx.tables["return_authorisations"]),
                                 "credit_notes": len(ctx.tables["credit_notes"])}


def gen_stock_movements(ctx: Ctx):
    """A ledger per (product, warehouse): every shipment line is an outbound movement at its shipment's dispatch
    time, every restocked return an inbound one, and supplier receipts (PO references) are placed just in time so
    the balance never goes negative and ends exactly at `inventory.on_hand`. If returns push the balance above
    the counted stock, a stock-count ADJUSTMENT closes the gap."""
    rng = ctx.rng
    ship_by_id = {s["id"]: s for s in ctx.tables["shipments"]}
    line_by_id = {l["id"]: l for l in ctx.tables["order_lines"]}
    pack_of = {p["id"]: max(1, int(p["case_pack"])) for p in ctx.products}
    events = defaultdict(list)   # (product_id, warehouse_id) -> [(ts, type, qty, reference)]
    for sl in ctx.tables["shipment_lines"]:
        s = ship_by_id[sl["shipment_id"]]
        pid = line_by_id[sl["order_line_id"]]["product_id"]
        events[(pid, s["warehouse_id"])].append((TS.fromisoformat(s["shipped_at"]), "SHIPMENT", -int(sl["quantity"]), s["shipment_number"]))
    rma_by_id = {r["id"]: r for r in ctx.tables["return_authorisations"]}
    for rl in ctx.tables["return_lines"]:
        if rl["disposition"] == "RESTOCK" and rl["_inspected_at"]:
            events[(rl["product_id"], rl["_warehouse_id"])].append((rl["_inspected_at"], "RETURN", int(rl["quantity"]), rma_by_id[rl["return_id"]]["rma_number"]))
    on_hand = {(i["product_id"], i["warehouse_id"]): int(i["on_hand"]) for i in ctx.tables["inventory"]}
    keys = sorted(set(events) | set(on_hand))
    rows = ctx.tables["stock_movements"]
    receipts = adjustments = 0
    po_seq_start = 10000
    for key in keys:
        pid, wid = key
        evs = sorted(events.get(key, []), key=lambda e: e[0])
        target = on_hand.get(key, 0)
        out_total = -sum(q for _, t, q, _ in evs if q < 0)
        in_returns = sum(q for _, t, q, _ in evs if q > 0)
        need = out_total + target - in_returns          # total receipts required to end at the counted stock
        balance = 0
        remaining_need = max(0, need)
        pack = pack_of.get(pid, 1)
        movs = []                                         # (ts, type, qty, reference), balances computed after sorting
        i = 0
        while i < len(evs):
            ts, typ, qty, ref = evs[i]
            if qty < 0 and balance + qty < 0:
                # receive enough for this and the next few outbound lines, capped by what is still needed overall
                lookahead = rng.randint(1, 5)
                want = -sum(q for _, _, q, _ in evs[i:i + lookahead] if q < 0) - balance
                want = max(want, -qty - balance)
                rcv = min(remaining_need, max(pack, math.ceil(want / pack) * pack))
                if rcv < -qty - balance:                 # keep the invariant even when the cap bites
                    rcv = -qty - balance
                # dated shortly before this shipment, never before the previous movement (so time order = event order)
                prev_ts = movs[-1][0] if movs else ts - dt.timedelta(days=30)
                rcv_ts = max(prev_ts + dt.timedelta(minutes=1), ts - dt.timedelta(days=rng.randint(1, 6), hours=rng.randint(0, 8)))
                rcv_ts = min(rcv_ts, ts - dt.timedelta(seconds=1))   # always strictly before the shipment it serves
                receipts += 1
                movs.append((rcv_ts, "RECEIPT", rcv, f"PO-{rcv_ts.year}-{po_seq_start + receipts:05d}"))
                balance += rcv
                remaining_need = max(0, remaining_need - rcv)
                continue                                  # re-check the same event with the new balance
            balance += qty
            movs.append((ts, typ, qty, ref))
            i += 1
        if balance != target:
            diff = target - balance
            last = movs[-1][0] if movs else TS.combine(ctx.as_of - dt.timedelta(days=rng.randint(10, 60)), dt.time(9, 0))
            when = min(TS.combine(ctx.as_of, dt.time(16, 0)), last + dt.timedelta(days=rng.randint(1, 12), hours=rng.randint(1, 7)))
            when = max(when, last + dt.timedelta(minutes=1))
            if diff > 0:
                receipts += 1
                movs.append((when, "RECEIPT", diff, f"PO-{when.year}-{po_seq_start + receipts:05d}"))
            else:
                adjustments += 1
                movs.append((when, "ADJUSTMENT", diff, "Stock count"))
        # balances follow time order; receipts were placed so this never dips below zero
        bal = 0
        for ts, typ, qty, ref in sorted(movs, key=lambda m: (m[0], 0 if m[2] > 0 else 1)):   # inbound first on equal timestamps
            bal += qty
            rows.append({"id": 0, "product_id": pid, "warehouse_id": wid, "moved_at": iso(ts), "movement_type": typ,
                         "quantity": qty, "reference": ref, "balance_after": bal})
    rows.sort(key=lambda r: (r["moved_at"], r["product_id"], r["warehouse_id"]))
    for n, r in enumerate(rows, 1):
        r["id"] = n
    ctx.anchors["aftersales"].update({"stock_movements": len(rows), "receipts": receipts, "adjustments": adjustments})


def _mess_name(rng, name):
    return rng.choice([name.upper(), name.lower(), name.replace(" ", "  ", 1), name + " ", name.replace("Sport", "Sports") if "Sport" in name else name.title()])


def _mess_phone(rng, phone):
    digits = phone.replace(" ", "")
    return rng.choice([digits, phone.replace(" ", "-"), phone.replace("+", "00"), phone.replace(" ", ".")])


def _typo(rng, text):
    words = text.split(" ")
    idx = [i for i, w in enumerate(words) if len(w) > 4 and w.isalpha()]
    if not idx:
        return text
    i = rng.choice(idx)
    w = words[i]
    k = rng.randint(1, len(w) - 2)
    words[i] = w[:k] + w[k + 1] + w[k] + w[k + 2:]
    return " ".join(words)


def apply_messiness(ctx: Ctx):
    """Optional: roughen master data like a real system's (config [messy]). Anchor customers, their contacts and
    their orders are left clean. Runs last; disabled by default, so it changes nothing unless asked."""
    if not CFG.get("messy", {}).get("enabled", False):
        ctx.anchors["messy"] = {"enabled": False}
        return
    rng = ctx.rng
    share = cfg("messy", "share")
    anchor_customers = {a["customer_id"] for a in ctx.anchors.get("case2", {}).values()}
    touched = {"customer_names": 0, "contact_phones": 0, "contact_emails": 0, "duplicate_customers": 0, "note_typos": 0}
    for c in ctx.tables["customers"]:
        if c["id"] in anchor_customers:
            continue
        if rng.random() < share:
            c["name"] = _mess_name(rng, c["name"]); touched["customer_names"] += 1
    for k in ctx.tables["customer_contacts"]:
        if k["customer_id"] in anchor_customers:
            continue
        if rng.random() < share:
            k["phone"] = _mess_phone(rng, k["phone"]); touched["contact_phones"] += 1
        if rng.random() < share / 2:
            local, _, dom = k["email"].partition("@")
            k["email"] = local.title() + "@" + dom; touched["contact_emails"] += 1   # mixed-case local part, same address
    # a few near-duplicate customers: same store keyed twice, no orders, as a second record
    pool = [c for c in ctx.tables["customers"] if c["id"] not in anchor_customers and c["segment"] == "CHAIN_STORE"]
    for c in rng.sample(pool, min(len(pool), max(3, int(len(ctx.tables["customers"]) * share / 4)))):
        dup = dict(c)
        dup["id"] = len(ctx.tables["customers"]) + 1
        dup["customer_number"] = f"C-{10000 + dup['id']}"
        dup["name"] = rng.choice([c["name"] + " (old)", c["name"].replace(" ", "-", 1), c["name"] + " " + c["postal_code"].split()[0]])
        dup["active"] = "false"
        ctx.tables["customers"].append(dup); ctx.customers.append(dup)
        touched["duplicate_customers"] += 1
    for o in ctx.tables["orders"]:
        if o["notes"] and o["customer_id"] not in anchor_customers and rng.random() < share:
            o["notes"] = _typo(rng, o["notes"]); touched["note_typos"] += 1
    ctx.anchors["messy"] = {"enabled": True, "share": share, **touched}
