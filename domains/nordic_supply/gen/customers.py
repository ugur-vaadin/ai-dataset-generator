"""Customers, their contacts and delivery addresses."""
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

from dsgen.model import D, cfg, iso, money, slug, weighted_choice
from .ctx import Ctx
from .pools import ANCHOR_STORES, CITIES, CONTACT_ROLES, FIRST_NAMES, INDEPENDENT_SUFFIX, INDEPENDENT_WORDS, LAST_NAMES, LEGAL_FORM, SEGMENTS, SEGMENT_WEIGHTS, STREETS

def _vat(rng, country):
    n = lambda k: "".join(str(rng.randint(0, 9)) for _ in range(k))
    return {"FI": "FI" + n(8), "SE": "SE" + n(10) + "01", "NO": "NO" + n(9) + "MVA",
            "DK": "DK" + n(8), "DE": "DE" + n(9), "EE": "EE" + n(9)}[country]

def _phone(rng, country):
    n = lambda k: "".join(str(rng.randint(0, 9)) for _ in range(k))
    return {"FI": f"+358 40 {n(3)} {n(4)}", "SE": f"+46 70 {n(3)} {n(2)} {n(2)}",
            "NO": f"+47 9{n(2)} {n(2)} {n(3)}", "DK": f"+45 {n(2)} {n(2)} {n(2)} {n(2)}",
            "DE": f"+49 40 {n(7)}", "EE": f"+372 5{n(3)} {n(4)}"}[country]

def _person(rng, country):
    c = country if country in FIRST_NAMES else "SE"
    return rng.choice(FIRST_NAMES[c]), rng.choice(LAST_NAMES[c])

def gen_customers(ctx: Ctx):
    rng = ctx.rng
    ams = ctx.users_by_role["ACCOUNT_MANAGER"]
    used = set()
    target = int(cfg("volume", "customers") * ctx.scale)

    def add_customer(name, chain, segment, country, city, postal, is_anchor=False):
        cid = len(ctx.customers) + 1
        street = f"{rng.choice(STREETS[country])} {rng.randint(1, 120)}"
        domain = f"{slug(chain) if chain else slug(name.split(' ' + LEGAL_FORM[country])[0])}.example"
        created = D(2015, 1, 1) + dt.timedelta(days=rng.randint(0, (ctx.as_of - D(2015, 1, 1)).days - 40))
        if rng.random() < 0.06:  # a few brand-new accounts
            created = ctx.as_of - dt.timedelta(days=rng.randint(5, 120))
        row = {
            "id": cid, "customer_number": f"C-{10000 + cid}", "name": name, "chain_name": chain or "",
            "segment": segment, "country": country, "city": city, "postal_code": postal, "street": street,
            "vat_number": _vat(rng, country), "email_domain": domain, "phone": _phone(rng, country),
            "credit_limit": money(rng.choice([5000, 10000, 15000, 25000, 40000, 60000, 100000])),
            "payment_terms_days": rng.choice([14, 30, 30, 30, 45, 60]),
            "customer_discount_pct": f"{rng.choice([0, 0, 0, 2, 3, 5, 5, 7.5, 10, 12]):.1f}",
            "account_manager_id": rng.choice(ams), "created_at": iso(created),
            "active": "false" if (not is_anchor and rng.random() < 0.05) else "true",
            "_weight": {"CHAIN_STORE": 1.6, "ONLINE": 2.4, "INDEPENDENT": 1.0, "DEPARTMENT_STORE": 1.4,
                        "RENTAL_OUTFITTER": 0.9, "CLUB_OR_SCHOOL": 0.4}[segment] * rng.paretovariate(2.0),
        }
        if row["active"] == "false":
            row["_weight"] *= 0.05
        ctx.tables["customers"].append(row)
        ctx.customers.append(row)
        used.add(name)
        # contacts
        n_contacts = rng.choice([1, 1, 2, 2, 3])
        for k in range(n_contacts):
            fn, ln = _person(rng, country)
            cont_id = len(ctx.tables["customer_contacts"]) + 1
            ctx.tables["customer_contacts"].append({
                "id": cont_id, "customer_id": cid, "first_name": fn, "last_name": ln,
                "role": CONTACT_ROLES[0] if k == 0 else rng.choice(CONTACT_ROLES[1:]),
                "email": f"{slug(fn)}.{slug(ln)}@{domain}", "phone": _phone(rng, country),
                "is_primary": "true" if k == 0 else "false", "language": {"FI": "fi", "SE": "sv", "NO": "nb",
                                                                           "DK": "da", "DE": "de", "EE": "et"}[country],
                "marketing_consent": "true" if rng.random() < cfg("pii", "marketing_consent_share") else "false",
                "consent_source": rng.choice(["WEBSITE", "TRADE_FAIR", "ACCOUNT_MANAGER", "PORTAL"]),
                "retention_until": iso(max(created, ctx.as_of) + dt.timedelta(days=365 * rng.choice([2, 3, 5]))),
            })
            ctx.contacts_by_customer[cid].append(ctx.tables["customer_contacts"][-1])
        # delivery addresses
        labels = ["Store"] + (["Central warehouse"] if segment in ("CHAIN_STORE", "ONLINE") and rng.random() < 0.3 else []) \
                 + (["Second store"] if rng.random() < 0.15 else [])
        for k, label in enumerate(labels):
            aid = len(ctx.tables["delivery_addresses"]) + 1
            acity, apostal = (city, postal) if k == 0 else rng.choice(CITIES[country])
            ctx.tables["delivery_addresses"].append({
                "id": aid, "customer_id": cid, "label": label,
                "street": street if k == 0 else f"{rng.choice(STREETS[country])} {rng.randint(1, 120)}",
                "postal_code": apostal, "city": acity, "country": country,
                "delivery_instructions": rng.choice(["", "", "Loading bay at the back, open 7-15",
                                                     "Call 30 min before arrival", "No deliveries before 9:00",
                                                     "Pallets only via goods entrance", "Leave with neighbour shop if closed"]),
                "is_default": "true" if k == 0 else "false",
            })
            ctx.addresses_by_customer[cid].append(ctx.tables["delivery_addresses"][-1])
        return row

    # anchor stores first (stable ids 1..6)
    for chain, country, city in ANCHOR_STORES:
        postal = dict(CITIES[country])[city]
        add_customer(f"{chain} {city}", chain, "CHAIN_STORE", country, city, postal, is_anchor=True)
    # chains
    for ch in cfg("chains"):
        chain, countries, stores, segment = ch["name"], ch["countries"], ch["stores"], "CHAIN_STORE"
        for _ in range(int(stores * ctx.scale)):
            country = rng.choice(countries)
            city, postal = rng.choice(CITIES[country])
            name = f"{chain} {city}"
            if name in used:
                for st in rng.sample(STREETS[country], len(STREETS[country])):
                    if f"{chain} {city} {st.split()[0]}" not in used:
                        name = f"{chain} {city} {st.split()[0]}"
                        break
                else:
                    continue
            add_customer(name, chain, segment, country, city, postal)
    # independents and others
    while len(ctx.customers) < target:
        cw = cfg("country_weights")
        country = weighted_choice(rng, list(cw), list(cw.values()))
        city, postal = rng.choice(CITIES[country])
        segment = weighted_choice(rng, SEGMENTS, SEGMENT_WEIGHTS)
        style = rng.random()
        if style < 0.45:
            base = f"{rng.choice(INDEPENDENT_WORDS)} {rng.choice(INDEPENDENT_SUFFIX)}"
        elif style < 0.75:
            base = f"{city} {rng.choice(INDEPENDENT_SUFFIX)}"
        else:
            fn, ln = _person(rng, country)
            base = f"{ln} {rng.choice(['Sport', 'Outdoor', 'Friluft', 'Urheilu'])}"
        if segment == "ONLINE":
            base = f"{rng.choice(INDEPENDENT_WORDS)}{rng.choice(['shop', 'store', 'gear', '24'])}"
        elif segment == "RENTAL_OUTFITTER":
            base = f"{city} {rng.choice(['Adventures', 'Expeditions', 'Guides', 'Rental'])}"
        elif segment == "CLUB_OR_SCHOOL":
            base = f"{city} {rng.choice(['Alpine Club', 'Outdoor School', 'Hiking Association', 'Scouts'])}"
        name = f"{base} {LEGAL_FORM[country]}" if segment != "CLUB_OR_SCHOOL" else base
        if name in used:
            continue
        add_customer(name, None, segment, country, city, postal)
