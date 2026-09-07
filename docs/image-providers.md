# Image generation providers for demo documents — comparison

For the team decision F32: which provider generates the photos and scanned documents the
business-case demos need (damaged pallet, delivery note, invoice, and later other domains).
Prices are list prices found on 2026-09-07 from third-party comparison pages and vary by
resolution and quality tier; verify against the provider's own pricing page before buying.
Sources at the end.

## What the demo needs

* Images that **match the data**: the prompt is built from the anchor record (pallet 2, two tent
  cartons crushed, torn stretch wrap, carrier label, fictional brand "Fjellvind"), no real logos.
* **Commercial use** in a public demo and in Vaadin marketing material.
* **Reproducibility**: images are generated once, committed with a provenance file, and only
  regenerated on purpose. Per-image price therefore matters little; terms and quality matter more.
* Enough realism for the **vision model** to read the damage, and for a viewer not to be
  distracted. 1024-pixel class is sufficient; the UI scales down.

## Comparison

| Provider / model | Price per 1024-class image | Tiers | Output rights for commercial use | Provenance marking | Training on your data (paid API) | Notes |
|---|---|---|---|---|---|---|
| **Google Imagen 4** (Gemini API / Vertex AI) | Fast $0.01–0.02 · Standard $0.04 · Ultra $0.06 | 3 quality tiers; up to 2K | Allowed; Google does not claim ownership of outputs | **SynthID** invisible watermark on every image, survives crop/resize/compression; verifier available | Not used on the paid tier | Strong photorealism; enterprise path through Vertex AI (same platform as Claude on Vertex); watermark is a plus for honesty in a demo |
| **OpenAI GPT Image 1.5** | $0.04 (some pages list $0.10 for the highest quality) | Quality low/medium/high; sizes to 1536 | Assigned to the user; commercial use and redistribution allowed | **C2PA** Content Credentials metadata (removable) | Not used for API | Best prompt adherence for text-in-image (labels, invoices, delivery notes); token-metered pricing varies with quality |
| **OpenAI GPT Image 1 Mini** | $0.005 | Lower quality | As above | C2PA | As above | Cheapest for drafts and bulk placeholders |
| **Black Forest Labs FLUX.2 Pro** (official API, also on fal / Replicate) | $0.05–0.055 | Pro / Flex / Max variants | Commercial use allowed; BFL claims no rights to outputs; may not be used to train competing models | None built in | Depends on host | Very photorealistic; multiple hosting options; **FLUX dev weights are non-commercial**, so only the hosted Pro/Flex/Max family qualifies |
| **FLUX schnell** (open weights, hosted on fal / Together / Replicate) | ≈ $0.003 | — | Apache-2.0 model; outputs usable commercially | None | Depends on host | Fast and nearly free; lower fidelity; fine for background/scenery images |
| **Ideogram 3.0** | $0.08 | — | Commercial use on paid plans | None | — | Best at legible text in images (invoices, labels), otherwise expensive |
| **Stability SDXL Turbo** | $0.005 | — | Commercial under Stability's community/enterprise licence depending on revenue | None | — | Cheapest; dated quality |
| Free stock (Unsplash / Pexels / Pixabay) | $0 | — | Commercial use, no attribution; **no model releases verified, $0 indemnification** on free tiers | — | — | Cannot match the data; visible real brands common. Scenery only |
| Own photos | ≈ $0 + an hour | — | Ours | — | — | Authentic; manual; one or two cases only |

## Re-evaluation with an OpenAI key in hand (2026-09-07)

OpenAI's current image models are `gpt-image-2` (latest), `gpt-image-1.5`, `gpt-image-1` and
`gpt-image-1-mini`. Pricing is by output tokens (about $32–40 per million image-output tokens), so
the price of one image depends on `quality` and `size`: roughly $0.01 (low), $0.04 (medium) and
$0.17 (high) for a 1024×1024 image on the 1.5 generation; the Batch API halves it. Requests go to
`POST /v1/images/generations` with `model`, `prompt`, `size`, `quality`, `n`; the image comes back
base64-encoded. Output rights are assigned to the customer; images carry C2PA Content Credentials.

What this means for us:

* **The implemented `openai` provider is the one to use now.** Defaults: `gpt-image-1.5`, quality
  `medium`, `1024x1024`; override with `DSGEN_OPENAI_IMAGE_MODEL`, `DSGEN_OPENAI_IMAGE_QUALITY`,
  `DSGEN_OPENAI_IMAGE_SIZE`. Draft at `low` (a cent), finalise at `medium`; `high` costs four times
  more for detail a demo screen will not show.
* **Nordic Supply's single photo costs about $0.04**, or under $0.50 with ten drafts. All six case 2
  scenarios with a photo each: about $0.25 for finals.
* Google Imagen stays the alternative if the OpenAI output looks too synthetic; nothing else changes.
* The first live run is also the first test of the request code; the provenance file records the
  outcome, and a failure falls back to the placeholder rather than breaking the run.

### First live run (2026-09-07, `gpt-image-1.5`, quality `low`, 1024×1024)

Status `generated`; 94 input and 431 output tokens (272 image tokens), logged at $0.011. The image
shows the pallet, torn stretch wrap, crushed cartons, a green tent bag and a legible "Fjellvind"
label — good enough to read the damage. Two flaws typical of `low`: bystanders in the background
despite "no people", and one garbled brand label on a side box. Plan: one `medium` run with the
prompt sharpened ("empty back room, nobody present; only the word Fjellvind on any label").

**Final (same day, `medium`, 1024×1024):** status `generated`, 1,056 image tokens, $0.04, a real JPEG
of 178 KB. No people, the only readable text is "Fjellvind" (plus the EUR pallet stamp, which is
realistic), torn wrap, split bottom carton with the green tent bag visible. Accepted as the case 2
attachment; the provenance file carries prompt, usage, terms note and anchor.

**Incident and third fix (same day).** A video-capture step deleted `out/nordic_supply` and regenerated it,
which destroyed the accepted medium-quality photo: the "keep" rule only protected an existing file. Generated
images are now **copied into the pack** (`domains/<name>/documents/generated/`) with their provenance and
restored into `out/` on every run, so neither regeneration nor deleting `out/` can lose a paid image. A
low-quality backup served as an interim; the medium-quality image was regenerated the same day ($0.04,
1,415 output tokens) and now lives in the pack with its full provenance.

Two framework fixes came out of the run: the provider now asks OpenAI for the output format that
matches the file extension (the first image was PNG bytes under a `.jpg` name), and a generated
image is **kept** across ordinary regenerations — only `--images <provider>` replaces it, so a
routine `check` cannot overwrite a paid photo with the placeholder. The provenance file records
`status: kept` and whether the prompt has changed since the image was made.

## Costs for the demo, for scale

| Scenario | Images | Imagen 4 Standard / GPT Image 1.5 (~$0.04) | Imagen 4 Fast (~$0.02) | GPT Image 1 Mini (~$0.005) |
|---|---:|---:|---:|---:|
| Nordic Supply, current six cases, one photo each | 6 | $0.24 | $0.12 | $0.03 |
| Three document types per case, 20 cases | 60 | $2.40 | $1.20 | $0.30 |
| Five domains × 20 cases × 3 documents | 300 | $12 | $6 | $1.50 |
| Iterating prompts (10 drafts per final image) | ×10 | ×10 | ×10 | ×10 |

Batch endpoints (OpenAI, Google) halve these where latency does not matter. Even with ten drafts
per final image, a full multi-domain document set costs tens of dollars. **Price is not a
selection criterion**; rights, provenance and quality are.

## Recommendation

1. **Primary: Google Imagen 4 Standard** for photos (damaged goods, warehouse, store), through
   Vertex AI if the demo already uses Google Cloud, otherwise the Gemini API. Reasons: clear
   commercial terms, SynthID watermark makes "this is a generated demo image" verifiable, strong
   photorealism, and paid-tier data is not used for training.
2. **Secondary: OpenAI GPT Image 1.5** for documents with legible text (delivery notes, invoices,
   packing lists), where prompt adherence to text matters most. C2PA credentials serve the same
   honesty purpose.
3. **Drafting: GPT Image 1 Mini or FLUX schnell** while iterating on prompts; regenerate the final
   with the primary model.
4. Do **not** use FLUX dev weights (non-commercial) or free stock for evidence images.

Whatever the choice, every image is committed with `<name>.provenance.json` (provider, model,
prompt, date, anchor id, terms version) so the licence question is answerable years later.

## Sources

[buildmvpfast image API pricing](https://www.buildmvpfast.com/api-costs/ai-image) ·
[CostLayer comparison, April 2026](https://costlayer.ai/blog/image-generation-api-pricing-2026-complete-cost-comparison) ·
[TokenMix image API comparison](https://tokenmix.ai/blog/ai-image-generation-api-comparison) ·
[OpenAI content provenance (C2PA)](https://developers.openai.com/api/docs/guides/content-provenance) ·
[OpenAI provenance signals help article](https://help.openai.com/en/articles/8912793-c2pa-and-synthid-in-openai-generated-images) ·
[Terms.Law on OpenAI output rights](https://terms.law/ai-output-rights/dall-e/) ·
[Imagen 4 on the Gemini API](https://developers.googleblog.com/imagen-4-now-available-in-the-gemini-api-and-google-ai-studio/) ·
[Google DeepMind SynthID](https://deepmind.google/models/synthid/) ·
[Gemini API image guide incl. watermark and copyright notes](https://zenn.dev/sora_biz/articles/gemini-api-image-generation-guide?locale=en) ·
[Black Forest Labs licensing](https://bfl.ai/licensing) ·
[FLUX dev non-commercial licence](https://bfl.ai/legal/non-commercial-license-terms) ·
[Flux 2 variants, licences and prices (Aug 2026)](https://invideo.io/blog/flux-ai-image-generator/) ·
[LicenseOrg on free stock licences](https://www.licenseorg.com/blog/free-stock-photos-licensing-traps)
