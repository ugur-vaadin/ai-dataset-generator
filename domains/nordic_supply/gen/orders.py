"""Orders, order lines, shipments, shipment lines and delivery events, including the late-shipment model."""
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

from .catalogue import current_price, promo_price_on
from dsgen.model import D, TS, add_business_days, cfg, first_of_next_month, iso, money, months_back, weighted_choice
from .ctx import Ctx
from .pools import CHANNELS, DELAY_REASONS, HUBS, SEASON_FACTOR, TRANSIT_DAYS, WAREHOUSES

def season_factor(season, month):
    return SEASON_FACTOR[season].get(month, 1.0 if season == "ALL" else 0.55)

def warehouse_for(rng, country):
    if country in ("FI", "EE"):
        return 1
    if country == "NO":
        return 3 if rng.random() < 0.4 else 2
    return 2

def next_seq(ctx, key):
    ctx.anchors.setdefault("_seq", {})
    ctx.anchors["_seq"][key] = ctx.anchors["_seq"].get(key, 0) + 1
    return ctx.anchors["_seq"][key]

def outage_window(ctx):
    """Göteborg WMS outage: the second full week (Mon-Sun) of last month, relative to as_of."""
    last_month = months_back(ctx.as_of, 1)
    first_monday = last_month + dt.timedelta(days=(7 - last_month.weekday()) % 7)
    start = first_monday + dt.timedelta(days=7)
    return start, start + dt.timedelta(days=6)

def ship_delay_days(ctx, promised_ship: D, warehouse_id: int):
    rng = ctx.rng
    L = cfg("late")
    o_start, o_end = outage_window(ctx)
    if warehouse_id == 2 and o_start <= promised_ship <= o_end and rng.random() < L["outage_late_prob"]:
        return rng.randint(L["outage_delay_min"], L["outage_delay_max"])
    p_late = L["base_late_dispatch_prob"]
    if promised_ship.month in (11, 12):
        p_late += L["nov_dec_extra"]
    if promised_ship.month == 9:
        p_late += L["september_extra"]
    if rng.random() < p_late:
        return min(L["max_delay_days"], 1 + int(rng.expovariate(1 / L["mean_delay_days"])))
    return rng.choice([0, 0, 0, 0, 0, -1])

def transit_extra_days(ctx, carrier: str, shipped: D):
    rng = ctx.rng
    last_month = months_back(ctx.as_of, 1)
    if carrier == cfg("carriers", "bad_carrier") and shipped >= last_month and rng.random() < cfg("carriers", "bad_carrier_delay_prob"):
        return rng.randint(2, 5)
    if rng.random() < cfg("late", "transit_extra_prob"):
        return rng.randint(1, 3)
    return 0

def to_weekday(d: D) -> D:
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d

def ts_on(rng, d: D, h0=7, h1=17) -> TS:
    return TS.combine(d, dt.time(rng.randint(h0, h1), rng.randint(0, 59), rng.randint(0, 59)))

def build_order(ctx: Ctx, customer, placed_at: TS, line_specs, ov=None):
    """Create one order with its lines, shipments, shipment lines and delivery events.

    line_specs: list of (product_row, qty, backordered: bool)
    ov (overrides, all optional): promised_ship (date), ship_delay (int days), transit_extra (int),
        carrier, warehouse_id, channel, address_id, price_mode ('list' ignores promotions),
        force_pallets (int minimum pallets), cancelled (bool), no_claim (bool)
    Returns the order row.
    """
    rng = ctx.rng
    ov = ov or {}
    placed = placed_at.date()
    country = customer["country"]
    oid = len(ctx.tables["orders"]) + 1
    year_seq = next_seq(ctx, f"SO{placed.year}")
    addr = ov.get("address_id") or (ctx.addresses_by_customer[customer["id"]][0]["id"]
                                    if rng.random() < 0.8 else rng.choice(ctx.addresses_by_customer[customer["id"]])["id"])
    channel = ov.get("channel") or (weighted_choice(rng, CHANNELS, [45, 35, 14, 6]) if customer["chain_name"]
                                    else weighted_choice(rng, CHANNELS, [8, 52, 28, 12]))
    created_by = rng.choice(ctx.users_by_role["ACCOUNT_MANAGER"]) if channel in ("EMAIL", "PHONE") else ""
    warehouse_id = ov.get("warehouse_id") or warehouse_for(rng, country)
    carrier = ov.get("carrier") or weighted_choice(rng, cfg("carriers", "names"), cfg("carriers", "weights"))
    cancelled = ov.get("cancelled", False)
    disc = float(customer["customer_discount_pct"])

    promised_ship = ov.get("promised_ship") or add_business_days(placed, weighted_choice(rng, [1, 2, 3], [35, 45, 20]))
    t_lo, t_hi = TRANSIT_DAYS[country]
    base_transit = rng.randint(t_lo, t_hi)
    promised_delivery = to_weekday(promised_ship + dt.timedelta(days=base_transit))
    requested_delivery = promised_delivery if rng.random() < 0.6 else to_weekday(promised_delivery + dt.timedelta(days=rng.randint(-2, 7)))

    # ---- lines
    lines = []
    total_net = 0.0
    any_bo = False
    for ln_no, (p, qty, bo) in enumerate(line_specs, start=1):
        list_price = current_price(ctx, p["id"], placed)
        promo = None if ov.get("price_mode") == "list" else promo_price_on(ctx, p["id"], placed)
        unit = promo if promo is not None else list_price
        line_total = round(qty * unit * (1 - disc / 100), 2)
        total_net += line_total
        lid = len(ctx.tables["order_lines"]) + 1
        restock = to_weekday(promised_ship + dt.timedelta(days=rng.randint(7, 35))) if bo else None
        row = {"id": lid, "order_id": oid, "line_number": ln_no, "product_id": p["id"], "quantity": qty,
               "unit_price": money(unit), "list_price": money(list_price),
               "promotion_applied": "true" if promo is not None else "false",
               "discount_pct": f"{disc:.1f}", "line_total": money(line_total),
               "status": "CANCELLED" if cancelled else "OPEN",
               "backordered_qty": qty if bo else 0, "expected_restock_date": iso(restock),
               "_p": p, "_bo": bo, "_restock": restock}
        ctx.tables["order_lines"].append(row)
        lines.append(row)
        any_bo = any_bo or bo

    order = {"id": oid, "order_number": f"SO-{placed.year}-{year_seq:06d}", "customer_id": customer["id"],
             "delivery_address_id": addr, "placed_at": iso(placed_at), "channel": channel,
             "status": "CANCELLED" if cancelled else "OPEN",
             "requested_delivery_date": iso(requested_delivery), "promised_ship_date": iso(promised_ship),
             "promised_delivery_date": iso(promised_delivery), "currency": "EUR",
             "total_net": money(total_net), "warehouse_id": warehouse_id, "created_by": created_by,
             "customer_reference": (f"PO-{rng.randint(1000, 99999)}" if rng.random() < 0.55 else ""),
             "notes": _order_note(ctx, customer)}
    ctx.tables["orders"].append(order)
    if cancelled:
        return order

    # ---- shipments: one for available lines, a later one for backordered lines
    groups = []
    main = [l for l in lines if not l["_bo"]]
    bo = [l for l in lines if l["_bo"]]
    if main:
        groups.append((main, promised_ship))
    if bo:
        planned = add_business_days(max(l["_restock"] for l in bo), rng.randint(0, 2))
        groups.append((bo, planned))

    shipped_lines = 0
    delivered_shipments = 0
    n_ships = 0
    for glines, planned in groups:
        delay = ov.get("ship_delay") if ov.get("ship_delay") is not None and planned == promised_ship \
            else ship_delay_days(ctx, planned, warehouse_id)
        ship_date = to_weekday(max(planned + dt.timedelta(days=delay), placed))
        if ship_date > ctx.as_of:
            # not shipped yet: lines stay OPEN / BACKORDERED
            for l in glines:
                l["status"] = "BACKORDERED" if l["_bo"] else "OPEN"
            continue
        shipped_at = ts_on(rng, ship_date, 9, 18)
        extra = ov.get("transit_extra") if ov.get("transit_extra") is not None and planned == promised_ship \
            else transit_extra_days(ctx, carrier, ship_date)
        expected_delivery = to_weekday(ship_date + dt.timedelta(days=base_transit))
        delivered_date = to_weekday(ship_date + dt.timedelta(days=base_transit + extra))
        delivered = delivered_date <= ctx.as_of
        delivered_at = ts_on(rng, delivered_date, 8, 15) if delivered else None
        weight = sum(l["quantity"] * float(l["_p"]["weight_kg"]) for l in glines)
        units = sum(l["quantity"] for l in glines)
        pallets = 0 if weight < 40 else math.ceil(weight / 250)
        pallets = max(pallets, ov.get("force_pallets", 0)) if planned == promised_ship else pallets
        packages = math.ceil(units / 6) if pallets == 0 else pallets * rng.randint(4, 12)
        sid = len(ctx.tables["shipments"]) + 1
        n_ships += 1
        status = "DELIVERED" if delivered else "IN_TRANSIT"
        exc_time = ts_on(rng, to_weekday(ship_date + dt.timedelta(days=2)), 8, 18)
        exception = (not delivered) and rng.random() < 0.05 and exc_time.date() <= ctx.as_of
        if exception:
            status = "EXCEPTION"
        ship = {"id": sid, "shipment_number": f"SH-{ship_date.year}-{next_seq(ctx, f'SH{ship_date.year}'):06d}",
                "order_id": oid, "warehouse_id": warehouse_id, "delivery_address_id": addr, "carrier": carrier,
                "tracking_number": f"{carrier[:2].upper()}{rng.randint(10**9, 10**10 - 1)}",
                "shipped_at": iso(shipped_at), "expected_delivery_date": iso(expected_delivery),
                "delivered_at": iso(delivered_at), "status": status, "pallet_count": pallets,
                "package_count": packages, "weight_kg": f"{weight:.1f}",
                "_ship_date": ship_date, "_delivered_date": delivered_date if delivered else None, "_extra": extra}
        ctx.tables["shipments"].append(ship)
        # shipment lines with pallet numbers (heaviest lines first onto pallet 1, 2, ...)
        ordered = sorted(glines, key=lambda l: -l["quantity"] * float(l["_p"]["weight_kg"]))
        for i, l in enumerate(ordered):
            l["status"] = "SHIPPED"
            l["_pallet"] = (i % pallets) + 1 if pallets else None
            l["_shipment_id"] = sid
            ctx.tables["shipment_lines"].append({"id": len(ctx.tables["shipment_lines"]) + 1, "shipment_id": sid,
                                                 "order_line_id": l["id"], "quantity": l["quantity"],
                                                 "pallet_number": l["_pallet"] if pallets else ""})
            shipped_lines += 1
        # delivery events
        wh_city = WAREHOUSES[warehouse_id - 1][4]
        ev = []
        pick_day = add_business_days(ship_date, -1) if rng.random() < 0.6 else ship_date
        t_pick = ts_on(rng, pick_day, 6, 11)
        ev.append((t_pick, "PICKED", wh_city, f"{units} units picked"))
        ev.append((t_pick + dt.timedelta(hours=rng.randint(1, 4)), "PACKED", wh_city,
                   f"{pallets} pallet(s)" if pallets else f"{packages} parcel(s)"))
        ev.append((shipped_at, "DISPATCHED", wh_city, f"Handed to {carrier}"))
        hub_t = ts_on(rng, to_weekday(ship_date + dt.timedelta(days=1)), 0, 6)
        if hub_t <= TS.combine(ctx.as_of, dt.time(23, 59)):
            ev.append((hub_t, "HUB_SCAN", HUBS[country], "Arrived at terminal"))
        if extra > 0:
            reason = rng.choice(DELAY_REASONS[:-1] if country != "NO" else DELAY_REASONS)
            dt_delay = ts_on(rng, to_weekday(ship_date + dt.timedelta(days=1 + rng.randint(0, max(0, extra - 1)))), 6, 20)
            if dt_delay <= TS.combine(ctx.as_of, dt.time(23, 59)):
                ev.append((dt_delay, "DELAYED", HUBS[country], reason))
        if delivered:
            if rng.random() < 0.03:
                ev.append((ts_on(rng, add_business_days(delivered_date, -1), 9, 16), "DELIVERY_ATTEMPTED",
                           customer["city"], "Receiver closed, new attempt next working day"))
            ev.append((TS.combine(delivered_date, dt.time(7, rng.randint(0, 59))), "OUT_FOR_DELIVERY", customer["city"], ""))
            contact = ctx.contacts_by_customer[customer["id"]][0]
            ev.append((delivered_at, "DELIVERED", customer["city"],
                       rng.choice([f"Signed by {contact['first_name'][0]}. {contact['last_name']}",
                                   "Signed at goods entrance", "Left at loading bay as instructed",
                                   f"Signed by {contact['first_name']} {contact['last_name']}"])))
            delivered_shipments += 1
        elif exception:
            ev.append((exc_time, "EXCEPTION", HUBS[country],
                       rng.choice(["Pallet damaged in terminal, inspection pending", "Address not found",
                                   "Receiver refused partial delivery"])))
        for t, typ, loc, note in ev:
            ctx.tables["delivery_events"].append({"id": len(ctx.tables["delivery_events"]) + 1, "shipment_id": sid,
                                                  "event_time": iso(t), "event_type": typ, "location": loc, "note": note})

    # ---- order status
    for l in lines:
        if l["status"] == "OPEN" and l["_bo"]:
            l["status"] = "BACKORDERED"
    if shipped_lines == 0:
        order["status"] = "OPEN" if (ctx.as_of - placed).days <= 1 else "CONFIRMED"
    elif shipped_lines < len(lines):
        order["status"] = "PARTIALLY_SHIPPED"
    elif delivered_shipments == n_ships:
        order["status"] = "DELIVERED"
    else:
        order["status"] = "SHIPPED"
    order["_lines"] = lines
    order["_customer"] = customer
    order["_no_claim"] = ov.get("no_claim", False)
    return order

def _order_note(ctx, customer):
    """Realistic order notes; a configurable share names a contact or a phone number (the personal data
    that real free-text fields carry, and that the masking demo has to catch)."""
    rng = ctx.rng
    if rng.random() < cfg("pii", "free_text_share"):
        c = rng.choice(ctx.contacts_by_customer[customer["id"]])
        return rng.choice([f"Call {c['first_name']} {c['last_name']} on {c['phone']} 30 min before delivery",
                           f"Contact {c['first_name']} ({c['email']}) if the loading bay is closed",
                           f"Receiver: {c['first_name']} {c['last_name']}, {c['phone']}",
                           f"{c['first_name']} asked for delivery after 10:00, mobile {c['phone']}"])
    return rng.choice(["", "", "", "", "Deliver before store opening", "Season opener stock",
                       "Part of annual pre-order", "Customer collects if not delivered by Friday"])


def gen_orders(ctx: Ctx):
    rng = ctx.rng
    # per-product popularity (heavy tail) and "short stock" set that drives backorders
    pop = {p["id"]: min(40.0, rng.paretovariate(1.3)) for p in ctx.products}
    B = cfg("backorder")
    short = set()
    for p in ctx.products:
        r = rng.random()
        if (p["_cat"] == "WIN" and r < B["winter_sports_short_share"]) or \
           (p["_sup"] == "FJV" and p["_cat"] == "TNT" and r < B["fjellvind_tents_short_share"]) or r < B["short_stock_share"]:
            short.add(p["id"])
    ctx.anchors["short_stock_products"] = len(short)
    ctx.anchors["_short_ids"] = short
    month_volume = cfg("month_volume")
    per_month = cfg("volume", "orders_per_month")
    cancel_rate = cfg("claims", "cancel_rate")
    cust_weights = [c["_weight"] for c in ctx.customers]

    start = ctx.history_start
    month = start
    while month <= ctx.as_of:
        days_in_month = (first_of_next_month(month) - month).days
        n = int(per_month * ctx.scale * month_volume[str(month.month)])
        if first_of_next_month(month) > ctx.as_of:  # partial current month
            n = int(n * ((ctx.as_of - month).days + 1) / days_in_month)
        # product weights for this month
        cands, ws = [], []
        for p in ctx.products:
            created = D.fromisoformat(p["created_at"])
            if created > month:
                continue
            if p["discontinued_on"] and D.fromisoformat(p["discontinued_on"]) < month:
                continue
            cands.append(p)
            ws.append(p["_demand"] * season_factor(p["_season"], month.month) * pop[p["id"]])
        for _ in range(n):
            day = month + dt.timedelta(days=rng.randint(0, days_in_month - 1))
            if day > ctx.as_of:
                continue
            if day.weekday() >= 5 and rng.random() < 0.85:
                day = to_weekday(day)
                if day > ctx.as_of:
                    continue
            placed_at = ts_on(rng, day, 7, 17)
            customer = rng.choices(ctx.customers, weights=cust_weights, k=1)[0]
            if D.fromisoformat(customer["created_at"]) > day:
                continue
            n_lines = weighted_choice(rng, [1, 2, 3, 4, 5, 6, 8, 10, 12], [14, 18, 18, 15, 12, 9, 7, 4, 3])
            picked = rng.choices(cands, weights=ws, k=n_lines)
            seen, specs = set(), []
            recent = (ctx.as_of - day).days <= B["recent_days"]
            for p in picked:
                if p["id"] in seen:
                    continue
                seen.add(p["id"])
                pack = p["case_pack"]
                qty = pack * rng.choice([1, 1, 2, 2, 3, 4, 5, 8]) if pack > 1 else rng.choice([1, 2, 2, 3, 4, 5, 6, 8, 10, 12, 20])
                if p["id"] in short:
                    bo = rng.random() < (B["short_recent_prob"] if recent else B["short_old_prob"])
                else:
                    bo = rng.random() < (B["normal_recent_prob"] if recent else B["normal_old_prob"])
                specs.append((p, qty, bo))
            ov = {"cancelled": rng.random() < cancel_rate}
            build_order(ctx, customer, placed_at, specs, ov)
        month = first_of_next_month(month)
