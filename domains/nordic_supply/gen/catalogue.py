"""Reference data and catalogue: users, warehouses, categories, suppliers, products, prices, promotions, inventory."""
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

from dsgen.model import D, TS, cfg, first_of_next_month, iso, money, slug
from .ctx import Ctx
from .pools import CATEGORIES, CAT_BY_CODE, CITIES, COLORS, LINES, MODEL_NAMES, SUPPLIERS, UNITS, USERS, VARIANT_POOL, WAREHOUSES

def gen_users(ctx: Ctx):
    for i, (username, full_name, role) in enumerate(USERS, start=1):
        row = {"id": i, "username": username, "full_name": full_name,
               "email": f"{username}@nordicsupply.example", "role": role, "active": "true",
               "created_at": iso(TS(2018, 6, 4, 9, 0, 0) + dt.timedelta(days=i * 37))}
        ctx.tables["users"].append(row)
        ctx.users_by_role[role].append(i)

def gen_warehouses(ctx: Ctx):
    for wid, code, name, country, city, postal in WAREHOUSES:
        ctx.tables["warehouses"].append({"id": wid, "code": code, "name": name, "country": country,
                                         "city": city, "postal_code": postal})

def gen_categories(ctx: Ctx):
    for i, c in enumerate(CATEGORIES, start=1):
        ctx.tables["categories"].append({"id": i, "code": c.code, "name": c.name,
                                         "season": c.season})

def gen_suppliers(ctx: Ctx):
    rng = ctx.rng
    for i, s in enumerate(SUPPLIERS, start=1):
        city, _ = rng.choice(CITIES[s.country])
        ctx.tables["suppliers"].append({
            "id": i, "code": s.code, "name": s.name, "country": s.country, "city": city,
            "contact_email": f"orders@{slug(s.name.split()[0])}.example",
            "lead_time_days": s.lead_time_days, "active": "true",
        })

def _variant(rng, kind):
    return rng.choice(VARIANT_POOL[kind])

def gen_products(ctx: Ctx):
    """Products with realistic names; SKU = SUP-CAT-NNNN. Case 3 anchor supplier gets exactly
    product_count active products spread over exactly its three categories."""
    rng = ctx.rng
    cat_ids = {c.code: i for i, c in enumerate(CATEGORIES, start=1)}
    sup_ids = {s.code: i for i, s in enumerate(SUPPLIERS, start=1)}
    target_total = int(cfg("volume", "products") * ctx.scale)
    fixed_total = sum(s.product_count for s in SUPPLIERS if s.product_count)
    flexible = [s for s in SUPPLIERS if not s.product_count]
    # weight flexible suppliers by demand of their categories
    weights = [math.fsum(CAT_BY_CODE[c].demand for c in s.categories) for s in flexible]
    wsum = math.fsum(weights)
    remaining = max(0, target_total - fixed_total)
    counts = {s.code: max(12, int(round(remaining * w / wsum))) for s, w in zip(flexible, weights)}
    for s in SUPPLIERS:
        if s.product_count:
            counts[s.code] = s.product_count

    pid = 0
    used_names = set()
    seq_by_supcat = Counter()
    for s in SUPPLIERS:
        n = counts[s.code]
        brand = s.name.split()[0]
        # spread across categories: anchor gets ~90/80/70 split, others weighted by demand
        if s.is_case3_anchor:
            split = [90, 80, 70]
            per_cat = dict(zip(s.categories, split))
            assert sum(split) == n
        else:
            ws = [CAT_BY_CODE[c].demand for c in s.categories]
            per_cat = {}
            left = n
            for c, w in zip(s.categories[:-1], ws[:-1]):
                k = int(round(n * w / math.fsum(ws)))
                per_cat[c] = k
                left -= k
            per_cat[s.categories[-1]] = left
        for ccode, k in per_cat.items():
            cat = CAT_BY_CODE[ccode]
            # build families: a model name + type, expanded into variants
            made = 0
            while made < k:
                tname, kind, mult = rng.choice(cat.types)
                model = rng.choice(MODEL_NAMES) + rng.choice(LINES)
                base = rng.uniform(*cat.price_range) * mult
                base = max(2.5, base)
                pool = VARIANT_POOL[kind]
                nvar = 1 if kind == "NONE" else min(len(pool), rng.choice([1, 2, 3, 3, 4, 5]))
                variants = rng.sample(pool, nvar) if nvar > 1 else [rng.choice(pool)]
                # pick a colour as well for size-based apparel/footwear, so names differ
                colour = rng.choice(COLORS) if kind in ("SIZE", "SHOE", "PERSONS", "TEMP", "LITRES",
                                                        "LITRES_SMALL", "LITRES_BIG", "LENGTH") else None
                for v in variants:
                    if made >= k:
                        break
                    pid += 1
                    seq_by_supcat[(s.code, ccode)] += 1
                    seq = seq_by_supcat[(s.code, ccode)]
                    parts = [brand, model, tname]
                    if v:
                        parts.append(v)
                    if colour and kind not in ("COLOR",):
                        parts.append(colour)
                    name = " ".join(parts)
                    if name in used_names:                     # same brand+model+type+variant twice: another colour, else a mark
                        alt = [c for c in COLORS if c != colour and " ".join(parts[:-1] + [c]) not in used_names] if colour and kind not in ("COLOR",) else []
                        if alt:
                            colour = alt[0]; parts[-1] = colour        # deterministic, no RNG draw: the rest of the data stays as it was
                        else:
                            parts.insert(2, "Mk II")
                        name = " ".join(parts)
                    used_names.add(name)
                    weight = round(rng.uniform(*cat.weight_range) * (mult if mult > 0.3 else 0.3), 3)
                    created = D(2019, 1, 1) + dt.timedelta(days=rng.randint(0, (ctx.as_of - D(2019, 1, 1)).days - 120))
                    # ~7% of catalogue discontinued (not for the anchor supplier: its 240 are all active)
                    discontinued = None
                    if not s.is_case3_anchor and rng.random() < 0.07:
                        discontinued = created + dt.timedelta(days=rng.randint(200, 1400))
                        if discontinued > ctx.as_of:
                            discontinued = None
                    pack = {"pcs": rng.choice([1, 1, 1, 6, 12]), "pair": rng.choice([1, 6])}[UNITS[kind]]
                    row = {
                        "id": pid,
                        "sku": f"{s.code}-{ccode}-{seq:04d}",
                        "name": name,
                        "category_id": cat_ids[ccode],
                        "supplier_id": sup_ids[s.code],
                        "product_type": tname,
                        "variant": v or "",
                        "colour": colour or (v if kind == "COLOR" else ""),
                        "unit": UNITS[kind],
                        "case_pack": pack,
                        "weight_kg": f"{weight:.3f}",
                        "active": "false" if discontinued else "true",
                        "discontinued_on": iso(discontinued),
                        "created_at": iso(created),
                        "_base_price": base,   # internal, removed before writing
                        "_cat": ccode, "_sup": s.code, "_season": cat.season, "_demand": cat.demand,
                    }
                    row["ean"] = ean13(pid)
                    row["description"] = product_description(pid, brand, model, tname, cat.name, v, colour)
                    row["min_order_qty"] = pack
                    ctx.tables["products"].append(row)
                    ctx.products.append(row)
                    ctx.products_by_cat[ccode].append(row)
                    made += 1
    ctx.anchors["case3_supplier"] = {
        "supplier_id": sup_ids["FJV"], "code": "FJV", "name": "Skarvind AS",
        "categories": ["Tents & Shelters", "Sleeping Bags & Mats", "Backpacks & Bags"],
        "active_products": sum(1 for p in ctx.products if p["_sup"] == "FJV" and p["active"] == "true"),
    }

def gen_price_history(ctx: Ctx):
    """1-4 price rows per product: initial price at creation, then changes typically on 1 Jan / 1 Jul.
    The current row has valid_to = NULL. A handful of already-scheduled future prices exist so the
    'starts on the first of next month' pattern is visible in the data before case 3 adds more."""
    rng = ctx.rng
    hid = 0
    cat_mgrs = ctx.users_by_role["CATALOGUE_MANAGER"]
    scheduled = 0
    for p in ctx.products:
        created = D.fromisoformat(p["created_at"])
        price = round(p["_base_price"] * rng.uniform(0.82, 0.95), 2)
        price = _pretty_price(price)
        rows = [(created, price, "Initial listing")]
        # candidate change dates: every 1 Jan and 1 Jul after creation
        d = created
        while True:
            nxt = D(d.year + (1 if d.month >= 7 else 0), 1 if d.month >= 7 else 7, 1)
            if nxt > ctx.as_of:
                break
            if rng.random() < 0.42:
                pct = rng.choice([0.02, 0.025, 0.03, 0.035, 0.04, 0.05, 0.06, -0.03, -0.05])
                price = _pretty_price(round(price * (1 + pct), 2))
                reason = rng.choice(["Annual price update", "Supplier increase", "Currency adjustment",
                                     "Range repositioning", "Cost update"]) if pct > 0 else \
                         rng.choice(["Clearance", "Competitive adjustment"])
                rows.append((nxt, price, reason))
            d = nxt
        # scheduled future increase for a few non-anchor products (already planned)
        if p["_sup"] != "FJV" and p["active"] == "true" and scheduled < 25 and rng.random() < 0.012:
            fut = first_of_next_month(ctx.as_of)
            fprice = _pretty_price(round(price * 1.03, 2))
            rows.append((fut, fprice, "Scheduled supplier increase"))
            scheduled += 1
        rows.sort()
        # write with valid_to = next valid_from - 1 day
        hist = []
        for i, (vf, pr, reason) in enumerate(rows):
            hid += 1
            vt = rows[i + 1][0] - dt.timedelta(days=1) if i + 1 < len(rows) else None
            ctx.tables["price_history"].append({
                "id": hid, "product_id": p["id"], "list_price": money(pr), "currency": "EUR",
                "valid_from": iso(vf), "valid_to": iso(vt), "reason": reason,
                "created_by": rng.choice(cat_mgrs),
                "created_at": iso(TS.combine(vf - dt.timedelta(days=rng.randint(3, 30)), dt.time(rng.randint(8, 16), rng.randint(0, 59)))),
            })
            hist.append((vf, pr))
        ctx.price_at[p["id"]] = hist
    ctx.anchors["scheduled_future_prices"] = scheduled

def _pretty_price(x: float) -> float:
    """Wholesale-looking prices: two decimals, ending .90/.50/.00 for larger amounts."""
    if x >= 50:
        return math.floor(x) + 0.90 if x - math.floor(x) >= 0.45 else math.floor(x) + 0.50 if x - math.floor(x) >= 0.2 else float(math.floor(x))
    return round(x, 2)

def current_price(ctx: Ctx, product_id: int, on: D) -> float:
    hist = ctx.price_at[product_id]
    price = hist[0][1]
    for vf, pr in hist:
        if vf <= on:
            price = pr
        else:
            break
    return price

def gen_promotions(ctx: Ctx):
    """~8% of active products get a promotion window. For the case 3 anchor supplier the windows are
    built on purpose around 'now' and 'the first of next month' so the phrase 'already on promotion'
    has more than one defensible reading (documented in docs/demo-scenarios.md)."""
    rng = ctx.rng
    promo_names = ["Autumn Trail Sale", "Back to the Mountains", "Season Opener", "Winter Warm-up",
                   "Spring Clearance", "Midsummer Deal", "Ruska Weeks", "Kaamos Special", "Pre-season Deal"]
    pid = 0
    today = ctx.as_of
    nm = first_of_next_month(today)

    def add(p, starts, ends, name, pct):
        nonlocal pid
        pid += 1
        base = current_price(ctx, p["id"], max(starts, D.fromisoformat(p["created_at"])))
        promo_price = _pretty_price(round(base * (1 - pct), 2))
        row = {"id": pid, "product_id": p["id"], "name": name, "discount_pct": f"{pct * 100:.1f}",
               "promo_price": money(promo_price), "starts_on": iso(starts), "ends_on": iso(ends),
               "created_by": rng.choice(ctx.users_by_role["CATALOGUE_MANAGER"])}
        ctx.tables["promotions"].append(row)
        ctx.promos_by_product[p["id"]].append((starts, ends, promo_price))

    anchor = [p for p in ctx.products if p["_sup"] == "FJV"]
    rng.shuffle(anchor)
    # 18 running now and past the 1st of next month; 4 running now but ending before it;
    # 3 starting after today but before the 1st; 5 ended last month (not "on promotion" in any reading)
    # windows are clamped so the four readings hold for any "today": group 2 ends between today and the day
    # before the 1st; group 3 starts after today and no later than the 1st (on the last day of a month that is the 1st)
    groups = [(18, lambda: (today - dt.timedelta(days=rng.randint(5, 25)), nm + dt.timedelta(days=rng.randint(10, 40)))),
              (4, lambda: (today - dt.timedelta(days=rng.randint(10, 30)), max(today, nm - dt.timedelta(days=rng.randint(2, 12))))),
              (3, lambda: (min(nm, today + dt.timedelta(days=rng.randint(3, 12))), nm + dt.timedelta(days=rng.randint(14, 45)))),
              (5, lambda: (today - dt.timedelta(days=rng.randint(60, 90)), today - dt.timedelta(days=rng.randint(8, 30))))]
    idx = 0
    anchor_counts = {}
    for n, win in groups:
        for _ in range(n):
            p = anchor[idx]; idx += 1
            s, e = win()
            add(p, s, e, rng.choice(promo_names), rng.choice([0.10, 0.15, 0.20, 0.25]))
    anchor_counts["active_today_and_on_first_of_next_month"] = 18
    anchor_counts["active_today_but_ends_before_first_of_next_month"] = 4
    anchor_counts["starts_after_today_before_first_of_next_month"] = 3
    anchor_counts["ended_before_today"] = 5
    ctx.anchors["case3_promotions"] = anchor_counts

    # everyone else: random windows across the history, ~8% of active products (excluding FJV)
    others = [p for p in ctx.products if p["_sup"] != "FJV" and p["active"] == "true"]
    for p in others:
        if rng.random() < 0.08:
            start = ctx.history_start + dt.timedelta(days=rng.randint(0, (today - ctx.history_start).days + 45))
            add(p, start, start + dt.timedelta(days=rng.randint(14, 56)), rng.choice(promo_names),
                rng.choice([0.10, 0.15, 0.20, 0.25, 0.30]))

def promo_price_on(ctx: Ctx, product_id: int, on: D):
    for s, e, pp in ctx.promos_by_product.get(product_id, []):
        if s <= on <= e:
            return pp
    return None

def ean13(pid: int) -> str:
    """Deterministic EAN-13: GS1 prefix 640 (Finland), a fixed company part, the product id, check digit."""
    body = f"6402026{pid:05d}"
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body))
    return body + str((10 - total % 10) % 10)

_DESCRIPTIONS = [
    "{brand} {model} {tname} for {cat_l}. {variant_s}Built for Nordic conditions, season after season.",
    "Reliable {tname_l} from {brand}'s {model} range. {variant_s}A wholesale staple for outdoor retailers.",
    "{brand} {model}: a {tname_l} that balances weight, durability and price. {variant_s}Retail-ready packaging.",
    "The {model} {tname_l} by {brand}. {variant_s}Popular with rental outfitters and clubs.",
]

def product_description(pid, brand, model, tname, cat_name, variant, colour) -> str:
    """Deterministic marketing text (no RNG, so adding it did not change the rest of the data)."""
    parts = []
    if variant:
        parts.append(variant)
    if colour:
        parts.append(colour)
    variant_s = (" / ".join(parts) + ". ") if parts else ""
    t = _DESCRIPTIONS[pid % len(_DESCRIPTIONS)]
    return t.format(brand=brand, model=model.strip(), tname=tname, tname_l=tname.lower(), cat_l=cat_name.lower(), variant_s=variant_s)


def gen_inventory(ctx: Ctx):
    """Stock per product per warehouse, generated AFTER orders so it agrees with them:
    a product with lines currently on backorder has no free stock (on_hand <= reserved) in the
    shipping warehouse and a next_inbound_date; 'short stock' products run low everywhere."""
    rng = ctx.rng
    short = ctx.anchors.get("_short_ids", set())
    orders_by_id = {o["id"]: o for o in ctx.tables["orders"]}
    backordered = {}   # (product_id, warehouse_id) -> earliest expected restock
    for l in ctx.tables["order_lines"]:
        if l["status"] == "BACKORDERED":
            wh = orders_by_id[l["order_id"]]["warehouse_id"]
            restock = l.get("_restock") or (ctx.as_of + dt.timedelta(days=14))
            key = (l["product_id"], wh)
            backordered[key] = min(backordered.get(key, restock), restock)
    iid = 0
    for p in ctx.products:
        for wid, code, *_ in WAREHOUSES:
            key = (p["id"], wid)
            if wid == 3 and key not in backordered and rng.random() < 0.6:
                continue  # the Oslo cross-dock holds a thin range
            iid += 1
            reorder = rng.choice([10, 20, 30, 50])
            inbound = None
            if p["active"] == "false":
                on_hand, reserved, reorder = 0, 0, 0
            elif key in backordered:
                reserved = int(rng.expovariate(1 / 8)) + 1
                on_hand = rng.randint(0, reserved)          # free stock <= 0
                inbound = max(backordered[key], ctx.as_of + dt.timedelta(days=rng.randint(1, 5)))
            elif p["id"] in short:
                on_hand = rng.randint(0, reorder)
                reserved = rng.randint(0, on_hand) if on_hand else 0
                inbound = ctx.as_of + dt.timedelta(days=rng.randint(3, 30))
            else:
                on_hand = int(rng.expovariate(1 / 60)) + 5
                reserved = min(on_hand, int(rng.expovariate(1 / 8)))
                if on_hand < reorder:
                    inbound = ctx.as_of + dt.timedelta(days=rng.randint(3, 45))
            ctx.tables["inventory"].append({
                "id": iid, "product_id": p["id"], "warehouse_id": wid, "on_hand": on_hand,
                "reserved": reserved, "reorder_point": reorder, "next_inbound_date": iso(inbound),
            })
