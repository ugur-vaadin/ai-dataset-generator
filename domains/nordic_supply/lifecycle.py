"""Nordic Supply — the domain's Python: context, generation steps, documents and hooks for the
framework (schema context, manifest extras, checks, facts). Everything else is data in this folder."""
from __future__ import annotations

from dsgen.model import iso

from .gen.anchors import gen_case2_anchors
from .gen.catalogue import (gen_categories, gen_inventory, gen_price_history, gen_products, gen_promotions,
                            gen_suppliers, gen_users, gen_warehouses)
from .gen.claims import gen_claims
from .gen.ctx import Ctx
from .gen.customers import gen_customers
from .gen.documents import document_context, gen_saved_widgets
from .gen.orders import gen_orders, outage_window
from . import checks as _checks, facts as _facts

# inventory comes after orders so stock agrees with the backorders
STEPS = [gen_users, gen_warehouses, gen_categories, gen_suppliers, gen_products, gen_price_history, gen_promotions,
         gen_customers, gen_orders, gen_case2_anchors, gen_claims, gen_inventory, gen_saved_widgets]


def make_ctx(rng, as_of, scale, months) -> Ctx:
    return Ctx(rng=rng, as_of=as_of, scale=scale, months=months)


def schema_context(ctx) -> str:
    """Dynamic part of the model-facing hints (fills {context} in domain.toml [ai_schema].hints)."""
    o = outage_window(ctx)
    return (f"- Context: the Göteborg warehouse (GOT) had a systems outage {iso(o[0])} to {iso(o[1])}. Dispatches planned\n"
            "  for that week left 3-6 days late, so the late shipments show up mostly in the following week. Baltic Freight Line\n"
            "  has had transit delays since last month.")


def manifest_extra(ctx) -> dict:
    o = outage_window(ctx)
    return {"goteborg_outage_window": [iso(o[0]), iso(o[1])]}


document_context = document_context
run_checks = _checks.run
facts_sections = _facts.sections
