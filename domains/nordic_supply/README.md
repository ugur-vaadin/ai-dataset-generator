# Nordic Supply domain pack

The first and richest pack: a wholesaler of sports, hiking and outdoor equipment selling to retail companies in
the Nordics, built for the three Vaadin AI business cases (self-service dashboard, message to claim, supervised
bulk change). Its flow is Python (`lifecycle.py` + `gen/`) because it uses mechanics the declarative engine does
not express (inventory reacting to orders, partial shipments); the property and insurance packs show the
declarative form.

* `docs/data-model.md` — every table and why it exists, business rules, what the model sees.
* `docs/demo-scenarios.md` — what each demo prompt should find, and what to check before presenting.
* The numbers for the current generation are in the published snapshot, `datasets/nordic_supply/FACTS.md`.

Files: `domain.toml` (entities, model-facing text), `config.toml` (volumes, rates, chains, carriers), `pools/`,
`scenarios.toml`, `checks.toml`, `review/overrides.toml`, `documents/` (six message templates, the kept photo),
`lifecycle.py` + `gen/`, `checks.py`, `facts.py`.

```bash
python3 -m dsgen nordic_supply check --pg --h2-file
```
