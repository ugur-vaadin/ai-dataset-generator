"""Loads a domain pack: domains/<name>/ with domain.toml, config.toml, pools/, scenarios.toml,
checks.toml and lifecycle.py (the domain's Python: context, steps, documents, hooks)."""
from __future__ import annotations

import importlib
import os
import tomllib
from dataclasses import dataclass, field

from .spec import DomainSpec, load_spec

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMAINS_DIR = os.path.join(ROOT, "domains")


@dataclass
class Domain:
    name: str
    path: str
    spec: DomainSpec
    config_path: str
    scenarios: dict = field(default_factory=dict)
    checks: dict = field(default_factory=dict)
    lifecycle: object = None
    flow: dict = None          # flow.toml, when the domain is declarative
    pools: dict = None

    def hook(self, name, default=None):
        return getattr(self.lifecycle, name, default)


def list_domains():
    return sorted(d for d in os.listdir(DOMAINS_DIR) if os.path.isfile(os.path.join(DOMAINS_DIR, d, "domain.toml")) and not d.startswith("_"))


def load_domain(name: str) -> Domain:
    path = os.path.join(DOMAINS_DIR, name)
    if not os.path.isdir(path):
        raise SystemExit(f"unknown domain '{name}'. Available: {', '.join(list_domains())}")
    spec = load_spec(os.path.join(path, "domain.toml"))
    dom = Domain(name=name, path=path, spec=spec, config_path=os.path.join(path, "config.toml"))
    for attr, fn in (("scenarios", "scenarios.toml"), ("checks", "checks.toml")):
        p = os.path.join(path, fn)
        if os.path.exists(p):
            with open(p, "rb") as f:
                setattr(dom, attr, tomllib.load(f))
    if os.path.exists(os.path.join(path, "flow.toml")):
        from .flow import load_flow
        dom.flow, dom.pools = load_flow(path)
    if os.path.exists(os.path.join(path, "lifecycle.py")):
        dom.lifecycle = importlib.import_module(f"domains.{name}.lifecycle")
    elif dom.flow is None:
        raise SystemExit(f"domain '{name}' has neither flow.toml nor lifecycle.py")
    return dom
