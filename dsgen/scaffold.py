"""Create a new domain pack: `python3 -m dsgen <name> new-domain --company "..."`. The result validates
and generates out of the box (two entities, one scenario, one document), so authoring starts from green."""
from __future__ import annotations

import os

from .domain import DOMAINS_DIR

DOMAIN_TOML = '''# {company} — domain specification. Fill in entities, columns, descriptions and PII tags.
# See DOMAIN_GUIDE.md. Validate with: python3 -m dsgen {name} validate

[domain]
name = "{name}"
version = "0.1.0"
company = "{company}"
description = "{description}"

[[entity]]
name = "people"
description = "People we deal with. One row per person."
exposed = false
columns = [
  {{ name = "id", type = "INT", pk = true }},
  {{ name = "full_name", type = "VARCHAR(120)", not_null = true, pii = "name" }},
  {{ name = "email", type = "VARCHAR(160)", not_null = true, unique = true, pii = "contact" }},
  {{ name = "created_at", type = "DATE", not_null = true }},
]

[[entity]]
name = "cases"
description = "The main business object. One row per case."
exposed = true
columns = [
  {{ name = "id", type = "INT", pk = true }},
  {{ name = "case_number", type = "VARCHAR(20)", not_null = true, unique = true, desc = "business key, e.g. 'CS-2026-000123'" }},
  {{ name = "person_id", type = "INT", not_null = true, ref = "people.id", desc = "-> people.id (hidden from the AI)" }},
  {{ name = "status", type = "VARCHAR(20)", not_null = true, desc = "OPEN, IN_PROGRESS, CLOSED" }},
  {{ name = "opened_at", type = "TIMESTAMP", not_null = true }},
  {{ name = "closed_at", type = "TIMESTAMP", desc = "NULL while open" }},
  {{ name = "amount", type = "DECIMAL(12,2)", not_null = true, desc = "EUR" }},
  {{ name = "notes", type = "VARCHAR(400)", pii = "free-text" }},
]

[views]

[sql]
runtime_tables = ""
indexes = """
CREATE INDEX ix_cases_status ON cases(status, opened_at);
"""
views = ""

[ai_schema]
intro = """You are querying the database of {company}. {description}
Dialect: {{dialect}}. Use standard SQL. Never modify data; only SELECT.
The application tells you today's date. "Last month" means the previous calendar month.

TABLES — table(columns), then what it holds and what non-obvious columns mean.
"""
hints = """
HINTS
- A case is OPEN when status <> 'CLOSED'.
{{dialect_hints}}
- Amounts are EUR.
{{context}}"""

[ai_schema.dialects.h2]
label = "H2 (version 2)"
hints = """- Date arithmetic: DATEADD('DAY', -7, CURRENT_TIMESTAMP), DATEDIFF('DAY', a, b), CURRENT_DATE."""

[ai_schema.dialects.postgres]
label = "PostgreSQL"
hints = """- Date arithmetic: CURRENT_TIMESTAMP - INTERVAL '7 days', (CAST(b AS DATE) - CAST(a AS DATE)) gives days."""
'''

CONFIG_TOML = '''# {company} — story tunables. Command-line flags override [generation].
[generation]
as_of = "{as_of}"
seed = 1
scale = 1.0
months = 12

[volume]
people = 500
cases_per_month = 80
'''

SCENARIOS_TOML = '''# Demo scenarios: anchor records the lifecycle builds, the document rendered for each, what the verifier checks.
[scenarios]
anchors_group = "demo"

[[scenario]]
key = "S1_example"
case = "1"
title = "Example scenario"
document = "emails/01-example.eml"
exercises = "A person writes about their open case; the case number is only in the quoted footer."
expected = "The agent finds the case and updates its status."
expect = [
  {{ kind = "sql_one", name = "case exists", sql = "SELECT COUNT(*) FROM cases WHERE id = {{case_id}}" }},
  {{ kind = "before_as_of", field = "opened_at" }},
  {{ kind = "document_contains", must = ["{{case_number}}", "{{person}}"] }},
]
'''

CHECKS_TOML = '''# SQL checks (SQLite dialect) that must return 0; {{as_of}} is substituted. [[smoke]] runs on the real database as the AI user.
[[check]]
name = "no cases opened after as_of"
sql = "SELECT COUNT(*) FROM cases WHERE date(opened_at) > {{as_of}}"

[[check]]
name = "closed cases have closed_at"
sql = "SELECT COUNT(*) FROM cases WHERE status = 'CLOSED' AND closed_at IS NULL"

[[smoke]]
name = "open cases by status"
sql = "SELECT status, COUNT(*) FROM cases GROUP BY status ORDER BY status"
'''

POOLS_TOML = '''# Name pools. Edit freely; order matters for reproducibility.
first_names = ["Anna", "Ben", "Chloe", "David", "Eva", "Finn", "Greta", "Hugo", "Ida", "Jon"]
last_names = ["Andersen", "Berg", "Carlsson", "Dahl", "Eriksen", "Falk", "Gran", "Holm", "Isaksen", "Juhl"]

[names]
# Real companies in this domain's sector and region that the pack must not resemble, matched at word start by `verify`
# (a shared list of Nordic outdoor brands, retailers and carriers is built in; see DOMAIN_GUIDE.md, "Names").
deny = []
allow = []
'''

TEMPLATE = '''From: {{person}} <{{person_email}}>
To: support@{name}.example
Date: {{as_of_rfc}} 09:12:00 +0200
Subject: Re: Your case {{case_number}}

Hello,

I have not heard anything about my case for two weeks. Can you tell me where it stands?

Regards,
{{person}}

> Case {{case_number}} opened {{opened_date}} — {company} support
'''

FLOW_TOML = '''# {company} — declarative flow: how many rows each entity has and how each field is produced.
# Expression reference: DOMAIN_GUIDE.md ("flow.toml"). Validate with: python3 -m dsgen {name} validate

[[bands.cases]]
max_age = 30
statuses = {{ OPEN = 55, IN_PROGRESS = 45 }}
[[bands.cases]]
statuses = {{ CLOSED = 90, IN_PROGRESS = 10 }}

[entity.people]
count = "cfg:volume.people"
[entity.people.fields]
full_name = "template:{{_fn}} {{_ln}}"
_fn = "pool:first_names"
_ln = "pool:last_names"
email = "template:{{_fn|ascii}}.{{_ln|ascii}}{{id}}@example.org"
created_at = "date:history_start - 0..900 days"

[entity.cases]
per = {{ day = "history", count = "cfg:volume.cases_per_month / 21", pick = "people", weekdays_only = true }}
[entity.cases.fields]
person_id = "copy:parent.id"
opened_at = "ts:day @ 8..17"
status = "status_by_age:opened_at using bands.cases"
closed_at = "if:status == CLOSED then ts:opened_at + 3..25 days | weekday | clamp else null"
amount = "money:50..5000"
notes = ""
case_number = "key:CS-{{opened_at|year}}-{{seq:06}}"

# The scenario record: an open case for a known person, opened about ten business days ago.
[[anchor]]
group = "demo"
key = "S1_example"
pre = {{ opened_day = "date:add_business_days(as_of, -10)" }}
[anchor.pick]
entity = "cases"
where = "status != CLOSED and opened_at <= anchor.opened_day"
[anchor.fields]
case_id = "copy:pick.id"
case_number = "copy:pick.case_number"
opened_at = "copy:pick.opened_at"
person = "copy:pick.person_id->people.full_name"
person_email = "copy:pick.person_id->people.email"
'''

LIFECYCLE_PY = '''"""{company} — optional Python hooks. Generation itself is declarative (flow.toml)."""
from __future__ import annotations


def document_context(ctx, key, anchor):
    return {{"opened_date": anchor["opened_at"][:10]}}


def schema_context(ctx):
    return ""


def manifest_extra(ctx):
    return {{}}
'''

README = '''# {company} domain pack

Generated by `dsgen new-domain`. Read `DOMAIN_GUIDE.md` at the repository root, then:

```bash
python3 -m dsgen {name} validate
python3 -m dsgen {name} check
```
'''


def create(name: str, company: str, description: str, as_of: str) -> str:
    import re
    if not re.match(r"^[a-z][a-z0-9_]*$", name):
        raise SystemExit("domain name must be snake_case (a-z, 0-9, _)")
    path = os.path.join(DOMAINS_DIR, name)
    if os.path.exists(path):
        raise SystemExit(f"{path} already exists")
    os.makedirs(os.path.join(path, "pools"))
    os.makedirs(os.path.join(path, "documents", "emails"))
    fmt = dict(name=name, company=company, description=description, as_of=as_of)
    files = {"domain.toml": DOMAIN_TOML, "config.toml": CONFIG_TOML, "flow.toml": FLOW_TOML, "scenarios.toml": SCENARIOS_TOML, "checks.toml": CHECKS_TOML,
             "pools/names.toml": POOLS_TOML, "documents/emails/01-example.eml.tmpl": TEMPLATE, "lifecycle.py": LIFECYCLE_PY,
             "README.md": README, "__init__.py": ""}
    for rel, content in files.items():
        with open(os.path.join(path, rel), "w", encoding="utf-8") as f:
            f.write(content.format(**fmt) if rel != "__init__.py" else "")
    return path
