"""Consistency checks for a generated dataset: generic checks from the spec (foreign keys, uniqueness,
NOT NULL, CSV headers, model-facing schema text), SQL checks from checks.toml, then the domain's own
checks (domains/<name>/checks.py). SQLite is the engine, so no database is needed."""
from __future__ import annotations

import csv
import json
import os
import re
import sqlite3


def load(out, spec):
    con = sqlite3.connect(":memory:")
    for t in spec.tables:
        defs = []
        for c in spec.entity(t).columns:
            ty = c.type.upper()
            aff = "INTEGER" if ty.startswith("INT") or ty.startswith("BIGINT") else "REAL" if ty.startswith("DECIMAL") else "TEXT"
            defs.append(f"{c.name} {aff}")
        con.execute(f"CREATE TABLE {t} ({', '.join(defs)})")
        with open(os.path.join(out, "csv", f"{t}.csv"), newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            header = next(r)
            assert header == spec.column_names(t), f"{t}: CSV header differs from spec"
            rows = [[None if v == "" else (1 if v == "true" else 0 if v == "false" else v) for v in row] for row in r]
        con.executemany(f"INSERT INTO {t} VALUES ({','.join('?' * len(defs))})", rows)
        for c in spec.entity(t).columns:
            if c.ref or c.pk or c.unique:
                con.execute(f"CREATE INDEX ix_{t}_{c.name} ON {t}({c.name})")
    con.commit()
    return con


def run(domain, out: str, quiet: bool = False):
    """Run all checks. Returns (failures, report)."""
    spec = domain.spec
    manifest = json.load(open(os.path.join(out, "manifest.json"), encoding="utf-8"))
    manifest["_out"] = out
    as_of = manifest["as_of"]
    con = load(out, spec)
    q = lambda sql, *p: con.execute(sql, p).fetchall()
    one = lambda sql, *p: con.execute(sql, p).fetchone()[0]
    failures, report = [], {"as_of": as_of, "domain": domain.name, "checks": {}, "summaries": {}}

    def check(name, ok, detail=""):
        report["checks"][name] = {"ok": bool(ok), "detail": detail}
        if not quiet or not ok:
            print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))
        if not ok:
            failures.append(name)

    # --- generic: integrity from the spec
    for t in spec.tables:
        for c in spec.entity(t).columns:
            if c.ref:
                rt, rc = c.ref.split(".")
                dangling = one(f"SELECT COUNT(*) FROM {t} x WHERE x.{c.name} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM {rt} r WHERE r.{rc} = x.{c.name})")
                check(f"fk {t}.{c.name} -> {rt}.{rc}", dangling == 0, f"{dangling} dangling")
            if c.pk or c.unique:
                dup = one(f"SELECT COUNT(*) - COUNT(DISTINCT {c.name}) FROM {t}")
                check(f"unique {t}.{c.name}", dup == 0, f"{dup} duplicates")
            if c.not_null or c.pk:
                nulls = one(f"SELECT COUNT(*) FROM {t} WHERE {c.name} IS NULL")
                if nulls:
                    check(f"not null {t}.{c.name}", False, f"{nulls} nulls")

    # --- generic: the model-facing schema text is complete and hides what it should
    missing = spec.undocumented_columns()
    check("every exposed column is described for the model", not missing, str(missing[:5]))
    text = open(os.path.join(out, "sql", "ai-schema-h2.txt"), encoding="utf-8").read()
    for t in spec.exposed_tables:
        m = re.search(rf"^{t}\((.*?)\)$", text, re.M)
        cols_in_text = [c.strip() for c in m.group(1).split(",")] if m else []
        check(f"schema text lists all columns of {t}", cols_in_text == spec.column_names(t))
    for t in spec.hidden_tables:
        check(f"schema text hides {t}", f"{t}(" not in text)

    # --- checks.toml: SQL that must return 0 (SQLite dialect); {as_of} is substituted
    for chk in domain.checks.get("check", []):
        sql = chk["sql"].replace("{as_of}", f"'{as_of}'")
        try:
            n = one(sql)
            check(chk["name"], n == 0, f"{n} rows" if n else "")
        except sqlite3.Error as e:
            check(chk["name"], False, f"SQL error: {e}")

    # --- scenarios.toml: expectations about the anchor records and their documents
    group = domain.scenarios.get("scenarios", {}).get("anchors_group")
    for sc in domain.scenarios.get("scenario", []):
        anchors = manifest["anchors"][group] if group else manifest["anchors"]
        a = anchors.get(sc["key"])
        check(f"scenario {sc['key']}: anchor record present", a is not None)
        if a is None:
            continue
        flat = {k: ("; ".join(map(str, val)) if isinstance(val, list) else val) for k, val in a.items()}
        flat.update(manifest.get("document_context", {}).get(sc["key"], {}))
        def fill(s):
            for k, val in flat.items():
                s = s.replace("{" + k + "}", "<NULL:" + k + ">" if val is None else str(val))
            return s
        doc_text = None
        if sc.get("document"):
            p = os.path.join(out, "documents", sc["document"])
            doc_text = open(p, encoding="utf-8").read() if os.path.exists(p) else None
            check(f"scenario {sc['key']}: document rendered", doc_text is not None, sc["document"])
        for e in sc.get("expect", []):
            kind = e["kind"]
            label = f"scenario {sc['key']}: {e.get('name') or kind + ' ' + e.get('field', '')}".rstrip()
            try:
                if kind in ("sql_zero", "sql_one", "sql_positive"):
                    n = one(fill(e["sql"]))
                    ok = (n == 0) if kind == "sql_zero" else (n == 1) if kind == "sql_one" else (n > 0)
                    check(label, ok, f"got {n}")
                elif kind == "weekday":
                    import datetime as _dt
                    d = _dt.date.fromisoformat(str(a[e["field"]])[:10])
                    check(label, d.strftime("%A") == e["weekday"], d.strftime("%A"))
                elif kind == "min":
                    check(label, float(a[e["field"]]) >= e["min"], str(a[e["field"]]))
                elif kind == "before_as_of":
                    check(label, a.get(e["field"]) is not None and str(a[e["field"]])[:10] <= as_of, str(a.get(e["field"])))
                elif kind == "document_contains":
                    must = [fill(m) for m in e.get("must", [])]
                    must_not = [fill(m) for m in e.get("must_not", [])]
                    missing = [m for m in must if doc_text is None or m not in doc_text]
                    present = [m for m in must_not if doc_text and m in doc_text]
                    check(label, not missing and not present, f"missing {missing} unexpected {present}")
                else:
                    check(label, False, f"unknown expectation kind {kind}")
            except Exception as ex:
                check(label, False, f"error: {ex}")

    # --- domain checks (Python)
    dom_checks = domain.hook("run_checks")
    if dom_checks:
        report["summaries"].update(dom_checks(con, manifest, check, q, one) or {})

    with open(os.path.join(out, "verification.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n{len(report['checks']) - len(failures)}/{len(report['checks'])} checks passed")
    if failures:
        print("FAILED:", failures)
    return failures, report
