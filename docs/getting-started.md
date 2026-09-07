# Getting started — for anyone with the repository

You need Python 3.11 and a coding assistant of your choice. Nothing in this repository calls an LLM;
the assistant is the LLM, and it works from the files in the repository, so any model, subscription,
or tool that can read a repository and run commands will do. The framework's commands, the validator and
the verifier are the contract; the assistant fills in the pack until they pass.

## 1. Check the machine

```bash
python3 -m dsgen doctor
```

Python is the only requirement for generating and verifying. Java plus an H2 jar enables the H2 smoke
test and the database file; Docker enables the PostgreSQL test; an image key enables real photos.
Everything optional is skipped when missing, and the run says so.

## 2. Run an existing domain

```bash
python3 -m dsgen nordic_supply check            # ~6 s: generate, verify, H2, FACTS.md, REVIEW.md, ESTIMATE.md
open out/nordic_supply/FACTS.md
```

## 3. Author a new domain with your assistant

1. Scaffold: `python3 -m dsgen <name> new-domain --company "..." --description "..."`. The result
   already validates and passes `check`.
2. Open the repository in your assistant (Claude Code, Cursor, Copilot, Codex, anything that reads
   `AGENTS.md` / `CLAUDE.md` and runs commands). Paste the business-case text and this instruction:

   > Author the domain pack `domains/<name>/` for this business case following `DOMAIN_GUIDE.md`, using
   > `domains/nordic_supply/` as the worked example. Work entity by entity, run
   > `python3 -m dsgen <name> validate` after every edit and `python3 -m dsgen <name> check` when the
   > pack is complete; fix until it prints ALL CHECKS PASSED. Then summarise `out/<name>/FACTS.md`, the
   > document index and the top of `REVIEW.md`.

   Claude Code users can type `/author-domain` instead; it runs the same steps.
3. Review `out/<name>/REVIEW.md`, answer in `domains/<name>/review/overrides.toml`, run `check` again.
4. Optional photos: put your key in the environment (never in the repo; see `.env.example`) and run
   `python3 -m dsgen <name> check --images openai` once. Generated images are kept across later runs.

Expect a few hours of assisted work for a rich domain (Nordic Supply: three business cases, nineteen
tables, six documents) and about an hour for a small one (the insurance pack: eight tables, one document).

## 4. Hand the output to the application

`out/<name>/` holds CSVs, DDL, loaders and read-only accounts for H2 and PostgreSQL, the model-facing
schema text, the documents with provenance, and the facts. `docs/integration-guide.md` shows the Java
wiring.

## What is and is not automated

| Step | Automated? |
|---|---|
| Pack structure check, generation, verification, H2/PostgreSQL smoke tests, facts, review queue, cost estimate | Yes, one command |
| Regenerating for a new date or scale | Yes, a flag |
| Applying review answers | Yes, on the next run |
| Image generation | Yes, given a key; one flag; kept afterwards |
| Deciding entities, vocabularies, stories, texts for a new domain | No — a person with an assistant, guided by `DOMAIN_GUIDE.md` and enforced by `validate` |
| Writing `lifecycle.py` (how records flow) | No — the one piece of Python per domain, usually written by the assistant |
| Reading the review queue | No — that is the point of it |
