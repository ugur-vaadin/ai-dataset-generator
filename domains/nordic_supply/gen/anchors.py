"""Case 2 anchor orders: the records the customer e-mails refer to."""
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

from .catalogue import _pretty_price, current_price, promo_price_on, ean13, product_description
from dsgen.model import last_weekday_before, next_weekday_after, D, TS, add_business_days, iso, money, months_back
from .ctx import Ctx
from .orders import build_order, to_weekday, ts_on

def find_customer(ctx, name):
    return next(c for c in ctx.customers if c["name"] == name)

def find_products(ctx, sup=None, cat=None, ptype=None, n=1, colour=None, active=True):
    """Anchor product lookup. Filters are relaxed step by step (colour, then type, then supplier)
    so the anchors also work at small --scale where a supplier may lack a product type."""
    rng = ctx.rng
    attempts = [(sup, cat, ptype, colour), (sup, cat, ptype, None), (sup, cat, None, None),
                (None, cat, ptype, None), (None, cat, None, None), (None, None, None, None)]
    for a_sup, a_cat, a_ptype, a_colour in attempts:
        pool = [p for p in ctx.products
                if (a_sup is None or p["_sup"] == a_sup) and (a_cat is None or p["_cat"] == a_cat)
                and (a_ptype is None or p["product_type"] == a_ptype) and (a_colour is None or p["colour"] == a_colour)
                and (not active or p["active"] == "true")]
        if len(pool) >= n:
            return rng.sample(pool, n)
    raise RuntimeError("no products to pick from")

def gen_case2_anchors(ctx: Ctx):
    rng = ctx.rng
    A = {}
    as_of = ctx.as_of

    # A1: "the second pallet from Tuesday's delivery arrived damaged, we need replacements before Friday"
    cust = find_customer(ctx, "Retkiaitta Tampere")
    tuesday = last_weekday_before(as_of, 1)
    tents = find_products(ctx, sup="FJV", cat="TNT", ptype="Tent", n=2)
    bags = find_products(ctx, sup="FJV", cat="SLP", n=2)
    mats = find_products(ctx, sup="FJV", cat="SLP", ptype="Sleeping Mat", n=1)
    specs = [(tents[0], 24, False), (tents[1], 18, False), (bags[0], 30, False), (bags[1], 24, False), (mats[0], 36, False)]
    placed = ts_on(rng, add_business_days(tuesday, -5), 9, 11)
    promised_ship = add_business_days(placed.date(), 2)
    ship_date = add_business_days(tuesday, -1)  # Monday
    order = build_order(ctx, cust, placed, specs, {
        "promised_ship": promised_ship, "ship_delay": (ship_date - promised_ship).days,
        "transit_extra": 0, "carrier": "PostNord", "warehouse_id": 1, "channel": "PORTAL",
        "force_pallets": 2, "price_mode": None, "no_claim": True})
    # make sure the delivery landed exactly on Tuesday: FI transit is 1-2 days; fix the shipment row
    ship = ctx.tables["shipments"][-1]
    _force_delivery_date(ctx, ship, tuesday)
    order["promised_delivery_date"] = iso(tuesday)
    A["A1_damaged_pallet"] = _anchor_info(ctx, order, ship, extra={
        "tuesday": iso(tuesday), "needed_by": iso(next_weekday_after(as_of, 4)),
        "pallet_2_lines": [l["_p"]["name"] for l in order["_lines"] if l.get("_pallet") == 2],
        "pallet_1_lines": [l["_p"]["name"] for l in order["_lines"] if l.get("_pallet") == 1]})

    # A2: missing cartons, no order number in the message, refers to "last Friday" and the store
    cust = find_customer(ctx, "Trailhead Umeå")
    friday = last_weekday_before(as_of, 4)
    boots = find_products(ctx, sup="RUS", cat="FTW", ptype="Hiking Boot", n=1)  # fallback: any FTW
    six = [p for p in ctx.products if p["_sup"] == boots[0]["_sup"] and p["product_type"] == boots[0]["product_type"]
           and p["active"] == "true" and int(p["case_pack"]) == 6]
    if six:
        boots = [rng.choice(six)]
    boots[0]["case_pack"] = 6          # the e-mail counts cartons of 6 pairs; make the catalogue agree
    socks = find_products(ctx, cat="BAS", ptype="Hiking Socks 2-pack", n=1)
    poles = find_products(ctx, cat="ACC", ptype="Trekking Poles", n=1)
    specs = [(boots[0], 48, False), (socks[0], 60, False), (poles[0], 12, False)]
    placed = ts_on(rng, add_business_days(friday, -6), 8, 16)
    promised_ship = add_business_days(placed.date(), 2)
    ship_date = add_business_days(friday, -2)
    order = build_order(ctx, cust, placed, specs, {
        "promised_ship": promised_ship, "ship_delay": (ship_date - promised_ship).days, "transit_extra": 0,
        "carrier": "DB Schenker", "warehouse_id": 2, "channel": "EDI", "no_claim": True})
    ship = ctx.tables["shipments"][-1]
    _force_delivery_date(ctx, ship, friday)
    A["A2_missing_cartons"] = _anchor_info(ctx, order, ship, extra={
        "friday": iso(friday), "boots_ordered": 48, "boots_received": 30, "cartons_of": 6,
        "cartons_ordered": 48 // 6, "cartons_received": 30 // 6, "cartons_missing": (48 - 30) // 6})

    # A3: wrong colour delivered (portal message, terse)
    cust = find_customer(ctx, "Nordkapp Sports Tromsø")
    jackets_blue = [p for p in ctx.products if p["_sup"] == "NVD" and "Jacket" in p["product_type"]
                    and p["colour"] == "Midnight Blue" and p["active"] == "true"]
    jacket = jackets_blue[0] if jackets_blue else find_products(ctx, sup="NVD", cat="SHL", ptype="Rain Jacket", n=1)[0]
    wrong_colour = "Moss Green" if jacket["colour"] != "Moss Green" else "Slate Grey"
    beanies = find_products(ctx, cat="ACC", ptype="Beanie", n=1)
    specs = [(jacket, 20, False), (beanies[0], 40, False)]
    deliv = add_business_days(as_of, -2)
    placed = ts_on(rng, add_business_days(deliv, -6), 8, 16)
    promised_ship = add_business_days(placed.date(), 2)
    order = build_order(ctx, cust, placed, specs, {
        "promised_ship": promised_ship, "ship_delay": 0, "transit_extra": 0, "carrier": "Bring",
        "warehouse_id": 3, "channel": "PORTAL", "no_claim": True})
    ship = ctx.tables["shipments"][-1]
    _force_delivery_date(ctx, ship, deliv)
    received = _ensure_colour_sibling(ctx, jacket, wrong_colour)
    A["A3_wrong_colour"] = _anchor_info(ctx, order, ship, extra={"ordered_colour": jacket["colour"],
                                                                 "received_colour": wrong_colour,
                                                                 "received_product": received["name"],
                                                                 "received_sku": received["sku"]})

    # A4: late delivery for Kiruna season opening, credit request; message contains personal data
    cust = find_customer(ctx, "Fjällbutiken Kiruna")
    skis = find_products(ctx, sup="LUM", cat="WIN", ptype="Touring Ski", n=2)
    skins = find_products(ctx, sup="LUM", cat="WIN", ptype="Climbing Skins", n=1)
    if skins[0]["id"] in (skis[0]["id"], skis[1]["id"]):
        skins = find_products(ctx, cat="WIN", n=1)
    goggles = find_products(ctx, cat="WIN", ptype="Ski Goggles", n=1)
    specs = [(skis[0], 12, False), (skis[1], 8, False), (skins[0], 20, False), (goggles[0], 30, False)]
    promised_delivery = to_weekday(months_back(as_of, 1) + dt.timedelta(days=23))   # ~24th of last month
    placed = ts_on(rng, add_business_days(promised_delivery, -8), 8, 16)
    promised_ship = add_business_days(promised_delivery, -2)
    actual_ship = add_business_days(promised_ship, 4)
    order = build_order(ctx, cust, placed, specs, {
        "promised_ship": promised_ship, "ship_delay": (actual_ship - promised_ship).days, "transit_extra": 3,
        "carrier": "Baltic Freight Line", "warehouse_id": 2, "channel": "EMAIL", "no_claim": True})
    ship = ctx.tables["shipments"][-1]
    order["promised_delivery_date"] = iso(promised_delivery)
    A["A4_late_delivery"] = _anchor_info(ctx, order, ship, extra={"promised_delivery": iso(promised_delivery),
                                                                  "season_opening": iso(to_weekday(promised_delivery + dt.timedelta(days=3)))})

    # A5: quality defect, written in Swedish, ~3 weeks after delivery
    cust = find_customer(ctx, "Trailhead Umeå")
    jackets = find_products(ctx, sup="NVD", cat="SHL", ptype="Softshell Jacket", n=1)
    fleece = find_products(ctx, cat="BAS", ptype="Fleece Jacket", n=1)
    specs = [(jackets[0], 24, False), (fleece[0], 18, False)]
    deliv = add_business_days(as_of, -16)
    placed = ts_on(rng, add_business_days(deliv, -5), 8, 16)
    promised_ship = add_business_days(placed.date(), 2)
    order = build_order(ctx, cust, placed, specs, {"promised_ship": promised_ship, "ship_delay": 0, "transit_extra": 0,
                                                    "carrier": "PostNord", "warehouse_id": 2, "channel": "PORTAL", "no_claim": True})
    ship = ctx.tables["shipments"][-1]
    _force_delivery_date(ctx, ship, deliv)
    A["A5_quality_defect_sv"] = _anchor_info(ctx, order, ship, extra={"defective_qty": 6})

    # A6: pricing dispute — promotion existed but list price was charged
    cust = find_customer(ctx, "Sportmagasinet Aarhus")
    placed6 = add_business_days(as_of, -6)
    promo_headlamps = [p for p in ctx.products if p["product_type"] == "Headlamp" and p["active"] == "true"
                       and any(s <= placed6 <= e for s, e, _ in ctx.promos_by_product.get(p["id"], []))]
    if not promo_headlamps:
        # make one: put a promotion on a headlamp covering the order date
        p = find_products(ctx, cat="NAV", ptype="Headlamp", n=1)[0]
        pid = len(ctx.tables["promotions"]) + 1
        base = current_price(ctx, p["id"], as_of)
        pp = _pretty_price(round(base * 0.85, 2))
        s, e = placed6 - dt.timedelta(days=10), placed6 + dt.timedelta(days=20)
        ctx.tables["promotions"].append({"id": pid, "product_id": p["id"], "name": "Season Opener", "discount_pct": "15.0",
                                         "promo_price": money(pp), "starts_on": iso(s), "ends_on": iso(e),
                                         "created_by": ctx.users_by_role["CATALOGUE_MANAGER"][0]})
        ctx.promos_by_product[p["id"]].append((s, e, pp))
        promo_headlamps = [p]
    lamp = promo_headlamps[0]
    lantern = find_products(ctx, cat="NAV", ptype="Camp Lantern", n=1)
    specs = [(lamp, 36, False), (lantern[0], 12, False)]
    placed = ts_on(rng, placed6, 9, 12)
    promised_ship = add_business_days(placed.date(), 1)
    order = build_order(ctx, cust, placed, specs, {"promised_ship": promised_ship, "ship_delay": 0, "transit_extra": 0,
                                                    "carrier": "DSV", "warehouse_id": 2, "channel": "EMAIL",
                                                    "price_mode": "list", "no_claim": True})
    ship = ctx.tables["shipments"][-1] if ctx.tables["shipments"][-1]["order_id"] == order["id"] else None
    if ship:
        deliv6 = add_business_days(as_of, -1)
        _force_delivery_date(ctx, ship, deliv6)
        order["promised_delivery_date"] = iso(deliv6)
    promo_row = next((r for r in ctx.tables["promotions"] if r["product_id"] == lamp["id"]
                      and D.fromisoformat(r["starts_on"]) <= placed.date() <= D.fromisoformat(r["ends_on"])), None)
    A["A6_pricing_dispute"] = _anchor_info(ctx, order, ship, extra={
        "promo_name": promo_row["name"] if promo_row else "promotion",
        "invoiced_unit_price": order["_lines"][0]["unit_price"],
        "expected_promo_price": money(promo_price_on(ctx, lamp["id"], placed.date()) or 0)})

    ctx.anchors["case2"] = A

def _ensure_colour_sibling(ctx, product, colour):
    """Return the same model/variant in another colour; create the SKU (with price history) if the
    catalogue lacks it, so a wrong-colour claim can point at a real product. Inventory is generated later."""
    base = product["name"].replace(product["colour"], "").strip() if product["colour"] else product["name"]
    for p in ctx.products:
        if p["colour"] == colour and p["name"].replace(colour, "").strip() == base:
            return p
    rng = ctx.rng
    prefix = product["sku"].rsplit("-", 1)[0]
    seq = max(int(p["sku"].rsplit("-", 1)[1]) for p in ctx.products if p["sku"].startswith(prefix + "-")) + 1
    pid = max(p["id"] for p in ctx.products) + 1
    row = dict(product)
    row.update({"id": pid, "sku": f"{prefix}-{seq:04d}", "ean": ean13(pid), "colour": colour,
                "name": product["name"].replace(product["colour"], colour) if product["colour"] else f"{product['name']} {colour}"})
    brand = row["name"].split()[0]
    row["description"] = product_description(pid, brand, row["name"].split()[1] if len(row["name"].split()) > 1 else "",
                                             product["product_type"], "", product["variant"], colour)
    ctx.tables["products"].append(row)
    ctx.products.append(row)
    hid = max(r["id"] for r in ctx.tables["price_history"])
    for r in [r for r in ctx.tables["price_history"] if r["product_id"] == product["id"]]:
        hid += 1
        ctx.tables["price_history"].append(dict(r, id=hid, product_id=pid))
    ctx.price_at[pid] = list(ctx.price_at[product["id"]])
    return row

def _force_delivery_date(ctx, ship, day: D):
    """Move a freshly built shipment's delivery to an exact day (keeps events consistent).
    If the natural flow had not delivered the shipment yet, the delivery is created."""
    rng = ctx.rng
    day = max(day, ship["_ship_date"])
    ship["expected_delivery_date"] = iso(day)
    ship["_delivered_date"] = day
    if ship["delivered_at"]:
        old = TS.fromisoformat(ship["delivered_at"])
        ship["delivered_at"] = iso(TS.combine(day, old.time()))
        for e in ctx.tables["delivery_events"]:
            if e["shipment_id"] == ship["id"] and e["event_type"] in ("OUT_FOR_DELIVERY", "DELIVERED"):
                t = TS.fromisoformat(e["event_time"])
                e["event_time"] = iso(TS.combine(day, t.time()))
        return
    delivered_at = ts_on(rng, day, 8, 15)
    ship["delivered_at"] = iso(delivered_at)
    ship["status"] = "DELIVERED"
    order = next(o for o in ctx.tables["orders"] if o["id"] == ship["order_id"])
    city = order["_customer"]["city"]
    ctx.tables["delivery_events"] = [e for e in ctx.tables["delivery_events"]
                                     if not (e["shipment_id"] == ship["id"] and e["event_type"] in ("EXCEPTION", "DELAYED"))]
    for t, typ, note in ((TS.combine(day, dt.time(7, rng.randint(0, 59))), "OUT_FOR_DELIVERY", ""),
                         (delivered_at, "DELIVERED", "Signed at goods entrance")):
        ctx.tables["delivery_events"].append({"id": len(ctx.tables["delivery_events"]) + 1, "shipment_id": ship["id"],
                                              "event_time": iso(t), "event_type": typ, "location": city, "note": note})
    if all(l["status"] == "SHIPPED" for l in order["_lines"]):
        order["status"] = "DELIVERED"

def _anchor_info(ctx, order, ship, extra=None):
    cust = order["_customer"]
    contact = ctx.contacts_by_customer[cust["id"]][0]
    info = {"order_number": order["order_number"], "order_id": order["id"], "customer": cust["name"],
            "customer_number": cust["customer_number"], "customer_id": cust["id"],
            "contact": f"{contact['first_name']} {contact['last_name']}", "contact_email": contact["email"],
            "contact_phone": contact["phone"], "contact_id": contact["id"],
            "placed_at": order["placed_at"], "promised_delivery_date": order["promised_delivery_date"],
            "lines": [{"line": l["line_number"], "product": l["_p"]["name"], "sku": l["_p"]["sku"], "qty": l["quantity"],
                       "unit_price": l["unit_price"], "pallet": l.get("_pallet")} for l in order["_lines"]]}
    if ship:
        info.update({"shipment_number": ship["shipment_number"], "shipment_id": ship["id"], "carrier": ship["carrier"],
                     "shipped_at": ship["shipped_at"], "delivered_at": ship["delivered_at"],
                     "pallet_count": ship["pallet_count"], "package_count": ship["package_count"]})
    info.update(extra or {})
    return info
