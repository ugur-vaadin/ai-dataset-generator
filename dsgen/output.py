"""Generic writers: CSV per table (column order = spec order), optional INSERT script, checksums."""
from __future__ import annotations

import csv
import hashlib
import os


import datetime as _dt
import re as _re


def format_value(v, ddl_type: str):
    """CSV text for a value: strings pass through; Python values are formatted by the column's SQL type."""
    if v is None or v == "":
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, _dt.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, _dt.date):
        return v.isoformat()
    t = ddl_type.upper()
    m = _re.match(r"DECIMAL\(\d+,(\d+)\)", t)
    if m and isinstance(v, (int, float)):
        return f"{float(v):.{int(m.group(1))}f}"
    if t.startswith(("INT", "BIGINT", "SMALLINT")) and isinstance(v, float):
        return str(int(round(v)))
    return str(v)


def write_csv(ctx, spec, out):
    counts = {}
    for t in spec.tables:
        cols = spec.entity(t).columns
        names = [c.name for c in cols]
        types = {c.name: c.type for c in cols}
        rows = ctx.tables[t]
        with open(os.path.join(out, "csv", f"{t}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=names, extrasaction="ignore", lineterminator="\n")
            w.writeheader()
            for r in rows:
                w.writerow({k: format_value(r.get(k), types[k]) for k in names})
        counts[t] = len(rows)
    return counts


def write_sql_inserts(ctx, spec, out):
    def lit(v):
        if v is None or v == "":
            return "NULL"
        if isinstance(v, (int, float)):
            return str(v)
        s = str(v)
        if s in ("true", "false"):
            return s.upper()
        return "'" + s.replace("'", "''") + "'"
    with open(os.path.join(out, "sql", "data.sql"), "w", encoding="utf-8") as f:
        for t in spec.tables:
            names = spec.column_names(t)
            for r in ctx.tables[t]:
                f.write(f"INSERT INTO {t} ({', '.join(names)}) VALUES ({', '.join(lit(r.get(k)) for k in names)});\n")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
