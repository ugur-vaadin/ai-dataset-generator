# Image providers for demo documents

Which provider generates the photos a business-case demo needs (a damaged pallet today; delivery notes,
invoices and other domains later), what it costs, and what we run. Prices are list prices seen on
2026-09-07 and vary by resolution and quality tier; check the provider's pricing page before buying.

## What the demo needs

* Images that **match the data**: the prompt is built from the anchor record (pallet 2, tent cartons crushed,
  torn stretch wrap, the fictional brand on the label), no real logos.
* **Commercial use** in a public demo and in marketing material.
* **Reproducibility**: an image is generated once, stored in the pack with a provenance file, restored into
  the output on every run, and replaced only on purpose (`--images <provider>`). Per-image price therefore
  matters little; terms and quality matter more.
* Enough realism for a vision model to read the damage and for a viewer not to be distracted. 1024 pixels is
  enough; the UI scales down.

## What we run

The `openai` provider with `gpt-image-1.5`, quality `medium`, 1024×1024 (override with
`DSGEN_OPENAI_IMAGE_MODEL`, `DSGEN_OPENAI_IMAGE_QUALITY`, `DSGEN_OPENAI_IMAGE_SIZE`). Measured on the Nordic
Supply pallet photo: about $0.011 at `low`, $0.04 at `medium`; `high` costs about four times `medium` for detail
a demo screen does not show. Draft at `low`, finalise at `medium`. Output rights are assigned to the customer
and images carry C2PA Content Credentials. A failed call falls back to the labelled placeholder and says so in
the provenance file. The `google` provider (Imagen) is implemented as the alternative and has not been run live.

The person runs the paid command, never the assistant (`AGENTS.md`). The key comes from the environment
(`.env.example`).

## Comparison

| Provider / model | Price per 1024-class image | Output rights for commercial use | Provenance marking | Training on your data (paid API) | Notes |
|---|---|---|---|---|---|
| **OpenAI GPT Image 1.5** (in use) | ≈ $0.01 low · $0.04 medium · $0.17 high | Assigned to the user; redistribution allowed | C2PA | Not used for training by default on the API | Best prompt adherence for legible text; what we run |
| OpenAI GPT Image 1 Mini | $0.005 | As above | C2PA | As above | Cheapest for drafts |
| **Google Imagen 4** (Gemini API / Vertex AI) | Fast $0.01–0.02 · Standard $0.04 · Ultra $0.06 | Allowed; Google claims no ownership of outputs | SynthID invisible watermark | Paid tier: not used | Strong photorealism; the implemented alternative |
| Black Forest Labs FLUX.2 Pro | $0.05–0.055 | Allowed; BFL claims no rights to outputs | None | Depends on host | FLUX *dev* weights are non-commercial: do not use |
| FLUX schnell (open weights, hosted) | ≈ $0.003 | Apache-2.0 | None | Depends on host | Nearly free; lower fidelity |
| Ideogram 3.0 | $0.08 | Paid plans | None | — | Best legible in-image text; expensive |
| Stability SDXL Turbo | $0.005 | Community/enterprise licence by revenue | None | — | Dated quality |
| Free stock (Unsplash, Pexels, Pixabay) | $0 | Commercial, no attribution; no model releases, no indemnification | — | — | Cannot match the record; visible reuse |
| Own photos | ≈ $0 plus an hour | Ours | — | — | Authentic; one or two cases only |

## Costs at scale

| Scenario | Images | GPT Image 1.5 medium / Imagen 4 Standard (≈ $0.04) | Imagen 4 Fast (≈ $0.02) | GPT Image 1 Mini (≈ $0.005) |
|---|---:|---:|---:|---:|
| Nordic Supply, six case 2 scenarios, one photo each | 6 | $0.24 | $0.12 | $0.03 |
| Three document types per case, 20 cases | 60 | $2.40 | $1.20 | $0.30 |
| Five domains × 20 cases × 3 documents | 300 | $12 | $6 | $1.50 |
| Iterating prompts, ten drafts per final image | ×10 | ×10 | ×10 | ×10 |

Batch endpoints halve these where latency does not matter. Even a full multi-domain document set with ten
drafts per image costs tens of dollars: **price is not a selection criterion**; rights, provenance and quality are.

## Rules that follow

1. Every generated image lives in the pack under `documents/generated/` with `<name>.provenance.json`
   (provider, model, quality, prompt, date, anchor, terms note), so the licence question is answerable later.
2. Use GPT Image 1.5 for documents with legible text; Imagen 4 if a photo looks too synthetic; drafts on the
   cheapest tier, finals on `medium`.
3. Never FLUX dev weights or free stock for evidence images.

## Sources

[buildmvpfast image API pricing](https://www.buildmvpfast.com/api-costs/ai-image) ·
[CostLayer comparison, April 2026](https://costlayer.ai/blog/image-generation-api-pricing-2026-complete-cost-comparison) ·
[TokenMix image API comparison](https://tokenmix.ai/blog/ai-image-generation-api-comparison) ·
[OpenAI content provenance (C2PA)](https://developers.openai.com/api/docs/guides/content-provenance) ·
[OpenAI provenance signals help article](https://help.openai.com/en/articles/8912793-c2pa-and-synthid-in-openai-generated-images) ·
[Terms.Law on OpenAI output rights](https://terms.law/ai-output-rights/dall-e/) ·
[Imagen 4 on the Gemini API](https://developers.googleblog.com/imagen-4-now-available-in-the-gemini-api-and-google-ai-studio/) ·
[Google DeepMind SynthID](https://deepmind.google/models/synthid/) ·
[Black Forest Labs licensing](https://bfl.ai/licensing) ·
[FLUX dev non-commercial licence](https://bfl.ai/legal/non-commercial-license-terms) ·
[LicenseOrg on free stock licences](https://www.licenseorg.com/blog/free-stock-photos-licensing-traps)
