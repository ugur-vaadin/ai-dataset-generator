"""Fjordhem — reporting hooks only; generation is declarative (flow.toml)."""
from __future__ import annotations


def schema_context(ctx):
    a = ctx.anchors["demo"]["D1_cold_snap"]
    return f"- Context: a cold week {a['cold_start']} to {a['cold_end']} tripled heating faults; {a['slow_contractor']} has been slow to start jobs since."


def manifest_extra(ctx):
    a = ctx.anchors["demo"]["D1_cold_snap"]
    return {"cold_week": [a["cold_start"], a["cold_end"]]}


def facts_sections(m, v):
    s = v["summaries"]
    a = m["anchors"]["demo"]["T1_ceiling_leak"]
    L = ["## Dashboard story\n", f"Cold week: {m['domain_anchors']['cold_week'][0]} to {m['domain_anchors']['cold_week'][1]}.\n"]
    if "wo_status" in s:
        L.append("Work orders by status: " + ", ".join(f"{k} {n}" for k, n in s["wo_status"].items()))
        L.append(f"\nOverdue open work orders: **{s['overdue']}**. Average hours to start by contractor: " + ", ".join(f"{k} {h}" for k, h in s["hours_to_start"].items()))
    L.append(f"\n## Message to work order\n\nE-mail from {a['tenant']} (unit {a['unit_number']}, {a['building']}, {a['city']}) about a ceiling leak since Tuesday {a['tuesday']}; no fault report exists yet.")
    return "\n".join(L)


def run_checks(con, manifest, check, q, one):
    overdue = one("SELECT COUNT(*) FROM work_orders WHERE status NOT IN ('DONE','CANCELLED') AND due_at < ?", manifest["as_of"] + " 12:00:00")
    check("dashboard: overdue open work orders exist", overdue > 5, str(overdue))
    return {"wo_status": dict(q("SELECT status, COUNT(*) FROM work_orders GROUP BY status ORDER BY 2 DESC")), "overdue": overdue,
            "hours_to_start": dict(q("SELECT c.name, ROUND(AVG((julianday(e.event_time) - julianday(w.created_at)) * 24), 1) FROM work_order_events e JOIN work_orders w ON w.id = e.work_order_id JOIN contractors c ON c.id = w.contractor_id WHERE e.event_type = 'STARTED' GROUP BY c.name ORDER BY 2 DESC"))}
