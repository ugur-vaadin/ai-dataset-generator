"""Loads the human-editable pools (pools/*.toml) and exposes them under the names the generators
use. Structural dataclasses for categories and suppliers live here; their data lives in TOML."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from typing import Optional

_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pools")

def _load(name):
    with open(os.path.join(_DIR, name), "rb") as f:
        return tomllib.load(f)

_N = _load("names.toml")
_C = _load("catalogue.toml")
_L = _load("claims.toml")

# --- names.toml
FIRST_NAMES = _N["first_names"]
LAST_NAMES = _N["last_names"]
CITIES = {k: [tuple(x) for x in v] for k, v in _N["cities"].items()}
STREETS = _N["streets"]
COUNTRY_NAMES = _N["country_names"]
LEGAL_FORM = _N["legal_form"]
TRANSIT_DAYS = {k: tuple(v) for k, v in _N["transit_days"].items()}
HUBS = _N["hubs"]
INDEPENDENT_WORDS = _N["customers"]["independent_words"]
INDEPENDENT_SUFFIX = _N["customers"]["independent_suffix"]
SEGMENTS = _N["customers"]["segments"]
SEGMENT_WEIGHTS = _N["customers"]["segment_weights"]
CONTACT_ROLES = _N["customers"]["contact_roles"]
ANCHOR_STORES = [(a["chain"], a["country"], a["city"]) for a in _N["anchor_store"]]

# --- catalogue.toml
@dataclass
class CategoryDef:
    code: str
    name: str
    season: str            # SPRING, SUMMER, AUTUMN, WINTER, ALL
    price_range: tuple     # EUR list price range
    weight_range: tuple    # kg per unit
    types: list            # (type name, variant kind, per-type price multiplier)
    demand: float          # relative demand weight

@dataclass
class SupplierDef:
    code: str
    name: str
    country: str
    categories: list      # category codes
    product_count: Optional[int] = None   # fixed count (case 3 anchor) or None = weighted
    lead_time_days: int = 14
    is_case3_anchor: bool = False

CATEGORIES = [CategoryDef(c["code"], c["name"], c["season"], tuple(c["price_range"]), tuple(c["weight_range"]),
                          [(t["name"], t["kind"], t["mult"]) for t in c["types"]], c["demand"]) for c in _C["category"]]
CAT_BY_CODE = {c.code: c for c in CATEGORIES}
SUPPLIERS = [SupplierDef(s["code"], s["name"], s["country"], s["categories"], s.get("product_count"),
                         s.get("lead_time_days", 14), s.get("is_case3_anchor", False)) for s in _C["supplier"]]
MODEL_NAMES = _C["naming"]["model_names"]
LINES = _C["naming"]["lines"]
COLORS = _C["naming"]["colors"]
UNITS = _C["units"]
VARIANT_POOL = dict(_C["variants"])
VARIANT_POOL["NONE"] = [""]
SEASON_FACTOR = {k: {int(m): f for m, f in v.items()} for k, v in _C["season_factor"].items()}
CHANNELS = _C["channels"]["names"]
DELAY_REASONS = _C["delays"]["reasons"]
WAREHOUSES = [(w["id"], w["code"], w["name"], w["country"], w["city"], w["postal_code"]) for w in _C["warehouse"]]
USERS = [(u["username"], u["full_name"], u["role"]) for u in _C["user"]]

# --- claims.toml
CLAIM_TYPES = _L["claims"]["types"]
CLAIM_TYPE_WEIGHTS = _L["claims"]["type_weights"]
DEFECTS = _L["claims"]["defects"]
RESOLUTION_FOR = _L["claims"]["resolution_for"]
