"""Review queue and overrides.

Queue: after generation, score generated content by how much a human should look at it and write
<out>/REVIEW.md + <out>/review-queue.json with stable ids. Signals: rendered documents (per-item text,
highest), scenario anchors, non-English documents, personal data in free text, statistical outliers in
numeric columns, heavily repeated template texts in text_asset columns, and everything else (sampled).

Overrides: domains/<name>/review/overrides.toml answers the queue (approve / reject / replace by id) and
is applied deterministically at the end of generation, before anything is written."""
from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import tomllib

PHONE = re.compile(r"\+\d{2,3}[\s\d]{6,}")
EMAIL = re.compile(r"[\w.-]+@[\w.-]+\.\w+")


def _business_key(spec, table):
    cols = spec.entity(table).columns
    for c in cols:
        if c.unique and not c.pk:
            return c.name
    return cols[0].name


def _sig(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


def load_overrides(domain) -> list:
    p = os.path.join(domain.path, "review", "overrides.toml")
    if not os.path.exists(p):
        return []
    with open(p, "rb") as f:
        return tomllib.load(f).get("override", [])


def apply_overrides(domain, ctx) -> list:
    """Apply replace/reject overrides to the in-memory tables. Returns the list of applied override ids."""
    spec = domain.spec
    applied = []
    for ov in load_overrides(domain):
        oid, action = ov.get("id", ""), ov.get("action", "approve")
        if action == "approve":
            continue
        kind, _, rest = oid.partition(":")
        if kind == "row":
            table, key, col = rest.split(".", 2) if rest.count(".") >= 2 else (None, None, None)
            if not table or table not in spec.tables:
                continue
            bk = _business_key(spec, table)
            for r in ctx.tables[table]:
                if str(r.get(bk)) == key or str(r.get("id")) == key:
                    r[col] = ov.get("value", "") if action == "replace" else ""
                    applied.append(oid)
        elif kind == "template":
            table_col, _, sig = rest.rpartition(":")
            table, col = table_col.split(".", 1)
            for r in ctx.tables.get(table, []):
                v = str(r.get(col) or "")
                if v and _sig(v) == sig:
                    r[col] = ov.get("value", "") if action == "replace" else ""
                    applied.append(oid)
    return sorted(set(applied))


def build_queue(domain, ctx, out, manifest) -> list:
    spec = domain.spec
    items = []
    overrides = {o["id"]: o for o in load_overrides(domain)}
    group = domain.scenarios.get("scenarios", {}).get("anchors_group")

    def add(id_, score, reason, sample, kind):
        st = overrides.get(id_, {}).get("action", "open")
        items.append({"id": id_, "score": score, "kind": kind, "reason": reason, "sample": sample[:300], "status": st})

    # 1. documents and anchors (demo-critical)
    for sc in domain.scenarios.get("scenario", []):
        if sc.get("document"):
            p = os.path.join(out, "documents", sc["document"])
            text = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
            lang = sc.get("language", "en")
            score = 100 if lang != "en" else 90
            reason = "per-item document the demo reads aloud" + (f"; language {lang}, needs a native reader" if lang != "en" else "")
            add(f"doc:{sc['document']}", score, reason, text[:300], "document")
        anchors = manifest["anchors"].get(group, {}) if group else manifest["anchors"]
        if sc["key"] in anchors:
            add(f"anchor:{group}.{sc['key']}", 80, "demo anchor record; a wrong detail breaks the script",
                json.dumps({k: v for k, v in anchors[sc['key']].items() if k != "lines"}, ensure_ascii=False), "anchor")
    # 2. free text with personal data (should be intentional), 3. repeated templates, 4. outliers
    for e in spec.entities:
        bk = _business_key(spec, e.name)
        rows = ctx.tables[e.name]
        for c in e.columns:
            if c.pii == "free-text":
                hits = [r for r in rows if r.get(c.name) and (PHONE.search(str(r[c.name])) or EMAIL.search(str(r[c.name])))]
                for r in hits[:3]:
                    add(f"row:{e.name}.{r.get(bk)}.{c.name}", 60, f"personal data in free text ({len(hits)} rows in this column); confirm it is intended",
                        str(r[c.name]), "pii-free-text")
            if getattr(c, "text_asset", False):
                counts = {}
                for r in rows:
                    v = str(r.get(c.name) or "")
                    if v:
                        counts[v] = counts.get(v, 0) + 1
                for v, n in sorted(counts.items(), key=lambda kv: -kv[1])[:3]:
                    if n >= 20:
                        add(f"template:{e.name}.{c.name}:{_sig(v)}", 50, f"template text repeated {n} times; one bad sentence repeats {n} times", v, "template")
            if c.type.upper().startswith("DECIMAL") and len(rows) > 50:
                vals = [(float(r[c.name]), r) for r in rows if r.get(c.name) not in (None, "")]
                if len(vals) > 50:
                    med = statistics.median(v for v, _ in vals)
                    if med > 0:
                        outl = [(v, r) for v, r in vals if v > med * 12]
                        for v, r in sorted(outl, key=lambda x: -x[0])[:3]:
                            add(f"row:{e.name}.{r.get(bk)}.{c.name}", 40, f"outlier: {v:.2f} vs median {med:.2f}", str(v), "outlier")
    items.sort(key=lambda i: (-i["score"], i["id"]))
    with open(os.path.join(out, "review-queue.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    from .names import inventory
    _render(items, out, domain, inventory(domain, out))
    return items


def _render(items, out, domain, names=None):
    total = len(items)
    high = [i for i in items if i["score"] >= 80]
    approved = [i for i in items if i["status"] == "approve"]
    L = [f"# Review queue — {domain.spec.company}\n",
         f"{total} items, {len(high)} demo-critical (score ≥ 80), {len(approved)} approved, "
         f"{sum(1 for i in items if i['status'] in ('replace', 'reject'))} overridden. "
         "Answer in `domains/" + domain.name + "/review/overrides.toml` (approve | reject | replace by id); overrides apply on the next generation.\n",
         "| Score | Status | Id | Why | Sample |", "|---:|---|---|---|---|"]
    for i in items:
        sample = i["sample"].replace("|", "\\|").replace("\n", " ")[:140]
        L.append(f"| {i['score']} | {i['status']} | `{i['id']}` | {i['reason']} | {sample} |")
    L.append("\nScores: 100 non-English document · 90 document · 80 anchor record · 60 personal data in free text · 50 repeated template · 40 numeric outlier.")
    if names:
        L.append("\n## Name inventory\n\nEvery company-like name in the pack and the data, by source. All must be fictional: no real brand, retailer or "
                 "carrier, not even as a stem, and no generic shop word next to a real town. The offline denylist check ran in `verify`; "
                 "search the web for the ones you do not recognise and add real ones to `[names] deny` in a pools file.\n")
        for where, (vals, n) in names.items():
            if vals is None:
                L.append(f"* **{where}** — {n:,} distinct values, built from the pools above")
            else:
                L.append(f"* **{where}** ({n}): " + ", ".join(vals))
    with open(os.path.join(out, "REVIEW.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
