# Nordic Supply domain pack

The first and richest pack: a wholesaler of sports, hiking and outdoor equipment selling to retail companies in
the Nordics, built for the three Vaadin AI business cases. Its flow is Python (`lifecycle.py` + `gen/`) because it
uses mechanics the declarative engine does not express (inventory reacting to orders, partial shipments); the
insurance and property packs show the declarative form.

* Case 1 (dashboard): a Göteborg warehouse outage in the second full week of last month makes late dispatches spike;
  Baltic Freight Line has transit delays; claims open over 7 days; backorder lines by category.
* Case 2 (message to claim): six customer e-mails (`documents/emails/*.tmpl`) rendered from real records, none with a
  claim yet; the canonical one is "the second pallet from Tuesday's delivery".
* Case 3 (bulk change): supplier Fjellvind AS has exactly 240 active products in three categories, some on promotion
  today and some on the first of next month.

Docs: `docs/data-model.md` (every table and why), `docs/demo-scenarios.md` (what each demo prompt should find).
Files: `domain.toml` (entities, model-facing text), `config.toml` (volumes, rates), `pools/`, `scenarios.toml`,
`checks.toml`, `review/overrides.toml`, `lifecycle.py` + `gen/`, `checks.py`, `facts.py`. Run
`python3 -m dsgen nordic_supply check --pg --h2-file` and read `out/nordic_supply/FACTS.md`.
