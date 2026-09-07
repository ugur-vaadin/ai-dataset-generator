# Fjordhem Property Management domain pack

Authored declaratively (no generation code) from a one-paragraph brief in 3 min 43 s to the first green check. It
frames the AI business cases on a property manager's service desk: tenants report faults, dispatchers create work
orders for contractors.

* Case 2 (message to work order): `documents/emails/01-ceiling-leak.eml` — a tenant's e-mail with no unit or building
  code; the sender resolves to tenant → unit → building; no fault report exists yet.
* Case 1 (dashboard): a cold week triples heating faults; one plumbing contractor is slow; overdue work orders by building.
* Case 3 candidates: reassign the slow contractor's open plumbing work orders; raise the priority of heating faults in one building.

```bash
python3 -m dsgen property_maintenance check --pg --h2-file
```
