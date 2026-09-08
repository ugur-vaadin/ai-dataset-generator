# ai-dataset-generator — deterministic demo datasets for Vaadin AI business-case apps

`dsgen` generates realistic, consistent, reproducible datasets for demo applications from a **domain pack**:
a handful of data files that describe a fictional company, its entities, its people, how records flow, and
the story the demo tells. The framework renders the rows, verifies them, loads them into H2 and PostgreSQL,
and writes the facts the demo script quotes. It never calls a language model: your coding assistant authors
the pack, code does the rest.

Three packs ship as worked examples: **Nordic Supply** (outdoor-equipment wholesaler; the three Vaadin AI
business cases — self-service dashboard, message-to-claim, supervised bulk change), **Fennoskandia Insurance**
(claims desk), and **Fjordhem Property Management** (service desk; authored from one paragraph in under four
minutes). The packs are the source of truth: fictional companies, entity specs, pools, templates and checks. A run
produces every table, document and database locally into `out/` (ignored by git). For the dataset the demo
application is built on, a published snapshot is committed under `datasets/nordic_supply/` (CSV, SQL, documents,
FACTS.md and a one-page `summary.html`; not the H2 file), produced only by `scripts/snapshot.sh` and checked for
staleness by `scripts/test.sh`. The summary page is served at
**https://ugur-vaadin.github.io/ai-dataset-generator/** (GitHub Pages, redeployed by `.github/workflows/pages.yml`
on every push that touches `datasets/`). Teams create their own packs with `new-domain`.

## Quick start

Read [docs/getting-started.md](docs/getting-started.md) for the full journey. Requirements: Python 3.11+, no
packages. Optional: `java` + an H2 jar for the H2 smoke test and database file, Docker for the PostgreSQL
test, an image key for real photos.

```bash
python3 -m dsgen doctor                              # what this machine can run; secrets are never printed
python3 -m dsgen nordic_supply check                 # generate out/nordic_supply, verify, H2 smoke test, FACTS.md (~6 s)
python3 -m dsgen nordic_supply check --pg --h2-file  # + PostgreSQL in Docker, + ready-to-use out/nordic_supply/db/nordic_supply.mv.db
python3 -m dsgen my_domain new-domain --company "…"  # scaffold a pack that already passes check
python3 -m dsgen my_domain validate                  # pack structure only
scripts/test.sh                                      # validate + check every pack; fails if datasets/ is stale
scripts/snapshot.sh nordic_supply                    # regenerate the committed snapshot in datasets/nordic_supply
```

Flags for `check`/`generate`: `--as-of` (the demo's "today"), `--seed`, `--scale`, `--months`, `--config`
(overlay the pack's `config.toml`), `--out`, `--csv-path-prefix`, `--images placeholder|openai|google`.
`estimate` predicts LLM/image cost by authoring mode; `review` prints the risk-scored review queue.

## Authoring a domain

Write your domain in a paragraph, scaffold a pack, and let your coding assistant fill it in following
[DOMAIN_GUIDE.md](DOMAIN_GUIDE.md); `validate` and `check` are the referees. You only paste the description of the
domain: `AGENTS.md` (imported by `CLAUDE.md`, pointed to by `GEMINI.md` and the Copilot instructions) carries the
whole procedure for any assistant; Claude Code users can also type `/author-domain`. A pack is mostly TOML:
`domain.toml` (entities, columns, what the model may see, personal-data tags), `flow.toml` (how rows and fields
are generated, story bursts, anchors), `config.toml`, `pools/`, `scenarios.toml`, `checks.toml`, and document
templates. Python is needed only for mechanics the flow language cannot express.

## What a run produces (`out/<domain>/`)

| Path | Content |
|---|---|
| `csv/*.csv` | One file per table; column order = DDL order; empty = NULL |
| `sql/schema-h2.sql`, `sql/schema-postgres.sql` | DDL per dialect, with column comments carrying descriptions and PII tags |
| `sql/load-h2.sql`, `sql/load-h2-classpath.sql`, `sql/load-postgres.sql` | Loaders: H2 `CSVREAD` (absolute paths / Spring classpath), psql `\copy` |
| `sql/readonly-user-h2.sql`, `sql/readonly-user-postgres.sql` | The `ai_reader` account: SELECT on exposed tables and views only |
| `sql/ai-schema-h2.txt`, `sql/ai-schema-postgres.txt` | What the model reads, per dialect, generated from the same spec as the DDL |
| `sql/pii-columns.json` | Column-level personal-data classification |
| `documents/` | Rendered messages, generated images with provenance, `INDEX.md` |
| `db/<domain>.mv.db` | Ready-to-use H2 database (with `--h2-file`) |
| `FACTS.md`, `REVIEW.md`, `ESTIMATE.md`, `manifest.json`, `verification.json` | The facts to present from; what to review; predicted cost; parameters, anchors, checksums; check results |

## Where to find what

| Question | Read |
|---|---|
| How do I run it, author a domain, review, hand over? | [docs/getting-started.md](docs/getting-started.md) |
| What exactly goes into a pack, and what does the validator enforce? | [DOMAIN_GUIDE.md](DOMAIN_GUIDE.md) |
| What must my coding assistant do? | [AGENTS.md](AGENTS.md) (imported by `CLAUDE.md`, pointed to by `GEMINI.md` and the Copilot instructions) |
| How does generation work, and who does what? | [docs/generation-model.md](docs/generation-model.md), with the workflow drawing |
| Why is it built this way? | [docs/design-decisions.md](docs/design-decisions.md) |
| How does the Vaadin application use the output? | [docs/integration-guide.md](docs/integration-guide.md) |
| Which image provider, at what cost? | [docs/image-providers.md](docs/image-providers.md) |
| What is in the Nordic Supply data, table by table, and what should each demo prompt find? | [domains/nordic_supply/docs/](domains/nordic_supply/docs/) and the generated `FACTS.md` in [datasets/nordic_supply/](datasets/nordic_supply/) |
| What changed? | [CHANGELOG.md](CHANGELOG.md) |

## Using it in an application

[docs/integration-guide.md](docs/integration-guide.md): two data sources (application and read-only AI user),
a `DatabaseProvider` returning the schema text plus today's date, saved widgets, claim-form lookups, the frozen
demo clock, price-change SQL, activity log.

## Layout

| Path | Content |
|---|---|
| `dsgen/` | Framework: spec, flow engine, schema and dialects, output, documents, verify, facts, smoke tests, validate, scaffold, review, estimate, CLI |
| `domains/<name>/` | Domain packs; `domains/_engine_smoke/` pins engine behaviour for `scripts/test.sh` |
| `datasets/<name>/` | Published snapshots of generated data (Nordic Supply today), with `README.md` and `summary.html` |
| `DOMAIN_GUIDE.md`, `AGENTS.md` (+ `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.claude/skills/`) | Authoring guide; the one instruction file for assistants and its per-tool pointers |
| `docs/` | Getting started, integration guide, generation model, design decisions and workflow diagram, image providers |
| `.env.example` | Environment variables (keys stay outside the repository) |

## Reproducibility

Same framework version + pack version + seed + as-of + scale + config → byte-identical files on the same
Python 3.x line. `manifest.json` records all of them plus Python version, platform and a SHA-256 per table.
Behaviour changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Notes

* All names, companies, brands, carriers, addresses and domains are fictional; `verify` checks them against a denylist of real Nordic and outdoor companies and `REVIEW.md` lists them for a human pass. No real customer data.
* Data is anchored to the pack's as-of date; regenerate before a demo or freeze the application clock.
* Generated images are kept in the pack and reused; only `--images <provider>` replaces them (and costs money).
