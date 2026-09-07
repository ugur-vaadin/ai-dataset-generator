"""Command line: python3 -m dsgen <domain> generate [--check] | verify | facts

Also reachable through the thin wrappers generate_dataset.py / verify_dataset.py (default domain
nordic_supply)."""
from __future__ import annotations

import argparse
import json
import os
import platform
import random

from . import VERSION
from .domain import list_domains, load_domain
from .model import D, first_of_next_month, iso, load_config, months_back
from .output import sha256, write_csv, write_sql_inserts
from .schema import write_ai_schema_texts, write_all_sql


def build_parser():
    p = argparse.ArgumentParser(prog="dsgen", description=f"dsgen v{VERSION} — deterministic demo datasets from domain packs.")
    p.add_argument("domain", nargs="?", default="nordic_supply", help=f"domain pack under domains/ (available: {', '.join(list_domains())})")
    p.add_argument("command", nargs="?", default="generate", choices=["generate", "verify", "facts", "check", "validate", "new-domain", "estimate", "review", "doctor"],
                   help="generate (default) | verify an existing out/ | facts | check = generate + verify + H2 + facts + review + estimate | validate | new-domain <name> | estimate (generate in memory, predict cost) | review (generate, write the review queue)")
    p.add_argument("--company", help="new-domain: company name")
    p.add_argument("--description", default="", help="new-domain: one-sentence description")
    p.add_argument("--as-of", help="'today' for the demo, ISO date (default from config)")
    p.add_argument("--seed", type=int, help="random seed (default from config)")
    p.add_argument("--scale", type=float, help="volume multiplier (default from config)")
    p.add_argument("--months", type=int, help="months of history before --as-of (default from config)")
    p.add_argument("--config", help="TOML file overlaying the domain's config.toml")
    p.add_argument("--out", help="output directory (default out/<domain>)")
    p.add_argument("--h2-file", action="store_true", help="also build out/db/<domain>.mv.db (needs java + H2 jar)")
    p.add_argument("--pg", action="store_true", help="with --check: also smoke-test against PostgreSQL in Docker")
    p.add_argument("--images", default=os.environ.get("DSGEN_IMAGE_PROVIDER", "placeholder"), help="image provider for documents: placeholder | openai | google")
    p.add_argument("--csv-path-prefix", help="directory the database will read CSVs from (default: absolute path of <out>/csv)")
    p.add_argument("--sql-inserts", action="store_true", help="also write sql/data.sql with plain INSERT statements")
    p.add_argument("--check", action="store_true", help="after generating: verify, smoke-test, render FACTS.md")
    p.add_argument("--quiet", action="store_true", help="less output")
    return p


def generate(domain, args) -> dict:
    load_config(domain.config_path, args.config)
    from .model import cfg
    g = cfg("generation")
    as_of = D.fromisoformat(args.as_of or g["as_of"])
    seed = args.seed if args.seed is not None else g["seed"]
    scale = args.scale if args.scale is not None else g["scale"]
    months = args.months if args.months is not None else g["months"]
    if as_of.weekday() >= 5:
        print("WARNING: --as-of falls on a weekend; documents read best when 'today' is a working day.")
    lc = domain.lifecycle
    if domain.flow is not None and not (lc and hasattr(lc, "STEPS")):
        from .flow import build_steps, make_ctx as flow_ctx
        ctx = flow_ctx(random.Random(seed), as_of, scale, months)
        steps = build_steps(domain, domain.flow, domain.pools)
    else:
        ctx = lc.make_ctx(random.Random(seed), as_of, scale, months)
        steps = lc.STEPS
    for step in steps:
        step(ctx)
        if not args.quiet:
            print(f"  {step.__name__:<20} done")
    from .review import apply_overrides
    applied = apply_overrides(domain, ctx)
    if applied and not args.quiet:
        print(f"  overrides applied: {applied}")
    out = args.out
    for sub in ("csv", "sql", "documents"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    spec = domain.spec
    counts = write_csv(ctx, spec, out)
    csv_prefix = args.csv_path_prefix or os.path.abspath(os.path.join(out, "csv"))
    write_all_sql(spec, out, csv_prefix)
    context = domain.hook("schema_context", lambda c: "")(ctx)
    write_ai_schema_texts(spec, out, context)
    from .llmusage import UsageLog
    usage = UsageLog(out)
    anchors_now = {k: v for k, v in ctx.anchors.items() if not k.startswith("_")}
    doc_contexts = {}
    if domain.scenarios:
        from .documents import render_all
        docs, imgs, doc_contexts = render_all(domain, ctx, out, anchors_now, provider=args.images, usage=usage)
        if not args.quiet:
            print(f"  documents: {len(docs)} text, images: {[(f, st) for f, st in imgs]}")
    write_docs = domain.hook("write_documents")
    if write_docs:
        write_docs(ctx, out, args)
    if args.sql_inserts:
        write_sql_inserts(ctx, spec, out)
    anchors = {k: v for k, v in ctx.anchors.items() if not k.startswith("_")}
    extra = domain.hook("manifest_extra", lambda c: {})(ctx)
    manifest = {"framework_version": VERSION, "domain": domain.name, "domain_version": spec.version,
                "as_of": iso(as_of), "seed": seed, "scale": scale, "months": months, "dialects": ["h2", "postgres"],
                "config": os.path.abspath(args.config) if args.config else os.path.relpath(domain.config_path),
                "python_version": platform.python_version(), "platform": platform.platform(), "csv_path_prefix": csv_prefix,
                "history_start": iso(ctx.history_start), "last_month": months_back(as_of, 1).strftime("%B %Y"),
                "first_of_next_month": iso(first_of_next_month(as_of)), "domain_anchors": extra,
                "row_counts": counts, "anchors": anchors, "document_context": doc_contexts,
                "overrides_applied": applied, "llm_usage": usage.summary(),
                "csv_sha256": {t: sha256(os.path.join(out, "csv", f"{t}.csv")) for t in counts}}
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)
    from .review import build_queue
    from .llmusage import estimate, render_estimate
    queue = build_queue(domain, ctx, out, manifest)
    est = estimate(domain, ctx, out)
    render_estimate(est, out, spec.company)
    manifest["review_queue"] = {"items": len(queue), "demo_critical": sum(1 for i in queue if i["score"] >= 80),
                                "approved": sum(1 for i in queue if i["status"] == "approve")}
    manifest["llm_estimate"] = {"text_items": est["text_items"], "text_output_tokens": est["text_output_tokens"], "images": est["images"],
                                "cost_by_mode_usd": est["cost_by_mode_usd"]}
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)
    print(f"Wrote {len(counts)} tables, {sum(counts.values()):,} rows to {out}/  (domain {domain.name}, as-of {iso(as_of)}, seed {seed}, scale {scale})")
    if not args.quiet:
        for t, n in counts.items():
            print(f"  {t:<20}{n:>9,}")
    return manifest


def check(domain, args) -> int:
    from . import facts, h2check, verify
    print("\n== verify")
    failures, _ = verify.run(domain, args.out, quiet=True)
    print("\n== H2 smoke test")
    h2 = h2check.run(domain, args.out)
    print(f"{h2['status']}: {h2['detail']}")
    for name, r in h2.get("queries", {}).items():
        print(f"  {'ok  ' if r['ok'] else 'FAIL'} {name}: {r['first_line']}")
    if args.pg:
        from . import pgcheck
        print("\n== PostgreSQL smoke test (Docker)")
        pg = pgcheck.run(domain, args.out)
        print(f"{pg['status']}: {pg['detail']}")
        for name, r in pg.get("queries", {}).items():
            print(f"  {'ok  ' if r['ok'] else 'FAIL'} {name}: {r['first_line']}")
        if pg["status"] == "failed":
            failures.append("postgres smoke test")
    if args.h2_file:
        from . import h2file
        print("\n== H2 database file")
        hf = h2file.build(domain, args.out)
        print(f"{hf['status']}: {hf['detail']}")
        if hf["status"] == "failed":
            failures.append("h2 file")
    print("\n== FACTS.md, REVIEW.md, ESTIMATE.md")
    facts.render_facts(domain, args.out)
    print(f"rendered {os.path.join(args.out, 'FACTS.md')} (+ REVIEW.md, ESTIMATE.md)")
    if failures or h2["status"] == "failed":
        print("\nCHECK FAILED")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.out:
        args.out = os.path.join("out", args.domain)
    if args.domain == "doctor" or args.command == "doctor":
        from .doctor import run as doctor
        return doctor()
    if args.command == "new-domain":
        from .scaffold import create
        import datetime as _dt
        path = create(args.domain, args.company or args.domain.replace("_", " ").title(), args.description or "A demo company.", _dt.date.today().isoformat())
        print(f"created {os.path.relpath(path)}; next: python3 -m dsgen {args.domain} validate && python3 -m dsgen {args.domain} check")
        return 0
    if args.command == "validate":
        from .validate import validate
        from .domain import DOMAINS_DIR
        problems = validate(os.path.join(DOMAINS_DIR, args.domain))
        for pr in problems:
            print("PROBLEM:", pr)
        print("valid" if not problems else f"{len(problems)} problem(s)")
        return 1 if problems else 0
    domain = load_domain(args.domain)
    from .validate import validate as _validate
    problems = _validate(domain.path)
    if problems:
        for pr in problems:
            print("PROBLEM:", pr)
        return 1
    if args.command == "verify":
        from . import verify
        load_config(domain.config_path, args.config)
        failures, _ = verify.run(domain, args.out, quiet=args.quiet)
        return 1 if failures else 0
    if args.command == "facts":
        from . import facts
        facts.render_facts(domain, args.out)
        return 0
    manifest = generate(domain, args)
    if args.command == "estimate":
        print(open(os.path.join(args.out, "ESTIMATE.md"), encoding="utf-8").read())
        return 0
    if args.command == "review":
        print(open(os.path.join(args.out, "REVIEW.md"), encoding="utf-8").read()[:4000])
        return 0
    if args.command == "check" or args.check:
        return check(domain, args)
    return 0
