"""Real-world name collision check.

Everything in a pack is fictional, but a fictional name can still be a real company's: a real brand used as
a stem ("Haltigear" from Halti), a real retailer reused as a chain, a real carrier shown with invented late
rates, or a generic shop word next to a real town ("Fjällbutiken Östersund") that reads as a local shop.
This module checks the company-like names of a pack offline in two ways and lists them for a human:

1. a denylist of real Nordic / outdoor brands, retailers and carriers (below), extended per pack by
   `[names] deny = [...]` in any `pools/*.toml`, matched at word start (so "Haltigear" matches "halti");
   `[names] allow = [...]` exempts values on purpose (the demo company itself, a deliberate homage);
2. a heuristic: a business name whose non-town tokens are all generic shop words (butiken, sport, store,
   kauppa, ...) next to a town from the pack's own city pools.

Which values are "company-like": pool lists whose key mentions word/name/brand/model/suffix/chain/carrier/
supplier/company (never first_names, last_names, cities, streets, country_names), the chains and carriers of
config.toml, and the columns `name` (of entities without person columns), `chain_name`, `carrier`, `brand`
of the generated tables (`name` only for organisations: entities with a country, VAT number or city and
no person columns, so product names are not scanned). The web check for names not on the list is the assistant's job (AGENTS.md).
"""
from __future__ import annotations

import csv
import glob
import os
import re
import tomllib
import unicodedata

# Brands, retailers and carriers a Nordic outdoor-equipment demo is most likely to collide with.
# Lower-case; single words match at the start of a word, phrases match anywhere.
DENY = [
    # outdoor / sports brands
    "halti", "fjällräven", "fjallraven", "haglöfs", "haglofs", "peak performance", "norrøna", "norrona", "bergans",
    "helly hansen", "swix", "didriksons", "houdini", "klättermusen", "klattermusen", "lundhags", "hilleberg", "primus",
    "trangia", "silva", "suunto", "rukka", "sasta", "icepeak", "luhta", "reima", "tunturi", "devold", "dale of norway",
    "ulvang", "aclima", "kari traa", "sail racing", "8848 altitude", "tenson", "craft", "salomon", "arc'teryx",
    "arcteryx", "patagonia", "the north face", "north face", "mammut", "salewa", "dynafit", "ortovox", "vaude",
    "deuter", "jack wolfskin", "osprey", "gregory", "black diamond", "petzl", "garmin", "kompass", "boreal", "scarpa",
    "la sportiva", "lowa", "meindl", "hanwag", "hoka", "merrell", "keen", "columbia", "marmot", "rab", "montane",
    "exped", "therm-a-rest", "thermarest", "sea to summit", "msr", "jetboil", "nordisk", "tentipi", "savotta",
    "lumi accessories", "makia", "billebeino",
    # retailers
    "retkiaitta", "partioaitta", "scandinavian outdoor", "intersport", "stadium", "xxl", "naturkompaniet", "addnature",
    "outnorth", "sportamore", "fjellsport", "milrab", "eventyrsport", "friluftsland", "spejder sport", "sportmaster",
    "decathlon", "globetrotter", "bergfreunde", "bergzeit", "granit", "trailhead", "sport 1", "g-sport", "gsport",
    "team sportia", "budget sport", "stockmann", "sportsdirect", "sports direct", "xxl sport", "outdoorexperten",
    "varuste", "scandinavian outdoor store", "kesko", "prisma", "tokmanni", "biltema", "jula", "clas ohlson",
    # carriers / logistics
    "postnord", "posti", "bring", "db schenker", "schenker", "dhl", "dsv", "ups", "fedex", "gls", "matkahuolto",
    "kaukokiito", "omniva", "itella", "fjord line", "hurtigruten", "maersk", "kuehne", "kühne", "geodis", "dachser",
    # other well-known Nordic companies whose names invite reuse
    "norrsken", "skandia", "nordea", "telia", "elisa", "fortum", "vattenfall", "equinor", "statkraft", "kesko",
]

# tokens that make a business name generic when they are all that is left after removing a town
GENERIC_TOKENS = {"sport", "sports", "outdoor", "outdoors", "store", "shop", "butik", "butiken", "butikken", "kauppa",
                  "magasinet", "magasin", "urheilu", "fritid", "friluft", "friluftsliv", "gear", "equipment", "outfitters",
                  "trekking", "camping", "adventure", "the", "&", "and", "af", "og", "och", "ja", "og", "center", "centre"}
GENERIC_SUFFIXES = ("butiken", "butikken", "butik", "kauppa", "shop", "store", "magasinet", "sport", "sports", "center", "centre")
POOL_KEY_HINTS = ("word", "name", "brand", "model", "suffix", "chain", "carrier", "supplier", "company")
POOL_KEY_SKIP = ("first_name", "last_name", "country_name", "cities", "streets", "hubs", "contact_role", "segment", "legal_form",
                 "channel", "categor", "status", "role", "type", "kind", "reason", "season", "names.deny", "names.allow")


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold())
    return "".join(c for c in s if not unicodedata.combining(c))


def _lists(domain):
    """Yield (source, [values]) for every company-like string list in the pack's pools and config."""
    for path in sorted(glob.glob(os.path.join(domain.path, "pools", "*.toml"))):
        data = tomllib.load(open(path, "rb"))
        base = os.path.basename(path)

        def walk(node, key):
            if isinstance(node, dict):
                for k, v in node.items():
                    yield from walk(v, f"{key}.{k}" if key else k)
            elif isinstance(node, list) and node and all(isinstance(x, str) for x in node):
                low = key.lower()
                if any(h in low for h in POOL_KEY_HINTS) and not any(s in low for s in POOL_KEY_SKIP):
                    yield f"pools/{base} [{key}]", node
            elif isinstance(node, list) and node and all(isinstance(x, dict) for x in node):
                names = [x["name"] for x in node if isinstance(x.get("name"), str)]
                if names and any(h in key.lower() for h in POOL_KEY_HINTS + ("supplier", "anchor")):
                    yield f"pools/{base} [[{key}]].name", names
                for x in node:
                    yield from walk(x, key)
        yield from walk(data, "")
    cfg_path = os.path.join(domain.path, "config.toml")
    if os.path.exists(cfg_path):
        cfg = tomllib.load(open(cfg_path, "rb"))
        if cfg.get("chains"):
            yield "config.toml [[chains]].name", [c["name"] for c in cfg["chains"] if c.get("name")]
        if cfg.get("carriers", {}).get("names"):
            yield "config.toml [carriers].names", list(cfg["carriers"]["names"])


def _cities(domain) -> set:
    towns = set()
    for path in glob.glob(os.path.join(domain.path, "pools", "*.toml")):
        data = tomllib.load(open(path, "rb"))
        for key in ("cities", "towns"):
            for lst in (data.get(key) or {}).values() if isinstance(data.get(key), dict) else []:
                for item in lst:
                    towns.add(_fold(item[0] if isinstance(item, list) else str(item)))
    return towns


def _table_values(domain, out):
    """Distinct values of company-like columns in the generated CSVs: (source, values, total_distinct)."""
    spec = domain.spec
    for e in spec.entities:
        cols = {c.name for c in e.columns}
        person = {"first_name", "last_name", "full_name"} & cols
        organisation = bool({"country", "vat_number", "legal_form", "city", "lead_time_days"} & cols) and not person
        wanted = [c for c in ("name", "chain_name", "carrier", "brand") if c in cols and (c != "name" or organisation)]
        if not wanted:
            continue
        path = os.path.join(out, "csv", f"{e.name}.csv")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        for c in wanted:
            vals = sorted({r[c] for r in rows if r.get(c)})
            yield f"{e.name}.{c}", vals


def rules(domain):
    deny, allow = list(DENY), set()
    for path in glob.glob(os.path.join(domain.path, "pools", "*.toml")):
        data = tomllib.load(open(path, "rb"))
        deny += [str(x) for x in data.get("names", {}).get("deny", [])]
        allow |= {_fold(str(x)) for x in data.get("names", {}).get("allow", [])}
    allow.add(_fold(domain.spec.company))
    patterns = []
    for d in sorted(set(_fold(x) for x in deny)):
        if " " in d:                       # phrase: anywhere
            rx = re.escape(d)
        elif len(d) <= 5:                  # short stem: whole word only ("rab", "keen", "xxl")
            rx = r"(?<![a-z0-9])" + re.escape(d) + r"(?![a-z0-9])"
        else:                              # longer stem: word start ("halti" catches "haltigear")
            rx = r"(?<![a-z0-9])" + re.escape(d)
        patterns.append((d, re.compile(rx)))
    return patterns, allow


def scan(domain, out=None):
    """Returns (denied, generic): lists of (value, reason, where)."""
    patterns, allow = rules(domain)
    towns = _cities(domain)
    denied, generic, seen = [], [], set()
    sources = list(_lists(domain))
    if out:
        sources += list(_table_values(domain, out))
    for where, values in sources:
        for v in values:
            fv = _fold(v)
            if fv in allow or (fv, where.split(" ")[0]) in seen:
                continue
            seen.add((fv, where.split(" ")[0]))
            for stem, rx in patterns:
                if rx.search(fv) and stem not in allow:
                    denied.append((v, f"matches '{stem}'", where))
                    break
            tokens = [t for t in re.split(r"[\s\-/]+", fv) if t]
            rest = [t for t in tokens if t not in towns]
            if rest and len(rest) < len(tokens) and all(t in GENERIC_TOKENS or t.endswith(GENERIC_SUFFIXES) for t in rest):
                generic.append((v, "generic shop words next to a real town", where))
    return denied, generic


def inventory(domain, out=None, limit=120):
    """Company-like names by source, for the review page: {source: (values or None, count)}."""
    inv = {}
    for where, values in list(_lists(domain)) + (list(_table_values(domain, out)) if out else []):
        vals = sorted(set(values))
        inv[where] = (vals if len(vals) <= limit else None, len(vals))
    return inv
