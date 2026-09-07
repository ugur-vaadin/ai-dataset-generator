"""Everything that describes the database, generated from the domain spec for every dialect: DDL
(with column comments carrying the model descriptions and PII tags), loaders, read-only account,
PII column list, and the model-facing schema text. One source of truth, so nothing can drift."""
from __future__ import annotations

import json
import os

from . import VERSION
from .dialects import DIALECTS, Dialect


def write_schema_sql(spec, out, dialect: Dialect):
    lines = dialect.ddl_header(spec.company, VERSION)
    for t in spec.tables:
        lines.append(f"CREATE TABLE {t} (")
        lines.append(",\n".join(f"    {n} {typ.replace('{TEXT}', dialect.text_type)}" for n, typ in spec.columns(t)))
        lines.append(");")
        comments = []
        for c in spec.entity(t).columns:
            text = c.desc or ""
            if c.pii != "none":
                text = (text + " " if text else "") + f"[pii:{c.pii}]"
            if text:
                comments.append(dialect.column_comment(t, c.name, text))
        lines.extend(comments)
        lines.append("")
    for key in ("runtime_tables", "indexes", "views"):
        if spec.sql.get(key):
            lines.append(spec.sql[key].replace("{TEXT}", dialect.text_type))
    with open(os.path.join(out, "sql", f"schema-{dialect.name}.sql"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def write_loaders(spec, out, csv_prefix, dialect: Dialect):
    with open(os.path.join(out, "sql", f"load-{dialect.name}.sql"), "w", encoding="utf-8") as f:
        f.write(dialect.loader(spec, csv_prefix))
    cp = dialect.classpath_loader(spec)
    if cp:
        with open(os.path.join(out, "sql", f"load-{dialect.name}-classpath.sql"), "w", encoding="utf-8") as f:
            f.write(cp)


def write_readonly_user(spec, out, dialect: Dialect):
    with open(os.path.join(out, "sql", f"readonly-user-{dialect.name}.sql"), "w", encoding="utf-8") as f:
        f.write(dialect.readonly_user(spec, list(spec.views)))


def write_pii_json(spec, out):
    """Column-level personal-data classification for the application's masking rules and for auditors."""
    data = {"classes": {"name": "a person's name", "contact": "e-mail address or phone number of a person",
                        "identifier": "a value that identifies or describes a person indirectly",
                        "free-text": "free text that may contain personal data written by people"},
            "columns": spec.pii_columns(),
            "hidden_from_ai": spec.hidden_tables,
            "exposed_to_ai": spec.exposed_tables}
    with open(os.path.join(out, "sql", "pii-columns.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def write_all_sql(spec, out, csv_prefix):
    for d in DIALECTS.values():
        write_schema_sql(spec, out, d)
        write_loaders(spec, out, csv_prefix, d)
        write_readonly_user(spec, out, d)
    write_pii_json(spec, out)


def ai_schema_text(spec, dialect: Dialect, context: str = "") -> str:
    """The text DatabaseProvider.getSchema() returns for one dialect: intro, every exposed table with all
    columns and the meaning of non-obvious ones, the views, the hints (dialect idioms + domain context)."""
    dl = spec.ai_schema.get("dialects", {}).get(dialect.name, {})
    intro = spec.ai_schema.get("intro", "").replace("{dialect}", dl.get("label", dialect.label))
    parts = [intro]
    for e in spec.entities:
        if not e.exposed:
            continue
        parts.append(f"{e.name}({', '.join(c.name for c in e.columns)})\n  {e.description}")
        parts.extend(f"  - {c.name}: {c.desc}" for c in e.columns if c.desc)
        parts.append("")
    if spec.views:
        parts.append("VIEWS")
        for v, desc in spec.views.items():
            parts.append(f"{v} {desc}")
    hints = spec.ai_schema.get("hints", "").replace("{dialect_hints}", dl.get("hints", "")).replace("{context}", context)
    parts.append(hints)
    return "\n".join(parts).rstrip() + "\n"


def write_ai_schema_texts(spec, out, context):
    for d in DIALECTS.values():
        with open(os.path.join(out, "sql", f"ai-schema-{d.name}.txt"), "w", encoding="utf-8") as f:
            f.write(ai_schema_text(spec, d, context))
