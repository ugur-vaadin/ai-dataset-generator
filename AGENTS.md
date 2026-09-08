# ai-demo-datasets — instructions for coding assistants

This repository generates deterministic demo datasets for Vaadin AI business-case applications.
`dsgen/` is the framework; `domains/<name>/` are domain packs (TOML data files; Python only for special mechanics).
The generator never calls an LLM. You, the assistant in this session, are the LLM: you author and
adjust packs; code renders, verifies and documents them.

This file is the single source of these instructions. `CLAUDE.md`, `GEMINI.md` and
`.github/copilot-instructions.md` only point here.

## When the user asks for a dataset

A request like "create a dataset for this domain: …", "author a dataset from the description in
`brief.md`", or "add a scenario to the insurance pack" means: run the procedure below without being told
the steps. The user provides only the domain description (text or a file). Do not ask them which files to
read, which commands to run, or how to verify; that is what this file is for.

**Pack name.** Derive it from the company or domain in the description: lowercase, words joined with
underscores, no country or legal suffix ("Fjordhem Property Management" → `property_maintenance` or
`fjordhem`, whichever reads better as a table prefix). State the name in your first reply. Ask only when
the description names no company and no domain.

**Procedure.**

1. Read `DOMAIN_GUIDE.md` (how a pack is built, the flow expression language, what the validator enforces)
   and skim `domains/nordic_supply/` as the worked example (`domains/property_maintenance/` is a small,
   purely declarative one).
2. Interview briefly, and only about what the description leaves open: the company and country, who the
   users are and what they look at, how records flow (entity A → B → C), the two or three demo moments,
   and "today" for the demo. Propose defaults instead of asking open questions; if the description
   covers these, do not ask at all.
3. Scaffold: `python3 -m dsgen <name> new-domain --company "…" --description "…"`. The result already
   passes `check`.
4. Entities in `domain.toml`, referenced tables first: description, columns with types, `pk`, `ref`, `desc`
   with the status vocabularies, `pii` tags; `exposed = false` for tables holding people. Run
   `python3 -m dsgen <name> validate` after each entity and fix what it reports before going on.
5. Pools in `pools/*.toml`, in the domain's culture; fictional brands and people only.
6. Flow in `flow.toml`: one `[entity.X]` per table in dependency order, a field expression per column, age
   bands for statuses, bursts for story spikes, anchors for the demo moments. Validate after every entity.
   Write Python (`lifecycle.py` with `STEPS`, or hooks) only for a mechanic the expressions cannot express,
   and say which one.
7. Scenarios in `scenarios.toml`: one `[[scenario]]` per demo moment with a document template under
   `documents/`, an image prompt if the demo needs a photo, and `expect` entries that pin the story
   (weekday, no record yet, document contains / does not contain).
8. Checks in `checks.toml`: chronology and consistency SQL, a smoke query per widget.
9. Run `python3 -m dsgen <name> check` and fix until it prints `ALL CHECKS PASSED`. Read
   `out/<name>/FACTS.md` and adjust volumes or anchors until the numbers tell the demo's story.
10. Report: the FACTS.md summary, the scenario table from `out/<name>/documents/INDEX.md`, the top of
    `REVIEW.md` (what a person should look at), and the cost table from `ESTIMATE.md`. If a scenario has an
    image, say that it is a placeholder and give the command that generates it and its estimated cost.

Read before other work on the framework: `docs/generation-model.md` (the process on one page).

## Commands (Python 3.11+, no packages)

- `python3 -m dsgen doctor` — environment check (Python, Java/H2, Docker, image keys) without printing secrets.
- `python3 -m dsgen <domain> validate` — pack structure and expressions; run after every edit to a pack.
- `python3 -m dsgen <domain> check` — generate, verify, H2 smoke test, FACTS/REVIEW/ESTIMATE. Add `--pg` (Docker), `--h2-file`.
- `python3 -m dsgen <name> new-domain --company "..." --description "..."` — scaffold a pack that already passes.
- `scripts/test.sh` — validate + check every pack (including the hidden `_engine_smoke` pack that pins engine features).
- `scripts/snapshot.sh <name>` — publish a pack's generated data into `datasets/<name>/`.

## Rules

- Never run a command that costs money on your own: `--images openai|google` calls a paid API. Tell the user the
  command and the estimate from `ESTIMATE.md`; they run it. Generated images are then kept across runs.
- Never edit `dsgen/` to make one pack work; work around the gap in the pack and report it (issue or CHANGELOG note).
- Never put API keys in files under this repository; they come from the environment (see `.env.example`).
- Never call the API or the network from `lifecycle.py`; generation is deterministic and offline.
- Everything domain-specific is data in the pack; Python holds only mechanics the flow language lacks.
- Every column the model can see needs a `desc` unless the name says everything. Personal data goes where real
  systems have it and is tagged; free text may contain it on purpose, bounded by a check.
- Keep `CHANGELOG.md` and the pack's `README.md` current when you change behaviour.
- `datasets/<name>/` is a published build of a pack. Never edit it by hand; after changing a pack that has one, run
  `scripts/snapshot.sh <name>` (`scripts/test.sh` fails while it is stale).
