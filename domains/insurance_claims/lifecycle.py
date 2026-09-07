"""Fennoskandia Insurance — reporting hooks only. Generation is declarative (flow.toml)."""
from __future__ import annotations

from dsgen.model import cfg


def schema_context(ctx) -> str:
    a = ctx.anchors["demo"]["P2_storm_week"]
    return f"- Context: a storm hit southern Finland and Sweden {a['storm_start']} to {a['storm_end']}; STORM incidents spiked and roofing repairs are queued."


def manifest_extra(ctx) -> dict:
    a = ctx.anchors["demo"]["P2_storm_week"]
    return {"storm_window": [a["storm_start"], a["storm_end"]]}


def facts_sections(m, v) -> str:
    s = v["summaries"]
    L = ["## Dashboard story\n", f"Storm window: {m['domain_anchors']['storm_window'][0]} to {m['domain_anchors']['storm_window'][1]}.\n"]
    if "claim_status" in s:
        L.append("Claims by status: " + ", ".join(f"{k} {n}" for k, n in s["claim_status"].items()))
        L.append("\nIncidents by type: " + ", ".join(f"{k} {n}" for k, n in s["incident_type"].items()))
        L.append(f"\nClaims open over 14 days: **{s['open_over_14d']}**. Average days to payment by shop: " + ", ".join(f"{k} {d}" for k, d in s["days_to_payment_by_shop"].items()))
    a = m["anchors"]["demo"]["P1_parking_damage"]
    L.append(f"\n## Message to claim\n\nE-mail from {a['holder']} about {a['vehicle_reg']} (policy {a['policy_number']}, deductible {a['deductible']} EUR), damage on Tuesday {a['tuesday']}; no incident or claim exists yet.")
    return "\n".join(L)


def run_checks(con, manifest, check, q, one):
    as_of = manifest["as_of"]
    open14 = one("SELECT COUNT(*) FROM claims WHERE status NOT IN ('PAID','REJECTED','CLOSED') AND julianday(?) - julianday(opened_at) > 14", as_of)
    check("dashboard: claims open over 14 days exist", open14 > 5, str(open14))
    shops = q("SELECT r.name, ROUND(AVG(julianday(p.paid_at) - julianday(c.opened_at)), 1) FROM claim_payments p JOIN claims c ON c.id = p.claim_id JOIN repair_shops r ON r.id = p.repair_shop_id GROUP BY r.name ORDER BY 2 DESC")
    check("dashboard: the slow repair shop is the slowest to be paid", bool(shops) and shops[0][0] == cfg("rates", "slow_shop"), str(shops[:2]))
    return {"claim_status": dict(q("SELECT status, COUNT(*) FROM claims GROUP BY status ORDER BY 2 DESC")),
            "incident_type": dict(q("SELECT incident_type, COUNT(*) FROM incidents GROUP BY incident_type ORDER BY 2 DESC")),
            "open_over_14d": open14, "days_to_payment_by_shop": dict(shops)}
