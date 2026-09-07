"""Cost instrumentation without calling anyone: a usage log every provider call appends to (placeholders
included, at $0), a summary for the manifest, and an offline `estimate` that predicts what the text and
image assets of a generation would cost under different authoring modes and models."""
from __future__ import annotations

import datetime as dt
import json
import os
import tomllib

PRICES = tomllib.load(open(os.path.join(os.path.dirname(__file__), "prices.toml"), "rb"))


class UsageLog:
    """Appends one JSON line per provider call to <out>/llm-usage.jsonl."""

    def __init__(self, out: str):
        self.path = os.path.join(out, "llm-usage.jsonl")
        self.entries = []
        if os.path.exists(self.path):
            os.remove(self.path)

    def record(self, purpose, provider, model, input_tokens=0, output_tokens=0, images=0, status="ok", cost_usd=None):
        if cost_usd is None:
            cost_usd = 0.0
            if model in PRICES["llm"]:
                p = PRICES["llm"][model]
                cost_usd = input_tokens / 1e6 * p["input"] + output_tokens / 1e6 * p["output"]
            key = f"{provider}/{model}" if provider != "placeholder" else "placeholder"
            if images:
                price = PRICES["image"].get(key) or PRICES["image"].get(key.rsplit("/", 1)[0]) or PRICES["image"].get(key.rsplit("/", 1)[0] + "/medium")
                if price is not None:
                    cost_usd += images * price
        e = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "purpose": purpose, "provider": provider,
             "model": model, "input_tokens": input_tokens, "output_tokens": output_tokens, "images": images, "status": status,
             "cost_usd": round(cost_usd, 6)}
        self.entries.append(e)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
        return e

    def summary(self) -> dict:
        return {"calls": len(self.entries), "images": sum(e["images"] for e in self.entries),
                "input_tokens": sum(e["input_tokens"] for e in self.entries), "output_tokens": sum(e["output_tokens"] for e in self.entries),
                "cost_usd": round(sum(e["cost_usd"] for e in self.entries), 4),
                "providers": sorted({e["provider"] for e in self.entries}), "prices_checked": PRICES["checked"]}


def measure_text_assets(ctx, spec) -> dict:
    """Token sizes (chars/4) of every column tagged text_asset = true, plus counts."""
    cpt = PRICES["assumptions"]["chars_per_token"]
    out = {}
    for e in spec.entities:
        for c in e.columns:
            if getattr(c, "text_asset", False):
                vals = [str(r.get(c.name) or "") for r in ctx.tables[e.name]]
                nonempty = [v for v in vals if v]
                toks = sum(len(v) for v in nonempty) / cpt
                out[f"{e.name}.{c.name}"] = {"items": len(nonempty), "tokens": round(toks), "avg_tokens": round(toks / len(nonempty), 1) if nonempty else 0,
                                             "distinct": len(set(nonempty))}
    return out


def estimate(domain, ctx, out) -> dict:
    """Predict LLM/image cost for this configuration under three authoring modes and each priced model."""
    A = PRICES["assumptions"]
    assets = measure_text_assets(ctx, domain.spec)
    docs = [sc for sc in domain.scenarios.get("scenario", []) if sc.get("document")]
    doc_tokens = 0
    for sc in docs:
        p = os.path.join(out, "documents", sc["document"])
        if os.path.exists(p):
            doc_tokens += len(open(p, encoding="utf-8").read()) / A["chars_per_token"]
    images = sum(len(sc.get("image", [])) for sc in domain.scenarios.get("scenario", []))
    total_items = sum(a["items"] for a in assets.values())
    total_out = sum(a["tokens"] for a in assets.values())
    modes = {}
    for model, p in PRICES["llm"].items():
        cost = lambda i, o: round(i / 1e6 * p["input"] + o / 1e6 * p["output"], 2)
        per_item_in = total_items * (A["prompt_tokens_per_item"] + A["context_tokens_per_item"])
        templ_out = sum(A["templates_per_column"] * max(a["avg_tokens"], 1) for a in assets.values())
        templ_in = len(assets) * A["templates_per_column"] * A["template_prompt_tokens"] / 10
        docs_in = len(docs) * A["prompt_tokens_per_document"]
        modes[model] = {
            "templates_by_code (LLM writes nothing at run time)": 0.0,
            "llm_writes_templates, code expands": cost(templ_in + docs_in, templ_out + doc_tokens),
            "llm_writes_every_item": cost(per_item_in + docs_in, total_out + doc_tokens),
        }
        modes[model + " (batch API, 50%)"] = {k: round(v / 2, 2) for k, v in modes[model].items()}
    image_costs = {k: round(images * v, 2) for k, v in PRICES["image"].items() if k != "placeholder"}
    return {"prices_checked": PRICES["checked"], "text_assets": assets, "text_items": total_items, "text_output_tokens": total_out,
            "documents": len(docs), "document_tokens": round(doc_tokens), "images": images, "cost_by_mode_usd": modes,
            "image_cost_usd": image_costs, "image_cost_with_10_drafts_usd": {k: round(v * 10, 2) for k, v in image_costs.items()}}


def render_estimate(est: dict, out: str, company: str) -> str:
    L = [f"# Cost estimate — {company}\n",
         f"Predicted from the generated data of this run and list prices checked {est['prices_checked']} (`dsgen/prices.toml`). "
         "No API was called. Token sizes are chars/4.\n",
         "## Text assets (columns tagged `text_asset`)\n", "| Column | Items | Distinct | Tokens | Avg/item |", "|---|---:|---:|---:|---:|"]
    for k, a in est["text_assets"].items():
        L.append(f"| {k} | {a['items']:,} | {a['distinct']:,} | {a['tokens']:,} | {a['avg_tokens']} |")
    L.append(f"| documents | {est['documents']} | — | {est['document_tokens']:,} | — |")
    L.append("\n## Cost by authoring mode (USD per full generation of these assets)\n")
    modes = list(next(iter(est["cost_by_mode_usd"].values())).keys())
    L.append("| Model | " + " | ".join(modes) + " |")
    L.append("|---|" + "---:|" * len(modes))
    for model, row in est["cost_by_mode_usd"].items():
        L.append(f"| {model} | " + " | ".join(f"${row[m]:,.2f}" for m in modes) + " |")
    L.append(f"\n## Images ({est['images']} in scenarios)\n\n| Provider/model | Final images | With 10 drafts each |\n|---|---:|---:|")
    for k, v in est["image_cost_usd"].items():
        L.append(f"| {k} | ${v:,.2f} | ${est['image_cost_with_10_drafts_usd'][k]:,.2f} |")
    per_item = [v["llm_writes_every_item"] for k, v in est["cost_by_mode_usd"].items() if "batch" not in k]
    templ = [v["llm_writes_templates, code expands"] for k, v in est["cost_by_mode_usd"].items() if "batch" not in k]
    L.append(f"\nReading: rows scale for free; the only run-time cost is text an LLM writes and images. At these volumes, LLM-written templates "
             f"expanded by code cost ${min(templ):.2f}–${max(templ):.2f} per generation; writing every item costs ${min(per_item):.2f}–${max(per_item):.2f} "
             "depending on the model (half through the Batch API). Consistency and review, not price, decide the mode.")
    text = "\n".join(L) + "\n"
    with open(os.path.join(out, "ESTIMATE.md"), "w", encoding="utf-8") as f:
        f.write(text)
    return text
