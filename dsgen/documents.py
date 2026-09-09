"""Documents for the scenarios: text documents rendered from templates (str.format_map over a context
the domain builds from the anchor record), images from a provider with a provenance file next to each,
and an INDEX.md listing what each document exercises."""
from __future__ import annotations

import base64
import datetime as dt
import io
import json
import os
import urllib.request


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"

    def __getitem__(self, key):
        v = super().__getitem__(key)
        return "" if v is None else v      # a null anchor field renders as empty text, never as 'None' 


def _flatten(anchor: dict) -> dict:
    flat = {}
    for k, v in anchor.items():
        if isinstance(v, list):
            flat[k] = "; ".join(str(x) if not isinstance(x, dict) else json.dumps(x, ensure_ascii=False) for x in v)
        else:
            flat[k] = v
    return flat


def scenario_context(domain, ctx, scenario, manifest_anchors) -> dict:
    group = domain.scenarios.get("scenarios", {}).get("anchors_group")
    anchor = manifest_anchors[group][scenario["key"]] if group else manifest_anchors[scenario["key"]]
    context = _flatten(anchor)
    context.update({"as_of": ctx.as_of.isoformat(), "as_of_rfc": ctx.as_of.strftime("%a, %d %b %Y"),
                    "yesterday_rfc": (ctx.as_of - dt.timedelta(days=1)).strftime("%a, %d %b %Y"),
                    "two_days_ago": (ctx.as_of - dt.timedelta(days=2)).isoformat()})
    hook = domain.hook("document_context")
    if hook:
        context.update(hook(ctx, scenario["key"], anchor))
    return context


def render_text_documents(domain, ctx, out, anchors) -> list:
    rendered = []
    for sc in domain.scenarios.get("scenario", []):
        if not sc.get("document"):
            continue
        context = _Safe(scenario_context(domain, ctx, sc, anchors))
        tmpl_path = os.path.join(domain.path, "documents", sc["document"] + ".tmpl")
        text = open(tmpl_path, encoding="utf-8").read().format_map(context)
        target = os.path.join(out, "documents", sc["document"])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(text)
        rendered.append(sc["document"])
    # index
    lines = [f"# Documents for {domain.spec.company}\n",
             "Generated from real records in the dataset by dsgen. Each document exercises a different part of the demo flow;",
             "the expectations the verifier checks for each are in `scenarios.toml`.\n",
             "| File | Scenario | Exercises | Expected outcome |", "|---|---|---|---|"]
    for sc in domain.scenarios.get("scenario", []):
        if sc.get("document"):
            lines.append(f"| {sc['document']} | {sc.get('title', sc['key'])} | {sc.get('exercises', '')} | {sc.get('expected', '')} |")
    with open(os.path.join(out, "documents", "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return rendered


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

def _placeholder_png(title: str, caption: str, size=(1024, 768)) -> bytes | None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return None
    import io
    W, H = size
    img = Image.new("RGB", (W, H), (70, 72, 76))
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, W - 40, H - 40], outline=(200, 200, 205), width=4)
    try:
        f1, f2 = ImageFont.load_default(30), ImageFont.load_default(22)
    except Exception:
        f1 = f2 = ImageFont.load_default()
    d.rectangle([0, 0, W, 90], fill=(20, 20, 20))
    d.text((24, 16), "PLACEHOLDER - replace with a generated or real image", fill=(255, 210, 60), font=f1)
    d.text((24, 54), caption[:120], fill=(230, 230, 230), font=f2)
    y = 140
    for line in [title] + [caption[i:i + 90] for i in range(0, len(caption), 90)]:
        d.text((60, y), line, fill=(235, 235, 235), font=f2)
        y += 34
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _openai_image(prompt: str, target: str = "") -> tuple[bytes, dict]:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    model = os.environ.get("DSGEN_OPENAI_IMAGE_MODEL", "gpt-image-1.5")
    quality = os.environ.get("DSGEN_OPENAI_IMAGE_QUALITY", "medium")      # low | medium | high (price scales with it)
    size = os.environ.get("DSGEN_OPENAI_IMAGE_SIZE", "1024x1024")         # 1024x1024 | 1536x1024 | 1024x1536
    ext = os.path.splitext(target)[1].lower().lstrip(".")
    fmt = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")
    body = {"model": model, "prompt": prompt, "size": size, "quality": quality, "n": 1, "output_format": fmt}
    req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.load(r)
    item = data["data"][0]
    usage = data.get("usage", {})
    return base64.b64decode(item["b64_json"]), {"model": model, "provider": "openai", "quality": quality, "size": size, "output_format": fmt,
                                                 "revised_prompt": item.get("revised_prompt"), "usage": usage,
                                                 "terms_note": "OpenAI API: output rights assigned to the customer; images carry C2PA Content Credentials. "
                                                               "Terms checked 2026-09-07 (docs/image-providers.md)."}


def _google_image(prompt: str, target: str = "") -> tuple[bytes, dict]:
    """Google: a Gemini image model through generateContent (default gemini-2.5-flash-image, which has a free tier
    with an AI Studio key), or an Imagen model through predict when DSGEN_GOOGLE_IMAGE_MODEL starts with 'imagen'."""
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_API_KEY not set")
    model = os.environ.get("DSGEN_GOOGLE_IMAGE_MODEL", "gemini-2.5-flash-image")
    headers = {"Content-Type": "application/json", "x-goog-api-key": key}
    if model.startswith("imagen"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:predict"
        body = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "4:3"}}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.load(r)
        raw, mime = base64.b64decode(data["predictions"][0]["bytesBase64Encoded"]), data["predictions"][0].get("mimeType", "image/png")
        note = "Google Imagen (paid tier only): commercial use allowed, SynthID watermark; terms checked 2026-09-07 (docs/image-providers.md)."
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseModalities": ["IMAGE"]}}
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.load(r)
        part = next(p for c in data.get("candidates", []) for p in c.get("content", {}).get("parts", []) if "inlineData" in p)
        raw, mime = base64.b64decode(part["inlineData"]["data"]), part["inlineData"].get("mimeType", "image/png")
        note = ("Google Gemini image model: SynthID watermark; on the free (unpaid) tier Google may use prompts and outputs to improve "
                "its services, on the paid tier it does not. Terms checked 2026-09-09 (docs/image-providers.md).")
    raw = _convert_to_extension(raw, mime, target)
    return raw, {"model": model, "provider": "google", "source_mime_type": mime, "terms_note": note}


def _convert_to_extension(raw: bytes, mime: str, target: str) -> bytes:
    """A provider that returns PNG for a .jpg target gets converted with Pillow when available; otherwise the bytes
    are kept and the provenance records the real MIME type."""
    ext = os.path.splitext(target)[1].lower()
    want = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(ext)
    if not want or want == mime:
        return raw
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}[want], quality=90)
        return buf.getvalue()
    except Exception:
        return raw


PROVIDERS = {"openai": _openai_image, "google": _google_image}


def render_images(domain, ctx, out, anchors, provider: str = "placeholder", usage=None) -> list:
    """For every [[scenario.image]]: build the prompt from the anchor, call the provider (or draw a placeholder),
    write the image and <file>.provenance.json. A failing provider falls back to the placeholder and says so."""
    written = []
    for sc in domain.scenarios.get("scenario", []):
        for im in sc.get("image", []):
            context = _Safe(scenario_context(domain, ctx, sc, anchors))
            prompt = im["prompt"].format_map(context)
            caption = im.get("caption", "").format_map(context)
            target = os.path.join(out, "documents", im["file"])
            os.makedirs(os.path.dirname(target), exist_ok=True)
            prov = {"scenario": sc["key"], "file": im["file"], "prompt": prompt, "caption": caption,
                    "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    "requested_provider": provider, "anchor": {k: v for k, v in dict(context).items() if k in ("order_number", "shipment_number", "customer", "customer_number")},
                    "terms_note": im.get("terms_note", "Confirm the provider's output-rights terms before public use; record the version here.")}
            data = None
            existing = None
            # generated images are stored in the pack (survive deleting out/); restore them into out/ first
            pack_img = os.path.join(domain.path, "documents", "generated", im["file"])
            if provider not in PROVIDERS and os.path.exists(pack_img) and os.path.exists(pack_img + ".provenance.json"):
                import shutil as _sh
                _sh.copyfile(pack_img, target)
                _sh.copyfile(pack_img + ".provenance.json", target + ".provenance.json")
            if os.path.exists(target + ".provenance.json"):
                try:
                    existing = json.load(open(target + ".provenance.json", encoding="utf-8"))
                except Exception:
                    existing = None
            if provider not in PROVIDERS and existing and existing.get("status") in ("generated", "kept") and os.path.exists(target):
                # a real image from an earlier run: keep it (and its provenance) rather than drawing a placeholder over it
                existing["status"] = "kept"
                existing["kept_at"] = prov["generated_at"]
                existing["current_prompt_matches"] = existing.get("prompt") == prompt
                with open(target + ".provenance.json", "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)
                if usage is not None:
                    usage.record(f"image {im['file']}", existing.get("provider", "?"), existing.get("model", "?"), images=0, status="kept")
                written.append((im["file"], "kept"))
                continue
            if provider in PROVIDERS:
                try:
                    data, meta = PROVIDERS[provider](prompt, target)
                    prov.update(meta)
                    prov["status"] = "generated"
                except Exception as e:  # network, key, quota: fall back and record why
                    prov["status"] = f"provider failed: {e}"
            if data is None:
                data = _placeholder_png(sc.get("title", sc["key"]), caption)
                prov.setdefault("status", "placeholder")
                prov["provider"] = "placeholder"
                if data is None:
                    prov["status"] = "placeholder not drawn: Pillow not installed"
            if data is not None:
                with open(target, "wb") as f:
                    f.write(data)
            with open(target + ".provenance.json", "w", encoding="utf-8") as f:
                json.dump(prov, f, indent=2, ensure_ascii=False)
            if prov.get("status") == "generated":
                # persist the paid image with the pack so no regeneration or deleted out/ can lose it
                import shutil as _sh
                os.makedirs(os.path.dirname(pack_img), exist_ok=True)
                _sh.copyfile(target, pack_img)
                _sh.copyfile(target + ".provenance.json", pack_img + ".provenance.json")
            if usage is not None:
                u = prov.get("usage") or {}
                usage.record(f"image {im['file']}", prov.get("provider", provider), f"{prov.get('model', 'placeholder')}" + (f"/{prov['quality']}" if prov.get("quality") else ""),
                             input_tokens=u.get("input_tokens", 0), output_tokens=u.get("output_tokens", 0), images=1, status=prov["status"])
            written.append((im["file"], prov["status"]))
    return written


def render_all(domain, ctx, out, anchors, provider="placeholder", usage=None):
    """Renders documents and images; returns (documents, images, contexts) where contexts holds the fully
    resolved template context per scenario so the verifier can check documents against the same values."""
    docs = render_text_documents(domain, ctx, out, anchors)
    imgs = render_images(domain, ctx, out, anchors, provider, usage)
    contexts = {sc["key"]: {k: v for k, v in scenario_context(domain, ctx, sc, anchors).items() if isinstance(v, (str, int, float, bool)) or v is None}
                for sc in domain.scenarios.get("scenario", [])}
    return docs, imgs, contexts
