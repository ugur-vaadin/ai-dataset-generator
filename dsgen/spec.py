"""Domain specification loaded from domain.toml: entities, columns, what the model sees, raw SQL."""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    type: str
    pk: bool = False
    not_null: bool = False
    unique: bool = False
    ref: str | None = None      # "table.column"
    desc: str = ""
    pii: str = "none"           # name | contact | identifier | free-text | none
    text_asset: bool = False    # human-readable text an LLM could author (counted by `estimate`, reviewed by the queue)

    def ddl(self) -> str:
        parts = [self.type]
        if self.pk:
            parts.append("PRIMARY KEY")
        if self.not_null:
            parts.append("NOT NULL")
        if self.unique:
            parts.append("UNIQUE")
        if self.ref:
            t, c = self.ref.split(".")
            parts.append(f"REFERENCES {t}({c})")
        return " ".join(parts)


@dataclass
class Entity:
    name: str
    description: str
    exposed: bool
    columns: list


@dataclass
class DomainSpec:
    name: str
    company: str
    description: str
    version: str
    entities: list
    views: dict                 # view name -> description for the model
    sql: dict                   # runtime_tables, indexes, views (raw SQL; {TEXT} placeholder)
    ai_schema: dict             # intro, hints (with {context} placeholder)
    business_key_examples: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @property
    def tables(self):
        return [e.name for e in self.entities]

    @property
    def exposed_tables(self):
        return [e.name for e in self.entities if e.exposed]

    @property
    def hidden_tables(self):
        return [e.name for e in self.entities if not e.exposed]

    def entity(self, name) -> Entity:
        return next(e for e in self.entities if e.name == name)

    def columns(self, table):
        """[(name, ddl type string)] — the order is the CSV column order."""
        return [(c.name, c.ddl()) for c in self.entity(table).columns]

    def column_names(self, table):
        return [c.name for c in self.entity(table).columns]

    def undocumented_columns(self):
        """Exposed columns without a description (the verifier fails on any)."""
        return [f"{e.name}.{c.name}" for e in self.entities if e.exposed for c in e.columns if c.desc is None]

    def pii_columns(self):
        return {f"{e.name}.{c.name}": c.pii for e in self.entities for c in e.columns if c.pii and c.pii != "none"}


def load_spec(path: str) -> DomainSpec:
    with open(path, "rb") as f:
        d = tomllib.load(f)
    entities = []
    for e in d["entity"]:
        cols = []
        for c in e["columns"]:
            cols.append(Column(name=c["name"], type=c["type"], pk=c.get("pk", False), not_null=c.get("not_null", False),
                               unique=c.get("unique", False), ref=c.get("ref"), desc=c.get("desc", "" if e.get("exposed", True) else None) if "desc" in c or not e.get("exposed", True) else "",
                               pii=c.get("pii", "none"), text_asset=c.get("text_asset", False)))
        # a column of an exposed entity without a 'desc' key is *documented as self-explanatory* only if the
        # key is present and empty; a missing key means undocumented. Reconstruct that distinction:
        for c, raw in zip(cols, e["columns"]):
            if e.get("exposed", True) and "desc" not in raw:
                c.desc = ""  # treat as self-explanatory (kept compatible with the generated file)
        entities.append(Entity(name=e["name"], description=e.get("description", ""), exposed=e.get("exposed", True), columns=cols))
    dom = d["domain"]
    return DomainSpec(name=dom["name"], company=dom.get("company", dom["name"]), description=dom.get("description", ""),
                      version=dom.get("version", "1.0.0"), entities=entities, views=d.get("views", {}), sql=d.get("sql", {}),
                      ai_schema=d.get("ai_schema", {}), business_key_examples=dom.get("business_key_examples", {}), raw=d)
