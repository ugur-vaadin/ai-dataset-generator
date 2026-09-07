# Authoring a domain pack

A *domain pack* is everything dsgen needs to generate a demo dataset for one business case:
what the world looks like (entities, vocabularies, rules), who is in it (name pools), what
story the demo tells (scenarios), and how records flow through their life (one small Python
module). Everything except the flow is data a human can read and edit. This guide is written
for a Claude Code session as much as for a person; `python3 -m dsgen <name> validate` is the
referee.

## Layout

```
domains/<name>/
  domain.toml        entities and columns (types, keys, descriptions the model reads, PII tags), views, raw SQL, model-facing intro/hints
  config.toml        story tunables: as-of date, seed, scale, volumes, rates
  pools/*.toml       name pools, templates, vocabularies
  scenarios.toml     demo anchors: the document rendered for each, the image prompt, what the verifier must find
  checks.toml        SQL checks that must hold (SQLite), smoke queries run on the real database as the AI user
  documents/         text templates (*.tmpl) with {placeholders}
  flow.toml          how rows and fields are generated, and the anchors (declarative; no code)
  lifecycle.py       optional Python: reporting hooks, or a full STEPS implementation for mechanics the flow cannot express
  checks.py, facts.py   optional Python checks and FACTS.md sections
```

Start from `python3 -m dsgen <name> new-domain --company "..." --description "..."`: it creates a
declarative pack (two entities, one anchor, one document) that validates and passes `check` immediately. Replace the example entities step by step;
keep it green after every step.

## Step 1 — from the business case to entities

Read the business-case text and answer, in the pack's `domain.toml`:

* **Who are the users of the application, and what do they look at?** Those are your exposed
  entities. Name them as the business does (`claims`, not `case_records`).
* **Who are the people in the data?** Customers, contacts, policyholders, employees. Put personal
  data in its own entity where real systems have it, tag columns with `pii = "name" | "contact" |
  "identifier" | "free-text"`, and set `exposed = false` on entities the AI must not read.
* **What flows?** Order → shipment → claim; policy → incident → claim → payment. Every flow needs
  timestamps in order and a status vocabulary. Write the vocabulary into the column `desc` — the
  model reads it.
* **What does the demo need to be true?** "Thousands of X so a combo box cannot hold them",
  "months of history so last month exists", "dated price history so a change can start next
  month". Those become volumes in `config.toml` and rules in `lifecycle.py`.

Rules for columns: snake_case; one `pk = true` per entity; `ref = "table.column"` for every
foreign key; referenced entities defined *before* the entities that reference them (loaders
insert in file order); `desc` on every column whose meaning is not obvious from its name; one of
`INT, BIGINT, VARCHAR(n), CHAR(n), DECIMAL(p,s), DATE, TIMESTAMP, BOOLEAN, {TEXT}`.

## Step 2 — the model-facing text

`[ai_schema].intro` and `.hints` are what `DatabaseProvider.getSchema()` returns. The table and
column lines are generated; you write the framing: what the company is, the definitions the
business uses ("a claim is OPEN when…"), join keys, units, and the dynamic `{context}` the
lifecycle fills (an outage week, a storm). Keep dialect idioms in `[ai_schema.dialects.*]`.

## Step 3 — pools

Name pools in the culture of the domain (Nordic, German, whatever the demo is). Product or item
templates as `type × model × variant`. Vocabularies as lists with weights. Avoid real companies,
brands, and people; use `.example` e-mail domains. Lists must be non-empty; order matters for
reproducibility, so append rather than reorder.

## Step 4 — the flow (`flow.toml`)

Describe how many rows each entity has and how each field is produced; the framework generates the
tables in file order, keeps dates inside the as-of window, formats values by column type and builds
the anchors. No Python is needed for the common shapes. Three ways to say how many rows:

```toml
[entity.customers]
count = "cfg:volume.customers"                       # absolute; scaled by --scale (scale = false to pin)

[entity.orders]
per = { day = "history", count = "cfg:volume.orders_per_month / 30", pick = "customers", pick_where = "active == true" }

[entity.order_lines]
per = { parent = "orders", count = "1..6" }           # per parent row; share = 0.8 keeps 80% of parents; when = "COND" filters

[entity.adjusters]
rows_from = { pool = "adjusters.list", columns = ["username", "full_name", "role"] }   # literal rows
```

Fields are string expressions, one per column; scratch fields start with `_` and are not written:

| Expression | Meaning |
|---|---|
| `"ACTIVE"`, `"null"`, `"const:12"` | constants |
| `copy:parent.id`, `copy:unit_id->units.building_id->buildings.name` | copy a value; `->` follows reference columns, any number of hops |
| `key:SO-{placed_at|year}-{seq:06}` | business key; `{seq}` counts per distinct rest of the key |
| `template:{first_name|ascii}.{last_name|ascii}{id}@example.org` | text with placeholders; filters `lower upper slug ascii year date money` |
| `pool:first_names[country]`, `weighted:products.mix`, `choice:A|B|C`, `lookup:postal_codes[city]` | draw from pools (`pools/*.toml`) |
| `int:1..80`, `float:0..1`, `money:50..5000`, `money:amount_by_type[incident_type]` | numbers; the table form takes `[lo, hi]` by key |
| `bool:0.4`, `bool:cfg.pii.free_text_share`, `rand:+358 40 ### ####`, `rand:phone_patterns[country]` | probability, digit patterns |
| `date:as_of - 60..3600 days`, `date:start_date + 364 days`, `date:last_weekday_before(as_of, Tuesday)` | dates; bases: `as_of`, `history_start`, a field, `parent.field`, `day`, or a function |
| `ts:day @ 6..22`, `ts:parent.reported_at + 1..30 hours | clamp`, `ts:opened_at + 3..25 days | weekday | clamp` | timestamps; `@` picks a time of day; `clamp` never after as-of |
| `status_by_age:opened_at using bands.claims` | status from age bands (`[[bands.claims]] max_age, statuses = {NEW = 60, ...}`) |
| `calc:max(0, {claimed_amount} * 0.6 - {policy_id->policies.deductible})` | arithmetic over placeholders |
| `if:status == REJECTED then 0 else if:_decided == true then calc:... else null` | conditions: `== != < <= > >= in`, `x in A..B`, `and`/`or`; UPPERCASE words are literals; quote lowercase literals (`language == 'nb'`) |
| `pick:repair_shops where specialty == row._spec`, `pick:customers weighted by weight` | id of a random row of a generated table; `row.x` is the current row inside the condition |
| `pareto:1.3 max 40`, `expo:60 max 400`, `normal:100 sd 15 min 0` | shaped distributions (popularity, skew) |
| `seq_in_parent`, `sibling_count`, `copy:prev.valid_to`, `date:prev.valid_to + 1 days` | position among siblings and the previous sibling: pallet numbers, contiguous price history |
| `dates.outage_start`, `if:promised_ship_date in dates.outage_start..dates.outage_end then …` | named dates from `[dates]`, evaluated once |
| `sum:order_lines.line_total`, `count:orders`, `max:order_lines.pallet_number` | aggregates over children, in `[entity.X.after]` (computed once all entities exist) |
| `{x|ean13}`, `{x|title}`, `{id|pad6}` | more template filters |

Per-day entities take `seasonality = "pools.month_table"` (month → multiplier) and `pick_weight = "column"` for skewed
parent selection. `[entity.X.after]` holds fields computed after everything exists (totals, counts, maxima).

Extras: `drop_when = "reported_at > as_of"` discards a row; `[[entity.X.variants]]` creates one child per
matching variant (events of different types); `[[entity.X.burst]]` multiplies a per-day entity in a
window (`from`, `to`, `factor`, `prob`, `when`, `set = { field = value }`) — the storm week, the outage.
Fields may reference each other in any order; the engine evaluates on demand.

Anchors are declared in the same file: `pre` fields (dates the story needs), then either `pick` a row by
condition (`none_of` excludes rows that have related records) or `ensure` one — pick if a matching row
exists, otherwise create it and its `children` through the same field expressions (`always = true` always
creates; `parent_pick` chooses the parent). `fields` are copied or computed from the pick. The result lands
in `manifest.anchors.<group>.<key>` for scenarios and templates. "The second pallet from Tuesday's delivery
with no claim yet" is an `ensure` with five children and a fixed delivery date.

When a mechanic cannot be expressed — stock that reacts to orders, a partial shipment split — keep a
`lifecycle.py` with `STEPS` (the framework then runs it instead of the flow) or add
hooks `after_<entity>(ctx)` / `after_anchors(ctx)` next to a flow. Reporting hooks (`schema_context`,
`manifest_extra`, `run_checks`, `facts_sections`, `document_context`) work with both.

## Step 5 — scenarios and documents

One `[[scenario]]` per demo moment. Give it a `key` (the anchor key), `title`, `exercises`,
`expected`, a `document` (rendered from `documents/<document>.tmpl` with `{placeholders}` from the
anchor plus `document_context`), optional `[[scenario.image]]` entries (prompt built from the
anchor; a placeholder is drawn until `--images openai|google` is used once, after which the generated
image is stored in the pack under `documents/generated/` and restored into `out/` on every run), and `expect` entries the
verifier checks: `sql_zero`, `sql_one`, `sql_positive` (SQLite SQL with placeholders),
`weekday`, `min`, `before_as_of`, `document_contains` (`must` / `must_not`). Make at least one
document withhold the obvious key (no order number) so the demo must search.

## Step 6 — checks

`checks.toml`: `[[check]]` SQL (SQLite) that must return 0 — chronology, status consistency,
amounts adding up, bounds on PII in free text. `[[smoke]]` queries run as the read-only AI user on
H2 and PostgreSQL (`sql_postgres` overrides the dialect). Anything complex goes in `checks.py`.

## Step 6b — review and cost

Tag columns an LLM could author with `text_asset = true` (names, descriptions, notes); `estimate`
prices them. Mark non-English documents with `language = "sv"` on the scenario; the review queue puts
them first. After a run, read `out/<name>/REVIEW.md` and answer in `review/overrides.toml`:
`approve` (a human looked), `reject` (blank the field), `replace` (set `value`). Overrides apply on the
next generation, before files are written, and the manifest lists what was applied.

## Step 7 — run

```bash
python3 -m dsgen <name> validate          # structure and references
python3 -m dsgen <name> check             # generate + verify + H2 smoke test + FACTS.md
python3 -m dsgen <name> check --pg        # also PostgreSQL in Docker
python3 -m dsgen <name> check --h2-file   # also a ready-to-use H2 database file
python3 -m dsgen <name> estimate          # predict LLM/image cost by mode and model, no API calls
python3 -m dsgen <name> review            # print the review queue
```

Read `out/<name>/FACTS.md`: if the numbers do not tell the story the demo needs, adjust `config.toml`
and the anchors, not the docs.

## What never goes into a pack

Real people, real companies, real brands or logos in prompts, real phone numbers or e-mail
domains, API keys, and anything that would need a licence.
