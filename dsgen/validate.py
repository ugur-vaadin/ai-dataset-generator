"""Validate a domain pack before generation: structure of domain.toml, config.toml, scenarios.toml,
checks.toml, pools/*.toml, and that lifecycle.py provides make_ctx and STEPS. Machine-checked contracts
are what make LLM-authored packs reliable; run this first, then `generate --check`."""
from __future__ import annotations

import importlib
import os
import re
import tomllib

TYPE_RE = re.compile(r"^(INT|BIGINT|SMALLINT|VARCHAR\(\d+\)|CHAR\(\d+\)|DECIMAL\(\d+,\d+\)|DATE|TIMESTAMP|BOOLEAN|\{TEXT\})$")
PII = {"name", "contact", "identifier", "free-text", "none"}
EXPECT_KINDS = {"sql_zero", "sql_one", "sql_positive", "weekday", "min", "before_as_of", "document_contains"}
WEEKDAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}


def _toml(path, problems, required=True):
    if not os.path.exists(path):
        if required:
            problems.append(f"missing file: {os.path.relpath(path)}")
        return None
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        problems.append(f"{os.path.relpath(path)}: TOML error: {e}")
        return None


EXPR_KINDS = {"const", "copy", "key", "template", "pool", "weighted", "choice", "lookup", "int", "float", "money", "bool", "rand",
              "date", "ts", "status_by_age", "calc", "if", "pick", "pareto", "expo", "normal", "sum", "count", "max", "min", "avg"}
AGG_KINDS = {"sum", "count", "max", "min", "avg"}


def _pool_path(pools, dotted):
    obj = pools
    for part in dotted.split("."):
        if isinstance(obj, dict) and part in obj:
            obj = obj[part]
        else:
            return None
    return obj


def _check_expr(P, where, expr, pools, flow):
    if not isinstance(expr, str) or ":" not in expr:
        return
    kind, rest = expr.split(":", 1)
    kind = kind.strip()
    if kind not in EXPR_KINDS:
        if re.match(r"^[a-z_]+$", kind):
            P.append(f"flow.toml: {where}: unknown expression kind '{kind}:' (known: {', '.join(sorted(EXPR_KINDS))})")
        return
    if kind in ("pool", "lookup", "weighted", "rand", "money") :
        m = re.match(r"\s*([\w.]+)(\[|$|\s)", rest)
        if m and kind != "weighted" or (kind == "weighted" and "=" not in rest and m):
            path = m.group(1)
            if kind == "money" and re.match(r"^-?[\d.]+$", path):
                return
            if _pool_path(pools, path) is None:
                P.append(f"flow.toml: {where}: pools path '{path}' not found")
    if kind == "status_by_age":
        m = re.search(r"using\s+bands\.(\w+)", rest)
        if not m:
            P.append(f"flow.toml: {where}: expected 'status_by_age:FIELD using bands.NAME'")
        elif m.group(1) not in flow.get("bands", {}):
            P.append(f"flow.toml: {where}: bands.{m.group(1)} not defined")
    if kind == "if":
        try:
            from .flow import _split_if
            _, a, b = _split_if(rest)
            _check_expr(P, where, a, pools, flow)
            _check_expr(P, where, b, pools, flow)
        except Exception as e:
            P.append(f"flow.toml: {where}: {e}")
    if kind == "pick":
        m = re.match(r"(\w+)", rest.strip())
        tables = flow.get("_tables", set())
        if tables and m and m.group(1) not in tables:
            P.append(f"flow.toml: {where}: pick from unknown entity '{m.group(1)}'")
    if kind in AGG_KINDS:
        m = re.match(r"(\w+)(?:\.(\w+))?", rest.strip())
        tables = flow.get("_tables", set())
        if tables and m and m.group(1) not in tables:
            P.append(f"flow.toml: {where}: {kind} over unknown entity '{m.group(1)}'")
        if kind != "count" and m and not m.group(2):
            P.append(f"flow.toml: {where}: {kind} needs a column ({kind}:CHILD.COLUMN)")
    if kind in ("date", "ts") and not re.match(r"^(?:\w+\([^)]*\)|[^+\-@|]+?)\s*(?:[+-]\s*(?:-?\d+(\.\.-?\d+)?|\{[^}]+\})\s*(minutes?|hours?|days?|business_days?))?\s*(@\s*\d+\.\.\d+)?\s*(\|\s*\w+\s*)*$", rest.strip()):
        P.append(f"flow.toml: {where}: cannot parse '{kind}:{rest}'")


def validate(path: str) -> list[str]:
    """Returns a list of problems (empty = valid)."""
    P = []
    name = os.path.basename(path.rstrip("/"))
    d = _toml(os.path.join(path, "domain.toml"), P)
    tables = {}
    if d:
        dom = d.get("domain", {})
        for k in ("name", "company", "description"):
            if not dom.get(k):
                P.append(f"domain.toml: [domain].{k} is required")
        if dom.get("name") and dom["name"] != name:
            P.append(f"domain.toml: [domain].name '{dom['name']}' differs from folder name '{name}'")
        ents = d.get("entity", [])
        if not ents:
            P.append("domain.toml: at least one [[entity]] is required")
        for e in ents:
            en = e.get("name")
            if not en or not re.match(r"^[a-z][a-z0-9_]*$", en):
                P.append(f"domain.toml: entity name '{en}' must be snake_case")
                continue
            if en in tables:
                P.append(f"domain.toml: duplicate entity '{en}'")
            cols = e.get("columns", [])
            tables[en] = {c.get("name") for c in cols}
            if not cols:
                P.append(f"domain.toml: entity '{en}' has no columns")
            if e.get("exposed", True) and not e.get("description"):
                P.append(f"domain.toml: exposed entity '{en}' needs a description (the model reads it)")
            if not any(c.get("pk") for c in cols):
                P.append(f"domain.toml: entity '{en}' has no primary key column (pk = true)")
            for c in cols:
                cn = c.get("name")
                if not cn or not re.match(r"^[a-z][a-z0-9_]*$", cn):
                    P.append(f"domain.toml: {en}: column name '{cn}' must be snake_case")
                if not TYPE_RE.match(c.get("type", "")):
                    P.append(f"domain.toml: {en}.{cn}: unsupported type '{c.get('type')}' (use INT, BIGINT, VARCHAR(n), CHAR(n), DECIMAL(p,s), DATE, TIMESTAMP, BOOLEAN, {{TEXT}})")
                if c.get("pii", "none") not in PII:
                    P.append(f"domain.toml: {en}.{cn}: pii must be one of {sorted(PII)}")
        for e in ents:
            for c in e.get("columns", []):
                if c.get("ref"):
                    if "." not in c["ref"]:
                        P.append(f"domain.toml: {e['name']}.{c['name']}: ref must be 'table.column'")
                    else:
                        rt, rc = c["ref"].split(".", 1)
                        if rt not in tables:
                            P.append(f"domain.toml: {e['name']}.{c['name']}: ref to unknown table '{rt}'")
                        elif rc not in tables[rt]:
                            P.append(f"domain.toml: {e['name']}.{c['name']}: ref to unknown column '{rt}.{rc}'")
        # entity order must allow FK-ordered loading (referenced tables first)
        seen = set()
        for e in ents:
            for c in e.get("columns", []):
                if c.get("ref") and "." in c["ref"]:
                    rt = c["ref"].split(".")[0]
                    if rt != e["name"] and rt not in seen:
                        P.append(f"domain.toml: entity '{e['name']}' references '{rt}' which is defined later; loaders insert in file order")
            seen.add(e.get("name"))
        ai = d.get("ai_schema", {})
        for k in ("intro", "hints"):
            if not ai.get(k):
                P.append(f"domain.toml: [ai_schema].{k} is required")
        if "{dialect_hints}" not in ai.get("hints", ""):
            P.append("domain.toml: [ai_schema].hints should contain {dialect_hints}")
        for dl in ("h2", "postgres"):
            if dl not in ai.get("dialects", {}):
                P.append(f"domain.toml: [ai_schema.dialects.{dl}] missing (label + hints)")
        for v in d.get("views", {}):
            if v not in d.get("sql", {}).get("views", ""):
                P.append(f"domain.toml: view '{v}' is described for the model but not created in [sql].views")
    cfg = _toml(os.path.join(path, "config.toml"), P)
    if cfg:
        g = cfg.get("generation", {})
        for k in ("as_of", "seed", "scale", "months"):
            if k not in g:
                P.append(f"config.toml: [generation].{k} is required")
    sc = _toml(os.path.join(path, "scenarios.toml"), P, required=False)
    if sc:
        keys = set()
        for s in sc.get("scenario", []):
            k = s.get("key")
            if not k:
                P.append("scenarios.toml: every [[scenario]] needs a key")
                continue
            if k in keys:
                P.append(f"scenarios.toml: duplicate scenario key '{k}'")
            keys.add(k)
            if s.get("document"):
                tmpl = os.path.join(path, "documents", s["document"] + ".tmpl")
                if not os.path.exists(tmpl):
                    P.append(f"scenarios.toml: {k}: template not found: documents/{s['document']}.tmpl")
            for e in s.get("expect", []):
                kind = e.get("kind")
                if kind not in EXPECT_KINDS:
                    P.append(f"scenarios.toml: {k}: unknown expectation kind '{kind}'")
                elif kind.startswith("sql") and not e.get("sql"):
                    P.append(f"scenarios.toml: {k}: {kind} needs sql")
                elif kind == "weekday" and e.get("weekday") not in WEEKDAYS:
                    P.append(f"scenarios.toml: {k}: weekday must be a day name")
                elif kind in ("weekday", "min", "before_as_of") and not e.get("field"):
                    P.append(f"scenarios.toml: {k}: {kind} needs field")
            for im in s.get("image", []):
                for f in ("file", "prompt"):
                    if not im.get(f):
                        P.append(f"scenarios.toml: {k}: image needs {f}")
    ck = _toml(os.path.join(path, "checks.toml"), P, required=False)
    if ck:
        for c in ck.get("check", []):
            if not c.get("name") or not c.get("sql"):
                P.append("checks.toml: every [[check]] needs name and sql")
        for c in ck.get("smoke", []):
            if not c.get("name") or not c.get("sql"):
                P.append("checks.toml: every [[smoke]] needs name and sql")
    pools = os.path.join(path, "pools")
    if os.path.isdir(pools):
        for f in sorted(os.listdir(pools)):
            if f.endswith(".toml"):
                _toml(os.path.join(pools, f), P)
    ov = _toml(os.path.join(path, "review", "overrides.toml"), P, required=False)
    if ov:
        for o in ov.get("override", []):
            if o.get("kind") and not o.get("id"):     # blanket answer for a whole kind (optionally table/column)
                if o["kind"] not in ("document", "anchor", "pii-free-text", "template", "outlier"):
                    P.append(f"review/overrides.toml: kind '{o['kind']}' must be document, anchor, pii-free-text, template or outlier")
                if o.get("action", "approve") != "approve":
                    P.append(f"review/overrides.toml: kind '{o['kind']}': a blanket answer can only approve; reject or replace by id")
                continue
            if not re.match(r"^(doc|anchor|row|template):", o.get("id", "")):
                P.append(f"review/overrides.toml: id '{o.get('id')}' must start with doc:, anchor:, row: or template: (or give a kind)")
            if o.get("action") not in ("approve", "reject", "replace"):
                P.append(f"review/overrides.toml: {o.get('id')}: action must be approve, reject or replace")
            if o.get("action") == "replace" and "value" not in o:
                P.append(f"review/overrides.toml: {o.get('id')}: replace needs value")
    # ---- flow.toml: entities match the spec, fields are columns or scratch, expressions parse, pools/bands resolve
    fl = _toml(os.path.join(path, "flow.toml"), P, required=False)
    if fl and d:
        import tomllib as _t
        pools = {}
        pdir = os.path.join(path, "pools")
        if os.path.isdir(pdir):
            for fn in sorted(os.listdir(pdir)):
                if fn.endswith(".toml"):
                    try:
                        pools.update(_t.load(open(os.path.join(pdir, fn), "rb")))
                    except _t.TOMLDecodeError:
                        pass
        pools.update(fl.get("pools", {}))
        spec_tables = {e["name"]: [c["name"] for c in e.get("columns", [])] for e in d.get("entity", [])}
        fl["_tables"] = set(spec_tables)
        for dname, dexpr in fl.get("dates", {}).items():
            _check_expr(P, f"dates.{dname}", dexpr, pools, fl)
        ents = fl.get("entity", {})
        for t in spec_tables:
            if t not in ents:
                P.append(f"flow.toml: entity '{t}' is in domain.toml but has no [entity.{t}] in flow.toml (it would stay empty)")
        seen = []
        for ename, e in ents.items():
            if ename not in spec_tables:
                P.append(f"flow.toml: [entity.{ename}] is not an entity in domain.toml")
                continue
            per = e.get("per", {})
            if "parent" in per and per["parent"] not in seen:
                P.append(f"flow.toml: {ename}: parent '{per['parent']}' must be generated before {ename} (define it earlier)")
            if per.get("pick") and per["pick"] not in seen:
                P.append(f"flow.toml: {ename}: pick '{per['pick']}' must be generated before {ename}")
            if "per" in e and "parent" not in per and per.get("day") != "history":
                P.append(f"flow.toml: {ename}: per needs parent = '...' or day = 'history'")
            if "rows_from" in e:
                rf = e["rows_from"]
                if not _pool_path(pools, rf.get("pool", "")):
                    P.append(f"flow.toml: {ename}: rows_from.pool '{rf.get('pool')}' not found in pools")
            fields = dict(e.get("fields", {}))
            for var in e.get("variants", []):
                fields.update(var.get("fields", {}))
            for acol, aexpr in e.get("after", {}).items():
                if acol not in spec_tables[ename]:
                    P.append(f"flow.toml: {ename}.after.{acol}: not a column of {ename}")
                _check_expr(P, f"{ename}.after.{acol}", aexpr, pools, fl)
                fields.setdefault(acol, aexpr)
            if per.get("seasonality") and _pool_path(pools, per["seasonality"]) is None:
                P.append(f"flow.toml: {ename}: seasonality table '{per['seasonality']}' not found in pools")
            if per.get("pick_weight") and per.get("pick") and per["pick_weight"] not in spec_tables.get(per["pick"], []) :
                P.append(f"flow.toml: {ename}: pick_weight '{per['pick_weight']}' is not a column of {per['pick']}")
            for fname, expr in fields.items():
                if fname not in spec_tables[ename] and not fname.startswith("_"):
                    P.append(f"flow.toml: {ename}.{fname}: not a column of {ename} (scratch fields must start with _)")
                _check_expr(P, f"{ename}.{fname}", expr, pools, fl)
            for col in spec_tables[ename]:
                if col not in fields and col != "id" and not (e.get("rows_from") and col in e["rows_from"].get("columns", [])):
                    P.append(f"flow.toml: {ename}.{col}: column has no field expression (it will be NULL)")
            seen.append(ename)
        for an in fl.get("anchor", []):
            for k in ("group", "key"):
                if k not in an:
                    P.append(f"flow.toml: every [[anchor]] needs {k}")
            pk = an.get("pick")
            if pk and pk.get("entity") not in spec_tables:
                P.append(f"flow.toml: anchor {an.get('key')}: pick.entity '{pk.get('entity')}' unknown")
            en = an.get("ensure")
            if en:
                if en.get("entity") not in spec_tables:
                    P.append(f"flow.toml: anchor {an.get('key')}: ensure.entity '{en.get('entity')}' unknown")
                for fname, expr in en.get("fields", {}).items():
                    _check_expr(P, f"anchor {an.get('key')}.ensure.{fname}", expr, pools, fl)
                for ch in en.get("children", []):
                    if ch.get("entity") not in spec_tables:
                        P.append(f"flow.toml: anchor {an.get('key')}: ensure child entity '{ch.get('entity')}' unknown")
                    for fname, expr in ch.get("fields", {}).items():
                        _check_expr(P, f"anchor {an.get('key')}.ensure.{ch.get('entity')}.{fname}", expr, pools, fl)
            for fname, expr in {**an.get("pre", {}), **an.get("fields", {})}.items():
                _check_expr(P, f"anchor {an.get('key')}.{fname}", expr, pools, fl)
    lc = os.path.join(path, "lifecycle.py")
    has_flow = os.path.exists(os.path.join(path, "flow.toml"))
    if not os.path.exists(lc) and not has_flow:
        P.append("missing file: flow.toml (declarative) or lifecycle.py (Python)")
    elif os.path.exists(lc):
        try:
            mod = importlib.import_module(f"domains.{name}.lifecycle")
            if not has_flow:
                for attr in ("make_ctx", "STEPS"):
                    if not hasattr(mod, attr):
                        P.append(f"lifecycle.py: must define {attr} (or add a flow.toml)")
        except Exception as e:
            P.append(f"lifecycle.py: import failed: {type(e).__name__}: {e}")
    return P
