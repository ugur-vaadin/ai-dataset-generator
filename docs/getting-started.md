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
2. Open the repository in your assistant (Claude Code, Cursor, Copilot, Codex, Gemini CLI, a local model
   in any tool that reads `AGENTS.md` and runs commands). Paste the description of your domain, nothing more:

   > Create a dataset using the following information about the domain: …

   or point at a file: "Author a dataset from the description in `brief.md`". `AGENTS.md` tells the
   assistant the rest: which guide and example to read, to write data rather than code, to run `validate`
   after every edit and `check` until it prints ALL CHECKS PASSED, and what to report. It derives the pack
   name from the company and states it in its first reply. Claude Code users can also type `/author-domain`.
3. Review `out/<name>/REVIEW.md`, answer in `domains/<name>/review/overrides.toml`, run `check` again. Its last
   section lists every company-like name in the pack: search the web for the ones you do not recognise, and add real
   ones to `[names] deny` in a pools file so the check catches them next time.
4. Optional photos: put your key in the environment (never in the repo; see `.env.example`) and run
   `python3 -m dsgen <name> check --images openai` once. Generated images are kept across later runs.

Measured: the property-maintenance pack (eight tables, one document) took the assistant 3 min 43 s from the
paragraph to a green check. A rich pack like Nordic Supply (nineteen tables, six documents, three business
cases) takes longer, mostly in the review of texts and anchors, not in generation.

## 4. Hand the output to the application

The output folder is described file by file in the README ("What a run produces"). For the dataset the
application is built on, publish it with `scripts/snapshot.sh <name>` into `datasets/<name>/`; the Java wiring is
in [integration-guide.md](integration-guide.md).
