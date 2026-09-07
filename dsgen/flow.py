"""Declarative flow engine: generates a domain's tables from flow.toml instead of Python.

flow.toml describes, per entity, how many rows exist (absolute, per parent, or per day over the
history window), how each field is produced (a small expression language, below), and the demo
anchors (records picked or computed from the data). Everything the two hand-written lifecycles had to
get right by hand — dates inside the as-of window and after their parents, statuses derived from age,
business keys, formatting by column type — the engine does once.

Field expressions (strings). A value without a "kind:" prefix is a constant.
  const:V                         constant (also any bare value)
  null                            NULL
  copy:REF                        copy a value (REF: field, parent.field, field->table.col, cfg.a.b, as_of, history_start)
  seq                             1-based row number in this entity
  key:PATTERN                     business key, e.g. key:POL-{start_date|year}-{seq:06}; {seq} counts per distinct rest of the key
  template:TEXT                   TEXT with {REF} and {REF|lower|slug|upper|year|date} placeholders
  pool:PATH  pool:PATH[REF]       random element of a pools list, or of the list under key REF in a pools table
  weighted:PATH  weighted:A=60|B=40   weighted choice from a pools table {value: weight} (or values/weights lists) or inline
  choice:A|B|C                    uniform choice of literals
  lookup:PATH[REF]                value of a pools table under key REF
  int:A..B  float:A..B  money:A..B    uniform numbers (money → 2 decimals); money:PATH[REF] takes [lo, hi] from a pools table
  bool:P                          true with probability P
  date:BASE ± A..B UNIT [| weekday] [| clamp]      BASE: as_of, history_start, field, parent.field, or a function call
  ts:BASE ± A..B UNIT [@ H0..H1] [| weekday] [| clamp]   UNIT: minutes, hours, days, business_days; @ picks a time of day
      functions: last_weekday_before(REF, Tuesday), next_weekday_after(REF, Friday), add_business_days(REF, N), first_of_month(REF)
  status_by_age:REF using bands.NAME   status from [[bands.NAME]] rows {max_age, statuses={A=w,...}} by age in days of REF
  calc:EXPR                       arithmetic over {REF} placeholders (+ - * / parentheses, round, min, max, abs)
  if:COND then EXPR else EXPR     COND: REF op VALUE (== != < <= > >= in), REF in A..B, and/or; UPPERCASE bare words are literals;
                                  nested: if:A then X else if:B then Y else Z
  pick:TABLE [where COND] [weighted by FIELD]   id of a random row of a generated table (COND sees the candidate's fields; a
                                  field of the current row is written as row.FIELD)
  pareto:ALPHA [max M]  expo:MEAN [max M]  normal:MEAN sd SD [min A] [max B]   shaped distributions
  seq_in_parent  sibling_count    position among the siblings created for the same parent; prev.FIELD refers to the previous sibling
  sum:CHILD.COL  count:CHILD  max:CHILD.COL  min:CHILD.COL  avg:CHILD.COL   aggregates over child rows (in [entity.X.after] only;
                                  the child's reference column to X is found from domain.toml, or given as "sum:CHILD.COL via FK")
  dates.NAME                      a named date from [dates] (evaluated once); usable as a base, in conditions and ranges
Entity generation:
  per = { day = "history", ..., seasonality = "POOLS.TABLE" }   month → multiplier table ("1".."12") applied to the daily count
  [entity.X.after] COL = "sum:…"   fields computed once all entities exist (aggregates, derived values)
Anchors:
  [[anchor]] ensure = { entity, where, always = false, fields = {…}, children = [{ entity, count, fields }] }
                                  pick a row matching where, or create one (and its children) through the field expressions
Entity generation:
  [entity.NAME] count = "cfg:volume.x [*|/ N]" | "A..B" | N        absolute rows (scaled by --scale unless scale = false)
  [entity.NAME] per = { parent = "T", count = "...", share = P, when = "COND" }   rows per parent row
  [entity.NAME] per = { day = "history", count = "..." , pick = "T", pick_where = "COND" }   rows per day; each picks a parent
  [entity.NAME] rows_from = { pool = "PATH", columns = ["a", "b"] }    literal rows from a pools list of lists
  [[entity.NAME.burst]] from/to (date expr), factor, prob, when, set = { field = value }     extra rows in a window
  [[entity.NAME.variants]] when = "COND", fields = { ... }            per parent: one row per matching variant
Anchors:
  [[anchor]] group, key, pre = {...}, pick = { entity, where, none_of = { entity, link, where } }, fields = {...}
"""
from __future__ import annotations

import ast
import datetime as dt
import os
import re
import tomllib
from dataclasses import dataclass, field

from .model import (BaseCtx, D, TS, add_business_days, first_of_month, first_of_next_month, iso, last_weekday_before,
                    next_weekday_after, slug, status_by_age, to_weekday, ts_on)

WEEKDAYS = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6}


class FlowError(Exception):
    pass


@dataclass
class FlowCtx(BaseCtx):
    """Generic context: tables, anchors, plus id indexes, sequence counters, named dates and pick caches."""
    index: dict = field(default_factory=dict)      # table -> {id: row}
    seqs: dict = field(default_factory=dict)
    dates: dict = field(default_factory=dict)
    pick_cache: dict = field(default_factory=dict)


def load_flow(domain_path: str):
    with open(os.path.join(domain_path, "flow.toml"), "rb") as f:
        flow = tomllib.load(f)
    pools = {}
    pdir = os.path.join(domain_path, "pools")
    if os.path.isdir(pdir):
        for fn in sorted(os.listdir(pdir)):
            if fn.endswith(".toml"):
                with open(os.path.join(pdir, fn), "rb") as f:
                    pools.update(tomllib.load(f))
    pools.update(flow.get("pools", {}))
    return flow, pools


# ---------------------------------------------------------------------------
# Evaluation environment
# ---------------------------------------------------------------------------

class Env:
    def __init__(self, ctx: FlowCtx, spec, pools, cfg, row=None, parent=None, extra=None):
        self.ctx, self.spec, self.pools, self.cfg = ctx, spec, pools, cfg
        self.row, self.parent, self.extra = row if row is not None else {}, parent, extra or {}
        self.rng = ctx.rng
        self.fields, self.entity, self._evaluating = {}, "", set()

    def path(self, dotted, obj):
        for part in dotted.split("."):
            if isinstance(obj, dict) and part in obj:
                obj = obj[part]
            else:
                raise FlowError(f"unknown path '{dotted}'")
        return obj

    def resolve(self, ref: str):
        ref = ref.strip()
        if "->" in ref:                                  # field->table.col->table2.col2 : follow reference columns, any depth
            first, *hops = ref.split("->")
            value = self.resolve(first)
            for hop in hops:
                if value is None:
                    return None
                table, col = hop.split(".", 1)
                row = self.ctx.index.get(table, {}).get(value)
                if row is None:
                    raise FlowError(f"no row {value!r} in {table} for '{ref}'")
                value = row.get(col)
            return value
        if ref == "as_of":
            return self.ctx.as_of
        if ref == "history_start":
            return self.ctx.history_start
        if ref == "first_of_next_month":
            return first_of_next_month(self.ctx.as_of)
        if ref.startswith("cfg."):
            return self.path(ref[4:], self.cfg)
        if ref.startswith("dates."):
            return self.ctx.dates[ref[6:]]
        if ref.startswith("prev."):
            prev = self.extra.get("prev")
            return None if prev is None else prev.get(ref[5:])
        if ref == "prev":
            return self.extra.get("prev")
        if ref in ("seq_in_parent", "sibling_index"):
            return self.extra.get("sibling_index")
        if ref == "sibling_count":
            return self.extra.get("sibling_count")
        if ref.startswith("row."):
            return self.extra["outer_row"].get(ref[4:]) if "outer_row" in self.extra else self.row.get(ref[4:])
        if ref.startswith("parent."):
            if self.parent is None:
                raise FlowError(f"'{ref}' used without a parent")
            return self.parent.get(ref[7:])
        if ref.startswith("anchor.") or ref.startswith("pre."):
            return self.extra.get(ref.split(".", 1)[1])
        if ref.startswith("pick."):
            return self.extra["pick"].get(ref[5:])
        if ref in self.row:
            return self.row[ref]
        if ref in self.fields and ref not in self._evaluating:      # referenced before its turn: evaluate on demand
            self._evaluating.add(ref)
            self.row[ref] = evaluate(self, self.fields[ref], self.entity)
            self._evaluating.discard(ref)
            return self.row[ref]
        if ref in self.extra:
            return self.extra[ref]
        raise FlowError(f"unknown reference '{ref}'" + (f" in entity '{self.entity}'" if self.entity else ""))


# ---------------------------------------------------------------------------
# Literals and conditions
# ---------------------------------------------------------------------------

def _literal(tok: str):
    tok = tok.strip()
    if tok == "null":
        return None
    if tok in ("true", "false"):
        return tok == "true"
    if re.fullmatch(r"-?\d+", tok):
        return int(tok)
    if re.fullmatch(r"-?\d+\.\d+", tok):
        return float(tok)
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'":
        return tok[1:-1]
    return tok


def _is_ref(tok: str) -> bool:
    tok = tok.strip()
    if tok in ("as_of", "history_start", "first_of_next_month", "prev", "seq_in_parent", "sibling_index", "sibling_count") or "->" in tok \
            or tok.startswith(("parent.", "cfg.", "anchor.", "pre.", "pick.", "prev.", "dates.", "row.")):
        return True
    return bool(re.fullmatch(r"[a-z_][a-z0-9_]*", tok)) and tok not in ("null", "true", "false")


def _value(env: Env, tok: str):
    tok = tok.strip()
    if tok.startswith("[") and tok.endswith("]"):
        return [_value(env, t) for t in tok[1:-1].split(",") if t.strip()]
    m = re.fullmatch(r"(.+?)\s*([+-])\s*(\d+)\s*(days?|hours?|minutes?)", tok)
    if m and _is_ref(m.group(1)):
        base = _value(env, m.group(1))
        n = int(m.group(3)) * (1 if m.group(2) == "+" else -1)
        unit = m.group(4).rstrip("s")
        return base + dt.timedelta(**{unit + "s": n})
    if _is_ref(tok):
        return env.resolve(tok)
    return _literal(tok)


def _norm(a, b):
    """Make two values comparable: dates vs timestamps vs iso strings, numbers vs numeric strings."""
    if isinstance(a, TS) and isinstance(b, D) and not isinstance(b, TS):
        a = a.date()
    if isinstance(b, TS) and isinstance(a, D) and not isinstance(a, TS):
        b = b.date()
    if isinstance(a, (D, TS)) and isinstance(b, str):
        b = TS.fromisoformat(b) if isinstance(a, TS) else D.fromisoformat(b[:10])
    if isinstance(b, (D, TS)) and isinstance(a, str):
        a = TS.fromisoformat(a) if isinstance(b, TS) else D.fromisoformat(a[:10])
    if isinstance(a, (int, float)) and isinstance(b, str):
        try:
            b = float(b)
        except ValueError:
            pass
    if isinstance(b, (int, float)) and isinstance(a, str):
        try:
            a = float(a)
        except ValueError:
            pass
    return a, b


def cond(env: Env, text: str) -> bool:
    text = text.strip()
    if text in ("", "true"):
        return True
    if text == "false":
        return False
    for op, fn in ((" or ", any), (" and ", all)):
        if op in text:
            return fn(cond(env, part) for part in text.split(op))
    if text.startswith("not "):
        return not cond(env, text[4:])
    m = re.fullmatch(r"(.+?)\s+in\s+(.+?)\.\.(.+)", text)
    if m:
        v = _value(env, m.group(1)); lo = _value(env, m.group(2)); hi = _value(env, m.group(3))
        v, lo = _norm(v, lo); v, hi = _norm(v, hi)
        return v is not None and lo <= v <= hi
    m = re.fullmatch(r"(.+?)\s+(==|!=|<=|>=|<|>|in)\s+(.+)", text)
    if not m:
        raise FlowError(f"cannot parse condition '{text}'")
    a, op, b = _value(env, m.group(1)), m.group(2), _value(env, m.group(3))
    if op == "in":
        return a in b
    if op in ("==", "!="):
        if a is None or b is None:
            return (a is None and b is None) == (op == "==")
        a, b = _norm(a, b)
        return (a == b) == (op == "==")
    a, b = _norm(a, b)
    if a is None or b is None:
        return False
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------

FUNC_RE = re.compile(r"^(last_weekday_before|next_weekday_after|add_business_days|first_of_month)\((.+)\)$")
DATE_RE = re.compile(r"^(?P<base>\w+\([^)]*\)|[^+\-@|]+?)\s*(?:(?P<sign>[+-])\s*(?P<lo>-?\d+)(?:\.\.(?P<hi>-?\d+))?\s*(?P<unit>minutes?|hours?|days?|business_days?))?"
                     r"\s*(?:@\s*(?P<h0>\d+)\.\.(?P<h1>\d+))?\s*(?P<mods>(?:\|\s*\w+\s*)*)$")


def _base_date(env: Env, base: str):
    base = base.strip()
    m = FUNC_RE.match(base)
    if m:
        fn, args = m.group(1), [a.strip() for a in m.group(2).split(",")]
        ref = _to_date(_value(env, args[0]))
        if fn == "last_weekday_before":
            return last_weekday_before(ref, WEEKDAYS[args[1]])
        if fn == "next_weekday_after":
            return next_weekday_after(ref, WEEKDAYS[args[1]])
        if fn == "add_business_days":
            return add_business_days(ref, int(args[1]))
        if fn == "first_of_month":
            return first_of_month(ref)
    return _value(env, base)


def _to_date(v):
    if isinstance(v, TS):
        return v.date()
    if isinstance(v, str):
        return D.fromisoformat(v[:10])
    return v


def _to_ts(v, env: Env, h0=None, h1=None):
    if isinstance(v, TS):
        return v
    if isinstance(v, str):
        return TS.fromisoformat(v) if len(v) > 10 else ts_on(env.rng, D.fromisoformat(v), h0 or 7, h1 or 17)
    return ts_on(env.rng, v, h0 or 7, h1 or 17)


def _datelike(env: Env, kind: str, rest: str):
    rest = re.sub(r"\{([^}]+)\}", lambda m: str(env.resolve(m.group(1))), rest)   # {field} placeholders inside offsets
    m = DATE_RE.match(rest.strip())
    if not m:
        raise FlowError(f"cannot parse {kind}:{rest}")
    base = _base_date(env, m.group("base"))
    if base is None:
        return None
    mods = [x.strip() for x in m.group("mods").split("|") if x.strip()]
    h0 = int(m.group("h0")) if m.group("h0") else None
    h1 = int(m.group("h1")) if m.group("h1") else None
    if kind == "date":
        val = _to_date(base)
    else:
        val = _to_ts(base, env, h0, h1) if not isinstance(base, TS) else base
    if m.group("sign"):
        lo = int(m.group("lo")); hi = int(m.group("hi")) if m.group("hi") is not None else lo
        n = env.rng.randint(min(lo, hi), max(lo, hi)) * (1 if m.group("sign") == "+" else -1)
        unit = m.group("unit").rstrip("s")
        if unit == "business_day":
            d = add_business_days(_to_date(val), n)
            val = d if kind == "date" else TS.combine(d, val.time())
        else:
            val = val + dt.timedelta(**{unit + "s": n})
            if kind == "date":
                val = _to_date(val)
    if h0 is not None and kind == "ts" and not m.group("sign") and isinstance(base, TS):
        val = ts_on(env.rng, base.date(), h0, h1)
    if "weekday" in mods:
        d = to_weekday(_to_date(val))
        val = d if kind == "date" else TS.combine(d, val.time())
    if "clamp" in mods:
        limit = env.ctx.as_of
        if _to_date(val) > limit:
            val = limit if kind == "date" else TS.combine(limit, dt.time(17, 0))
    return val


def _fmt_placeholder(env: Env, ph: str):
    ref, *filters = ph.split("|")
    if ref.startswith("seq"):
        return None  # handled by key
    v = env.resolve(ref)
    for f in filters:
        f = f.strip()
        if f == "lower":
            v = str(v).lower()
        elif f == "upper":
            v = str(v).upper()
        elif f == "slug":
            v = slug(str(v))
        elif f == "year":
            v = _to_date(v).year
        elif f == "date":
            v = iso(_to_date(v))
        elif f == "ascii":
            v = str(v).lower().replace("ö", "o").replace("ä", "a").replace("å", "a").replace("ø", "o").replace("æ", "ae")
        elif f.startswith("money"):
            v = f"{float(v):.2f}"
        elif f == "title":
            v = str(v).title()
        elif f == "ean13":                 # 12 digits in → 13 with check digit
            digits = "".join(ch for ch in str(v) if ch.isdigit())[:12].rjust(12, "0")
            total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(digits))
            v = digits + str((10 - total % 10) % 10)
        elif f.startswith("pad"):
            v = str(v).rjust(int(f[3:]), "0")
    return "" if v is None else str(v)


def _template(env: Env, text: str, entity: str = "") -> str:
    def rep(m):
        ph = m.group(1)
        if ph.startswith("seq"):
            width = int(ph.split(":")[1]) if ":" in ph else 0
            rest = re.sub(r"\{seq[^}]*\}", "", text)
            rest = re.sub(r"\{([^}]+)\}", lambda mm: _fmt_placeholder(env, mm.group(1)) or "", rest)
            k = (entity, rest)
            env.ctx.seqs[k] = env.ctx.seqs.get(k, 0) + 1
            return f"{env.ctx.seqs[k]:0{width}d}" if width else str(env.ctx.seqs[k])
        return _fmt_placeholder(env, ph)
    return re.sub(r"\{([^}]+)\}", rep, text)


def _weighted(env: Env, spec_text: str):
    if "=" in spec_text and "|" in spec_text or re.fullmatch(r"\s*\w+\s*=\s*[\d.]+\s*", spec_text):
        items = [p.split("=") for p in spec_text.split("|")]
        vals, ws = [i[0].strip() for i in items], [float(i[1]) for i in items]
    else:
        table = env.path(spec_text.strip(), env.pools)
        if isinstance(table, dict) and "values" in table:
            vals, ws = table["values"], table["weights"]
        else:
            vals, ws = list(table.keys()), [float(w) for w in table.values()]
    return env.rng.choices(vals, weights=ws, k=1)[0]


def _range(env: Env, text: str):
    m = re.fullmatch(r"\s*(-?[\d.]+)\s*\.\.\s*(-?[\d.]+)\s*", text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.fullmatch(r"\s*([\w.]+)\[(.+)\]\s*", text)
    if m:
        lo, hi = env.path(m.group(1), env.pools)[str(env.resolve(m.group(2)))]
        return float(lo), float(hi)
    raise FlowError(f"cannot parse range '{text}'")


_ALLOWED_AST = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.USub, ast.Call, ast.Name, ast.Load)


def _calc(env: Env, text: str):
    expr = re.sub(r"\{([^}]+)\}", lambda m: repr(float(env.resolve(m.group(1)) or 0)), text)
    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST) or (isinstance(node, ast.Name) and node.id not in ("round", "min", "max", "abs")):
            raise FlowError(f"calc: not allowed: {ast.dump(node)[:40]}")
    return eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, {"round": round, "min": min, "max": max, "abs": abs})


def _split_if(rest: str):
    """'COND then A else B' where A or B may themselves be if-expressions: the else that closes this if is
    the first one not consumed by a nested 'if:' inside the then-branch."""
    i = rest.find(" then ")
    if i < 0:
        raise FlowError(f"cannot parse if:{rest} (expected 'if:COND then A else B')")
    c, tail = rest[:i].strip(), rest[i + 6:]
    depth, pos = 0, 0
    for m in re.finditer(r" else |if:", tail):
        if m.group() == "if:":
            depth += 1
        elif depth == 0:
            return c, tail[:m.start()].strip(), tail[m.end():].strip()
        else:
            depth -= 1
    raise FlowError(f"cannot parse if:{rest} (no matching else)")


def evaluate(env: Env, expr, entity: str = ""):
    if not isinstance(expr, str):
        return expr
    s = expr.strip()
    if s == "null":
        return None
    if s == "seq":
        return len(env.ctx.tables[entity]) + 1
    if s in ("seq_in_parent", "sibling_index", "sibling_count", "as_of", "history_start", "first_of_next_month") or s.startswith(("dates.", "prev.")):
        return env.resolve(s)
    if ":" not in s:
        return _literal(s)
    kind, rest = s.split(":", 1)
    kind = kind.strip(); rest = rest.strip()
    if kind == "const":
        return _literal(rest)
    if kind == "copy":
        return env.resolve(rest)
    if kind == "key":
        return _template(env, rest, entity)
    if kind == "template":
        return _template(env, rest, entity)
    if kind == "pool":
        m = re.fullmatch(r"([\w.]+)(?:\[(.+)\])?", rest)
        table = env.path(m.group(1), env.pools)
        if m.group(2):
            table = table[str(env.resolve(m.group(2)))]
        return env.rng.choice(table)
    if kind == "weighted":
        return _weighted(env, rest)
    if kind == "choice":
        return _literal(env.rng.choice(rest.split("|")))
    if kind == "lookup":
        m = re.fullmatch(r"([\w.]+)\[(.+)\]", rest)
        return env.path(m.group(1), env.pools)[str(env.resolve(m.group(2)))]
    if kind in ("int", "float", "money"):
        lo, hi = _range(env, rest)
        if kind == "int":
            return env.rng.randint(int(lo), int(hi))
        v = env.rng.uniform(lo, hi)
        return round(v, 2) if kind == "money" else v
    if kind == "bool":
        return env.rng.random() < _number(env, rest)
    if kind == "rand":                      # rand:+358 40 ### ####  or  rand:PATH[REF] (pattern from a pools table); # = digit
        m = re.fullmatch(r"([\w.]+)\[(.+)\]", rest)
        pattern = env.path(m.group(1), env.pools)[str(env.resolve(m.group(2)))] if m else rest
        return "".join(str(env.rng.randint(0, 9)) if ch == "#" else ch for ch in pattern)
    if kind in ("date", "ts"):
        return _datelike(env, kind, rest)
    if kind == "status_by_age":
        m = re.fullmatch(r"(.+?)\s+using\s+bands\.(\w+)", rest)
        if not m:
            raise FlowError(f"cannot parse status_by_age:{rest} (expected 'status_by_age:FIELD using bands.NAME')")
        d = _to_date(env.resolve(m.group(1)))
        bands = [(b.get("max_age"), list(b["statuses"].keys()), list(b["statuses"].values())) for b in env.spec["bands"][m.group(2)]]
        return status_by_age(env.rng, (env.ctx.as_of - d).days, bands)
    if kind == "calc":
        return _calc(env, rest)
    if kind == "if":
        c, a, b = _split_if(rest)
        return evaluate(env, a, entity) if cond(env, c) else evaluate(env, b, entity)
    if kind == "pick":
        return _pick(env, rest)
    if kind == "pareto":
        m = re.fullmatch(r"([\d.]+)(?:\s+max\s+([\d.]+))?", rest)
        v = env.rng.paretovariate(float(m.group(1)))
        return min(v, float(m.group(2))) if m.group(2) else v
    if kind == "expo":
        m = re.fullmatch(r"([\d.]+)(?:\s+max\s+([\d.]+))?", rest)
        v = env.rng.expovariate(1 / float(m.group(1)))
        return min(v, float(m.group(2))) if m.group(2) else v
    if kind == "normal":
        m = re.fullmatch(r"(-?[\d.]+)\s+sd\s+([\d.]+)(?:\s+min\s+(-?[\d.]+))?(?:\s+max\s+(-?[\d.]+))?", rest)
        v = env.rng.gauss(float(m.group(1)), float(m.group(2)))
        if m.group(3):
            v = max(v, float(m.group(3)))
        if m.group(4):
            v = min(v, float(m.group(4)))
        return v
    if kind in ("sum", "count", "max", "min", "avg"):
        return _aggregate(env, kind, rest, entity)
    raise FlowError(f"unknown expression kind '{kind}' in '{expr}'")


def _pick(env: Env, rest: str):
    m = re.fullmatch(r"(\w+)(?:\s+where\s+(.+?))?(?:\s+weighted\s+by\s+(\w+))?", rest.strip())
    if not m:
        raise FlowError(f"cannot parse pick:{rest}")
    table, where, wfield = m.group(1), m.group(2), m.group(3)
    rows = env.ctx.tables.get(table, [])
    if where:
        # fast path: 'field == REF' partitions the table once by field value
        eq = re.fullmatch(r"(\w+)\s*==\s*(.+)", where)
        if eq and "->" not in eq.group(1):
            key = (table, eq.group(1))
            if key not in env.ctx.pick_cache:
                part = {}
                for r in rows:
                    part.setdefault(str(r.get(eq.group(1))), []).append(r)
                env.ctx.pick_cache[key] = part
            want = _value(Env(env.ctx, env.spec, env.pools, env.cfg, row=env.row, parent=env.parent, extra=env.extra), eq.group(2))
            cands = env.ctx.pick_cache[key].get(str(want), [])
        else:
            outer = env.row
            cands = [r for r in rows if cond(Env(env.ctx, env.spec, env.pools, env.cfg, row=r, parent=env.parent, extra={**env.extra, "outer_row": outer}), where)]
    else:
        cands = rows
    if not cands:
        return None
    if wfield:
        ck = (table, where, wfield, "w")
        if ck not in env.ctx.pick_cache or env.ctx.pick_cache[ck][0] is not cands:
            env.ctx.pick_cache[ck] = (cands, [float(r.get(wfield) or 0) for r in cands])
        return env.rng.choices(cands, weights=env.ctx.pick_cache[ck][1], k=1)[0].get("id")
    return env.rng.choice(cands).get("id")


def _aggregate(env: Env, kind: str, rest: str, entity: str):
    m = re.fullmatch(r"(\w+)(?:\.(\w+))?(?:\s+via\s+(\w+))?", rest.strip())
    if not m:
        raise FlowError(f"cannot parse {kind}:{rest}")
    child, col, fk = m.group(1), m.group(2), m.group(3)
    if fk is None:
        fk = env.spec["_fk"].get((child, entity))
        if fk is None:
            raise FlowError(f"{kind}:{rest}: no reference column from {child} to {entity}; say 'via COLUMN'")
    ck = ("agg", child, fk)
    if ck not in env.ctx.pick_cache:
        groups = {}
        for r in env.ctx.tables.get(child, []):
            groups.setdefault(r.get(fk), []).append(r)
        env.ctx.pick_cache[ck] = groups
    rows = env.ctx.pick_cache[ck].get(env.row.get("id"), [])
    if kind == "count":
        return len(rows)
    vals = [float(r.get(col)) for r in rows if r.get(col) not in (None, "")]
    if not vals:
        return 0 if kind in ("sum",) else None
    return {"sum": sum(vals), "max": max(vals), "min": min(vals), "avg": sum(vals) / len(vals)}[kind]


# ---------------------------------------------------------------------------
# Row generation
# ---------------------------------------------------------------------------

def _number(env: Env, v):
    """A literal number or 'cfg:path' / a reference to one."""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s.startswith("cfg:"):
        return float(env.path(s[4:], env.cfg))
    if _is_ref(s):
        return float(env.resolve(s))
    return float(s)


def _count(env: Env, text, scale=True):
    if isinstance(text, (int, float)):
        n = float(text)
    else:
        s = str(text).strip()
        m = re.fullmatch(r"(-?\d+)\.\.(-?\d+)", s)
        if m:
            return env.rng.randint(int(m.group(1)), int(m.group(2)))
        m = re.fullmatch(r"cfg:([\w.]+)\s*(?:([*/])\s*([\d.]+))?", s)
        if m:
            raw = env.path(m.group(1), env.cfg)
            if isinstance(raw, str):                 # a config value may itself be a count expression, e.g. "18..35"
                return _count(env, raw, scale=False)
            n = float(raw)
            if m.group(2):
                n = n * float(m.group(3)) if m.group(2) == "*" else n / float(m.group(3))
        else:
            n = float(s)
    if scale:
        n *= env.ctx.scale
    return int(round(n))


def _new_row(ctx: FlowCtx, entity: str, spec, columns, env: Env, preset=None):
    row = dict(preset or {})
    env.row = row
    fields = spec.get("fields", {})
    env.fields, env.entity = fields, entity
    if "id" in columns and "id" not in row and "id" not in fields:
        row["id"] = len(ctx.tables[entity]) + 1
    for name, expr in fields.items():             # authoring order: scratch fields (prefixed _) can feed later columns
        if name not in row:
            row[name] = evaluate(env, expr, entity)
    for col in columns:
        row.setdefault(col, None)
    if spec.get("drop_when") and cond(env, spec["drop_when"]):
        return None
    ctx.tables[entity].append(row)
    ctx.index.setdefault(entity, {})[row.get("id")] = row
    return row


def generate_entity(ctx: FlowCtx, name: str, spec, columns, flow, pools, cfg, hooks=None):
    env = Env(ctx, flow, pools, cfg)
    if "rows_from" in spec:
        rf = spec["rows_from"]
        for values in env.path(rf["pool"], pools):
            preset = dict(zip(rf["columns"], values))
            _new_row(ctx, name, spec, columns, Env(ctx, flow, pools, cfg), preset)
    elif "per" in spec:
        per = spec["per"]
        if "parent" in per:
            parents = ctx.tables[per["parent"]]
            for p in parents:
                penv = Env(ctx, flow, pools, cfg, parent=p)
                if per.get("when") and not cond(penv, per["when"]):
                    continue
                if "share" in per and ctx.rng.random() >= _number(penv, per["share"]):
                    continue
                if "variants" in spec:
                    for var in spec["variants"]:
                        venv = Env(ctx, flow, pools, cfg, parent=p)
                        if cond(venv, var.get("when", "true")):
                            merged = dict(spec); merged["fields"] = {**spec.get("fields", {}), **var.get("fields", {})}
                            _new_row(ctx, name, merged, columns, venv)
                    continue
                n = _count(penv, per.get("count", 1), scale=False)
                prev = None
                for i in range(n):
                    r = _new_row(ctx, name, spec, columns, Env(ctx, flow, pools, cfg, parent=p, extra={"prev": prev, "sibling_index": i + 1, "sibling_count": n}))
                    prev = r if r is not None else prev
        elif per.get("day") == "history":
            candidates = ctx.tables[per["pick"]] if per.get("pick") else [None]
            if per.get("pick_where"):
                candidates = [c for c in candidates if cond(Env(ctx, flow, pools, cfg, row=c), per["pick_where"])]
            bursts = []
            for b in spec.get("burst", []):
                benv = Env(ctx, flow, pools, cfg)
                bursts.append((_to_date(evaluate(benv, b["from"])), _to_date(evaluate(benv, b["to"])), b))
            season = env.path(per["seasonality"], pools) if per.get("seasonality") else None
            day = ctx.history_start
            while day <= ctx.as_of:
                denv = Env(ctx, flow, pools, cfg, extra={"day": day})
                n = _count(denv, per.get("count", 1))
                if season:
                    n = int(round(n * float(season.get(str(day.month), 1.0))))
                if per.get("weekdays_only") and day.weekday() >= 5:
                    n = 0
                extra_n, active_bursts = 0, []
                for lo, hi, b in bursts:
                    if lo <= day <= hi:
                        extra_n += int(n * _number(Env(ctx, flow, pools, cfg), b.get("factor", 1)))
                        active_bursts.append(b)
                weights = None
                if per.get("pick_weight") and candidates and candidates[0] is not None:
                    weights = [float(c.get(per["pick_weight"]) or 0) for c in candidates]
                for i in range(n + extra_n):
                    parent = (ctx.rng.choices(candidates, weights=weights, k=1)[0] if weights else ctx.rng.choice(candidates)) if candidates else None
                    preset = {}
                    renv = Env(ctx, flow, pools, cfg, parent=parent, extra={"day": day})
                    for b in active_bursts:
                        if ctx.rng.random() < _number(renv, b.get("prob", 1)) and cond(renv, b.get("when", "true")):
                            preset.update(b.get("set", {}))
                    _new_row(ctx, name, spec, columns, renv, preset)
                day += dt.timedelta(days=1)
        else:
            raise FlowError(f"{name}: per needs parent or day = 'history'")
    else:
        n = _count(env, spec.get("count", 0), scale=spec.get("scale", True))
        for _ in range(n):
            _new_row(ctx, name, spec, columns, Env(ctx, flow, pools, cfg))
    if hooks and hasattr(hooks, f"after_{name}"):
        getattr(hooks, f"after_{name}")(ctx)


def evaluate_dates(ctx: FlowCtx, flow, pools, cfg):
    env = Env(ctx, flow, pools, cfg)
    for k, expr in flow.get("dates", {}).items():
        ctx.dates[k] = evaluate(env, expr)


def run_after(ctx: FlowCtx, flow, pools, cfg, spec_columns):
    """[entity.X.after] fields: aggregates and derived values, once every entity exists."""
    for name, espec in flow["entity"].items():
        after = espec.get("after")
        if not after:
            continue
        ctx.pick_cache = {k: v for k, v in ctx.pick_cache.items() if not (isinstance(k, tuple) and k and k[0] == "agg")}
        for row in ctx.tables[name]:
            env = Env(ctx, flow, pools, cfg, row=row)
            env.fields, env.entity = {}, name
            for col, expr in after.items():
                row[col] = evaluate(env, expr, name)


def _ensure(ctx, flow, pools, cfg, en, pre, spec_columns):
    """Pick a row matching `where`, or create the row (and children) through field expressions."""
    entity = en["entity"]
    picked = None
    if not en.get("always"):
        for cand in ctx.tables[entity]:
            if cond(Env(ctx, flow, pools, cfg, row=cand, extra=dict(pre)), en.get("where", "true")):
                picked = cand
                break
    if picked is None:
        espec = dict(flow["entity"].get(entity, {}))
        espec["fields"] = {**espec.get("fields", {}), **en.get("fields", {})}
        espec.pop("drop_when", None)
        parent = None
        if en.get("parent_pick"):
            pid = _pick(Env(ctx, flow, pools, cfg, extra=dict(pre)), en["parent_pick"])
            parent = ctx.index[en["parent_pick"].split()[0]][pid]
        env = Env(ctx, flow, pools, cfg, parent=parent, extra=dict(pre))
        picked = _new_row(ctx, entity, espec, spec_columns[entity], env)
        for ch in en.get("children", []):
            cspec = dict(flow["entity"].get(ch["entity"], {}))
            cspec["fields"] = {**cspec.get("fields", {}), **ch.get("fields", {})}
            cspec.pop("drop_when", None)
            n = ch.get("count", 1)
            prev = None
            for i in range(int(n)):
                cenv = Env(ctx, flow, pools, cfg, parent=picked, extra={**pre, "prev": prev, "sibling_index": i + 1, "sibling_count": int(n)})
                for k, v in ch.get("field_lists", {}).items():   # per-child literal values, e.g. product ids
                    cenv.extra[k] = v[i % len(v)]
                r = _new_row(ctx, ch["entity"], cspec, spec_columns[ch["entity"]], cenv)
                prev = r if r is not None else prev
        picked["_ensured"] = True
    return picked


def generate_anchors(ctx: FlowCtx, flow, pools, cfg, spec_columns=None):
    for an in flow.get("anchor", []):
        group, key = an["group"], an["key"]
        env = Env(ctx, flow, pools, cfg)
        pre = {}
        for k, expr in an.get("pre", {}).items():
            env.extra = pre
            pre[k] = evaluate(env, expr)
        picked = None
        if "ensure" in an:
            picked = _ensure(ctx, flow, pools, cfg, an["ensure"], pre, spec_columns)
        elif "pick" in an:
            pk = an["pick"]
            for cand in ctx.tables[pk["entity"]]:
                cenv = Env(ctx, flow, pools, cfg, row=cand, extra=dict(pre))
                if not cond(cenv, pk.get("where", "true")):
                    continue
                if "none_of" in pk:
                    no = pk["none_of"]
                    clash = False
                    for other in ctx.tables[no["entity"]]:
                        if other.get(no["link"]) == cand.get("id"):
                            oenv = Env(ctx, flow, pools, cfg, row=other, extra=dict(pre))
                            if cond(oenv, no.get("where", "true")):
                                clash = True
                                break
                    if clash:
                        continue
                picked = cand
                break
            if picked is None:
                raise FlowError(f"anchor {key}: no row of {pk['entity']} matches")
        out = dict(pre)
        fenv = Env(ctx, flow, pools, cfg, row=out, extra={**pre, "pick": picked or {}})
        for k, expr in an.get("fields", {}).items():
            out[k] = evaluate(fenv, expr)
            fenv.extra[k] = out[k]
        if picked is not None:
            out.setdefault("pick_id", picked.get("id"))
        ctx.anchors.setdefault(group, {})[key] = {k: (iso(v) if isinstance(v, (D, TS)) else v) for k, v in out.items()}


def build_steps(domain, flow, pools):
    """Return the list of step functions dsgen.cli runs, one per entity in flow order, then anchors."""
    from .model import CFG
    spec = domain.spec
    hooks = domain.lifecycle
    steps = []
    spec_columns = {t: spec.column_names(t) for t in spec.tables}
    flow["_fk"] = {(e.name, c.ref.split(".")[0]): c.name for e in spec.entities for c in e.columns if c.ref}
    def dates(ctx):
        evaluate_dates(ctx, flow, pools, CFG)
    dates.__name__ = "dates"
    steps.append(dates)
    for name, espec in flow["entity"].items():
        cols = spec_columns[name]
        def step(ctx, name=name, espec=espec, cols=cols):
            generate_entity(ctx, name, espec, cols, flow, pools, CFG, hooks)
        step.__name__ = f"gen_{name}"
        steps.append(step)
    def anchors(ctx):
        generate_anchors(ctx, flow, pools, CFG, spec_columns)
        run_after(ctx, flow, pools, CFG, spec_columns)
        if hooks and hasattr(hooks, "after_anchors"):
            hooks.after_anchors(ctx)
    anchors.__name__ = "gen_anchors"
    steps.append(anchors)
    return steps


def make_ctx(rng, as_of, scale, months) -> FlowCtx:
    return FlowCtx(rng=rng, as_of=as_of, scale=scale, months=months)
