# Changelog

Framework (`dsgen`) and domain packs are versioned separately: `dsgen.VERSION` and `[domain].version`
in each `domain.toml`; both are written to `manifest.json`.

## dsgen 2.3.1 · property_maintenance 0.1.0 — 2026-09-07

* Third domain pack `property_maintenance` (Fjordhem), authored from a one-paragraph brief in 3 min 43 s to first green.
* Engine fixes found while authoring: config counts may be range strings (`"18..35"`); `->` references chain across any number of hops;
  null anchor fields render as empty text in documents and never satisfy `document_contains` (previously matched the text "None").

## dsgen 2.3.0 · insurance_claims 0.2.1 — 2026-09-07

* Flow engine closes the business-case audit gaps: `pick:` from generated tables (where / weighted by), `pareto:` `expo:` `normal:`,
  `[dates]` named dates and `seasonality` + `pick_weight` on per-day entities, `[entity.X.after]` aggregates (`sum count max min avg`),
  sibling references (`prev.`, `seq_in_parent`, `sibling_count`), anchor `ensure` (pick or create with children), template filters
  `ean13` `title` `padN`, `{field}` placeholders in date offsets, `//` `%` `**` in calc.
* INT columns format floats as integers; validator understands the new kinds, `after` blocks, `dates`, `seasonality`, `ensure`.
* Hidden `domains/_engine_smoke/` pack (35 checks) exercises every feature; `scripts/test.sh` runs all packs.
* insurance_claims 0.2.1 uses `pick` for repair shops, named storm dates and monthly seasonality.

## dsgen 2.2.0 · insurance_claims 0.2.0 — 2026-09-07

* Declarative flow engine (`dsgen/flow.py`): `flow.toml` describes counts (absolute, per parent, per day), field expressions
  (constants, copy, key, template, pools, numbers, dates and timestamps with clamps, status bands, calc, nested if), bursts,
  variants, drop rules and anchors. The framework generates tables from it; `lifecycle.py` becomes optional (hooks) or a full
  Python implementation for special mechanics.
* Typed CSV formatting (decimals, dates, booleans) from the column types; validator checks flow files (entities, fields,
  expression kinds, pools paths, bands, order); scaffold produces a declarative pack.
* insurance_claims 0.2.0 re-expressed in `flow.toml` (no generation code); pools restructured (cities/postal codes, patterns, weights).

## dsgen 2.1.2 — 2026-09-07

* Generated images persist in the domain pack (`documents/generated/`) and are restored into `out/` on every run.
* Getting-started video produced from real command output (pipeline kept outside the repository).

## dsgen 2.1.1 — 2026-09-07

* OpenAI image provider: defaults `gpt-image-1.5` / `medium` / 1024×1024 (env overrides), `output_format` matching the file extension, usage tokens and terms note in provenance; first live image generated.
* Generated images are kept across runs that do not request a provider (`status: kept`); price table gained per-quality OpenAI entries.

## dsgen 2.1.0 · nordic_supply 1.2.1 · insurance_claims 0.1.1 — 2026-09-07

* Cost instrumentation: `llm-usage.jsonl` per run, `dsgen/prices.toml`, `estimate` command and `ESTIMATE.md` (cost by authoring mode × model from measured `text_asset` columns and documents).
* Review: `REVIEW.md` + `review-queue.json` with risk scores and stable ids; `review/overrides.toml` (approve / reject / replace) applied before writing; `language` on scenarios.
* Shared flow helpers in `dsgen.model`: `status_by_age`, `last_weekday_before`, `next_weekday_after`, `clamp_to_day`.
* Nordic Supply 1.2.1: `text_asset` tags, sample overrides (one template replacement). Insurance 0.1.1: `text_asset` tags, uses the shared helpers, scenario doc.

## dsgen 2.0.0 · nordic_supply 1.2.0 · insurance_claims 0.1.0 — 2026-09-07

* Framework/domain split: `dsgen/` + `domains/<name>/` packs (domain.toml, config.toml, pools/, scenarios.toml, checks.toml, documents/, lifecycle.py).
* `validate`, `new-domain` scaffold, `DOMAIN_GUIDE.md`, Claude Code skill `author-domain`.
* PostgreSQL dialect (DDL, `\copy` loader, role, model text) and Docker smoke test (`--pg`); H2 database file (`--h2-file`).
* Per-dialect model-facing schema text; DDL column comments with descriptions and PII tags; `pii-columns.json`.
* Nordic Supply 1.2.0: consent/retention on contacts, bounded personal data in free text, `{TEXT}` placeholder types.
* Declarative scenarios with generic expectations; e-mails as templates; image generation step (openai/google/placeholder) with provenance.
* Second domain pack `insurance_claims` (Fennoskandia Insurance).
* Output moves to `out/<domain>/`; `schema.sql` → `schema-h2.sql` / `schema-postgres.sql`; `ai-schema.txt` → `ai-schema-h2.txt` / `-postgres.txt`.

## 1.1.1 — 2026-09-07

* `manifest.json` records a SHA-256 per CSV file, so an unintended change in generated content shows in a diff.
* Documentation aligned with the package structure (decisions D2, D8).

## 1.1.0 — 2026-09-07

* Generator split into a package with thin entry points (since replaced by `python3 -m dsgen`).
* Story tunables moved to `config/default.toml` (`--config` overlays it).
* Model-facing schema text is generated from the column spec plus a descriptions map; the verifier fails on undocumented columns.
* `products` gained `ean` (valid EAN-13), `description`, `min_order_qty`.
* Inventory is generated after orders: backordered products have no free stock in the shipping warehouse and a `next_inbound_date`.
* `--check` runs verification, an H2 smoke test (DDL, loader, read-only user, widget queries) and renders `out/FACTS.md`.
* `sql/readonly-user-h2.sql`: the `ai_reader` account with SELECT on exposed tables and views only.
* `load-h2.sql` uses absolute CSV paths (`--csv-path-prefix` to override).
* `manifest.json` records Python version, platform and config path.
* Verifier: NOT NULL, EAN, unit-price, cancelled-order, inventory and e-mail-content checks added.

## 1.0.0 — 2026-09-07

* First complete dataset: 19 tables, three scenario anchors, six e-mails, 121 checks, H2 load verified by hand.
