---
name: author-domain
description: Author or extend a dsgen domain pack (a demo dataset for a Vaadin AI business case) from a business-case description — interview, write the pack files, validate, generate with checks, iterate until green, report FACTS.md. Use when asked to create a dataset for a new domain/business case, add a scenario or entity to an existing pack, or make generated demo data for an app.
---

# Author a domain pack

You turn a business-case description into a validated, generated dataset with dsgen. Data first,
code last; the validator and the verifier are the referees, not your judgment.

## Procedure

1. **Read** `DOMAIN_GUIDE.md` and skim `domains/nordic_supply/` (the worked example: domain.toml,
   scenarios.toml, config.toml, lifecycle.py).
2. **Interview briefly** (only what the text does not say): company and country; the three
   personas and what each looks at; the flow (entity A → B → C); the two or three demo moments;
   "today" for the demo. Propose defaults rather than asking open questions.
3. **Scaffold**: `python3 -m dsgen <name> new-domain --company "..." --description "..."`.
4. **Entities**: replace the examples in `domain.toml`. For every entity: description, columns with
   types, `pk`, `ref`, `desc` with status vocabularies, `pii` tags; `exposed = false` for entities
   holding people. Referenced entities first. Run `validate` after each entity.
5. **Pools**: write `pools/*.toml` in the domain's culture; no real brands or people.
6. **Flow**: write `flow.toml` — one `[entity.X]` per table in dependency order, a field expression per
   column (see the table in `DOMAIN_GUIDE.md`), age bands for statuses, bursts for story spikes, and the
   anchors. Run `validate` after every entity. Write Python (`lifecycle.py` with `STEPS`, or hooks) only for a
   mechanic the expressions cannot express, and say which one.
7. **Scenarios**: one `[[scenario]]` per demo moment with a document template, an image prompt if
   the demo needs one, and `expect` entries that pin the story (weekday, no record yet, document
   contains / does not contain).
8. **Checks**: `checks.toml` with chronology and consistency SQL; a smoke query per widget.
9. **Run** `python3 -m dsgen <name> check` and fix until `ALL CHECKS PASSED`. Then read
   `out/<name>/FACTS.md` and adjust volumes or anchors until the numbers tell the demo's story.
10. **Report**: the FACTS.md summary, the scenario table from `out/<name>/documents/INDEX.md`, the top of
    `REVIEW.md` (what a human should look at) and the `ESTIMATE.md` cost table.

## Rules

- Never call the API or the network from `lifecycle.py`; generation is deterministic and offline.
- Never edit `dsgen/` to make a pack work; if the framework lacks something, work around it in the pack
  and report the gap (issue or CHANGELOG note).
- Every column the model can see needs a `desc` unless the name says everything.
- Personal data goes where real systems have it and is tagged; free text may contain it on
  purpose, bounded by a check.
