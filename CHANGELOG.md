# Changelog

Framework (`dsgen`) and domain packs are versioned separately: `dsgen.VERSION` and `[domain].version`
in each `domain.toml`; both are written to `manifest.json`.

## dsgen 2.4.0 / nordic_supply 1.3.0 — 2026-09-08

Response to the independent audit (AUDIT.md) and to a reviewer's list of company names too close to real ones.

Framework:
* `verify` checks every company-like name in the pools and the data against a denylist of real Nordic and outdoor brands,
  retailers and carriers (`dsgen/names.py`; packs extend it with `[names] deny` / `allow`), and flags generic shop words next
  to a real town. `REVIEW.md` ends with a name inventory by source for a person to scan. Rule added to `AGENTS.md`.
* `scripts/test.sh` runs every pack for three more as-of dates (first working day, month end, a Monday the 1st) so the
  "move the demo in time" promise is tested. A GitHub Actions workflow runs the suite on Python 3.11 and 3.13.
* `contact` e-mail addresses are unique per pack rule (`unique = true`), enforced by the generic check.

Nordic Supply data:
* All chains, several suppliers and model words, and every carrier renamed to invented names (Halti, Retkiaitta, Trailhead,
  Boreal, Granit, Kompass, Lofoten, Abisko, Vidda and the real carriers are gone). E-mail templates now have neutral file names.
* Regeneration works for any as-of date: anchor A4 is placed relative to today; the case 3 promotion windows are clamped and
  the checks derive the expected counts from the constructed layout instead of the literals 22/21.
* No order line after a product's discontinued date; delay events precede delivery, attempts follow dispatch, damage reports
  follow delivery (six new chronology checks); contact e-mails unique; users exist before the price rows they signed;
  anchor quantities are multiples of the case pack.
* `docs/data-model.md`, `docs/demo-scenarios.md` and the generated pallet photo are now in the repository.

## docs — 2026-09-08

* `docs/design-decisions.md` records every design decision with its rationale and alternatives, plus the end-to-end workflow as `docs/workflow.svg`.
* `AGENTS.md` is now the single instruction file for every assistant and carries the whole authoring procedure: the
  user only pastes a domain description; the assistant derives the pack name, reads the guide and example, validates
  after every edit, checks until green, reports, and never runs paid image generation on its own. `CLAUDE.md` imports
  it; `GEMINI.md` and `.github/copilot-instructions.md` point to it; the Claude Code skill is a thin trigger.
* Getting-started, README and the quickstart video (scenes 3 and 4) use the short request instead of the long instruction.
* Video build re-synthesises only narration paragraphs whose text changed.

## dsgen 2.3.2 — 2026-09-07

* `scripts/snapshot.sh <domain>` publishes a generated dataset into `datasets/<domain>/` (CSV, SQL, documents, FACTS, REVIEW, manifest, verification) with a generated `README.md`; the H2 file and per-run cost/queue/usage files are git-ignored there.
* `scripts/test.sh` fails when a committed snapshot's per-table SHA-256 no longer matches what the pack generates.
* The H2 smoke test and `--h2-file` load through a copy of `load-h2.sql` with the CSV path made absolute, so a loader written with a relative `--csv-path-prefix` (as in snapshots) still runs. `generate --h2-file` now builds the file too (before, only `check` honoured the flag).
* First snapshot: `datasets/nordic_supply/`, with `summary.html`, a one-page overview of the data behind the three business cases.
* GitHub Pages workflow publishes every snapshot's `summary.html` (Nordic Supply as the site root).

## nordic_supply 1.2.2 — 2026-09-07

Final data pass for the three business cases; every fact in the six customer messages is now cross-checked against the records.

* E-mail 02 counted cartons of six but the boots' `case_pack` was 1; the anchor now picks (or sets) a six-pack SKU and the template takes the carton numbers from the anchor.
* E-mail 03 named a colour that did not exist as a product; the received colour is now a real SKU with price history (inventory follows), recorded in the anchor as `received_sku`.
* E-mail 06 named a fixed promotion; it now names the promotion that actually covered the order date.
* Four new checks pin these facts, plus one for the spread of customers behind the document's case 1 example query.
* FACTS.md gains the case 1 example "orders shipped after the promised date last month, by customer" (totals and top ten).
* All six messages and anchors reviewed and approved in `review/overrides.toml`.

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
