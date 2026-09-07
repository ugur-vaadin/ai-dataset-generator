"""Shared helpers, date utilities, the generic generation context and the config loader."""
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


from . import VERSION  # framework version

D = dt.date

TS = dt.datetime

def iso(d):
    if d is None:
        return ""
    if isinstance(d, TS):
        return d.strftime("%Y-%m-%d %H:%M:%S")
    return d.isoformat()

def money(x):
    return f"{x:.2f}"

def add_business_days(d: D, n: int) -> D:
    step = 1 if n >= 0 else -1
    n = abs(n)
    while n > 0:
        d += dt.timedelta(days=step)
        if d.weekday() < 5:
            n -= 1
    return d

def first_of_next_month(d: D) -> D:
    return (d.replace(day=1) + dt.timedelta(days=32)).replace(day=1)

def first_of_month(d: D) -> D:
    return d.replace(day=1)

def months_back(d: D, n: int) -> D:
    y, m = d.year, d.month - n
    while m <= 0:
        m += 12
        y -= 1
    return D(y, m, 1)

def to_weekday(d: D) -> D:
    """Next Monday..Friday on or after d."""
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d

def ts_on(rng, d: D, h0=7, h1=17) -> TS:
    """A timestamp on day d with a random time between h0 and h1."""
    return TS.combine(d, dt.time(rng.randint(h0, h1), rng.randint(0, 59), rng.randint(0, 59)))

def last_weekday_before(d: D, weekday: int) -> D:
    """Most recent date strictly before d with the given weekday (0 = Monday)."""
    d = d - dt.timedelta(days=1)
    while d.weekday() != weekday:
        d -= dt.timedelta(days=1)
    return d

def next_weekday_after(d: D, weekday: int) -> D:
    d = d + dt.timedelta(days=1)
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    return d

def status_by_age(rng, age_days: int, bands):
    """Pick a status from age bands: [(max_age_days or None, [statuses], [weights]), ...]; the first band whose
    max_age is None or >= age_days is used. Keeps 'recent = open, old = closed' consistent across domains."""
    for max_age, statuses, weights in bands:
        if max_age is None or age_days <= max_age:
            return rng.choices(statuses, weights=weights, k=1)[0]
    return bands[-1][1][-1]

def clamp_to_day(ts: TS, last_day: D, hour: int = 17) -> TS:
    """Pull a timestamp back onto last_day if it fell after it (nothing happens after as-of)."""
    return ts if ts.date() <= last_day else TS.combine(last_day, dt.time(hour, 0))

def slug(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch in "äå": ch = "a"
        elif ch == "ö": ch = "o"
        elif ch == "ø": ch = "o"
        elif ch == "æ": ch = "ae"
        elif ch == "ü": ch = "u"
        elif ch == "é": ch = "e"
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_." and (not out or out[-1] != "."):
            out.append(".")
    return "".join(out).strip(".")

def weighted_choice(rng: random.Random, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]

def zipf_weights(n: int, s: float = 0.9):
    return [1.0 / ((i + 1) ** s) for i in range(n)]

@dataclass
class BaseCtx:
    """What every domain's context has. Domains subclass it with their own indexes."""
    rng: random.Random
    as_of: D
    scale: float
    months: int
    tables: dict = field(default_factory=lambda: defaultdict(list))
    anchors: dict = field(default_factory=dict)

    @property
    def history_start(self) -> D:
        return months_back(self.as_of, self.months)


# ---------------------------------------------------------------------------
# Configuration (config/default.toml, optionally overlaid by --config)
# ---------------------------------------------------------------------------

import tomllib as _tomllib

CFG: dict = {}
DEFAULT_CONFIG = None  # set by load_config(default_path, overlay)

def _merge(base: dict, over: dict) -> dict:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base

def load_config(default_path: str, overlay: str | None = None) -> dict:
    """Load the domain's config.toml and overlay the given file. Fills the module-level CFG."""
    with open(default_path, "rb") as f:
        cfg = _tomllib.load(f)
    if overlay:
        with open(overlay, "rb") as f:
            _merge(cfg, _tomllib.load(f))
    CFG.clear()
    CFG.update(cfg)
    return CFG

def cfg(*keys):
    """cfg('late', 'base_late_dispatch_prob') -> value, loading the defaults on first use."""
    if not CFG:
        raise RuntimeError("configuration not loaded; call load_config(<domain>/config.toml) first")
    node = CFG
    for k in keys:
        node = node[k]
    return node
