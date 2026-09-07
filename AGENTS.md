# ai-demo-datasets — instructions for coding assistants

This repository generates deterministic demo datasets for Vaadin AI business-case applications.
`dsgen/` is the framework; `domains/<name>/` are domain packs (TOML data files; Python only for special mechanics).
The generator never calls an LLM. You, the assistant in this session, are the LLM: you author and
adjust packs; code renders, verifies and documents them.

Read before working:
- `DOMAIN_GUIDE.md` — how a pack is built and what the validator enforces.
- `domains/nordic_supply/` — the worked example; `domains/insurance_claims/` — a small one.
- `docs/generation-model.md` — the process on one page.

Commands (Python 3.11+, no packages):
- `python3 -m dsgen doctor` — environment check (Python, Java/H2, Docker, image keys) without printing secrets.
- `python3 -m dsgen <domain> validate` — pack structure; run after every edit to a pack.
- `python3 -m dsgen <domain> check` — generate, verify, H2 smoke test, FACTS/REVIEW/ESTIMATE. Add `--pg` (Docker), `--h2-file`, `--images openai|google`.
- `python3 -m dsgen <name> new-domain --company "..." --description "..."` — scaffold a pack that already passes.
- `scripts/test.sh` — validate + check every pack (including the hidden `_engine_smoke` pack that pins engine features).

Rules:
- Never edit `dsgen/` to make one pack work; work around the gap in the pack and report it (issue or CHANGELOG note).
- Never put API keys in files under this repository; they come from the environment (see `.env.example`).
- Everything domain-specific is data in the pack; `lifecycle.py` holds only the flow.
- Generated images are kept across runs; only `--images <provider>` replaces them (and costs money).
- Keep `CHANGELOG.md` and the pack's `README.md` current when you change behaviour.
