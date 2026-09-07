"""Generation context for Nordic Supply: the framework's BaseCtx plus the in-memory indexes the
generators share (products by category, prices, promotions, customers, contacts, addresses)."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from dsgen.model import BaseCtx


@dataclass
class Ctx(BaseCtx):
    products: list = field(default_factory=list)
    products_by_cat: dict = field(default_factory=lambda: defaultdict(list))
    price_at: dict = field(default_factory=dict)      # product_id -> sorted [(valid_from, price)]
    promos_by_product: dict = field(default_factory=lambda: defaultdict(list))
    customers: list = field(default_factory=list)
    contacts_by_customer: dict = field(default_factory=lambda: defaultdict(list))
    addresses_by_customer: dict = field(default_factory=lambda: defaultdict(list))
    users_by_role: dict = field(default_factory=lambda: defaultdict(list))
