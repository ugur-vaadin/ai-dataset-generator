---
name: author-domain
description: Author or extend a dsgen domain pack (a demo dataset for a Vaadin AI business case) from a domain description — interview only where needed, write the pack files, validate after every edit, check until green, report FACTS.md. Use when asked to create a dataset for a new domain/business case, add a scenario or entity to an existing pack, or make generated demo data for an app.
---

# Author a domain pack

Follow the section "When the user asks for a dataset" in `AGENTS.md` at the repository root, step by
step, and its rules. That file is the single source of the procedure for every assistant; this skill only
makes it a slash command in Claude Code.

Two reminders that matter most in practice:

- Data first, code last. The validator and the verifier are the referees, not your judgment: run
  `python3 -m dsgen <name> validate` after every edit and `python3 -m dsgen <name> check` until it prints
  `ALL CHECKS PASSED`.
- Never run `--images openai|google` yourself; it costs money. Report the command and the estimate.
