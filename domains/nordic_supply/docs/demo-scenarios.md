# Demo scenarios: what each prompt should find

The concrete numbers for the current generation (row counts, weekly late shipments, open claims,
the six anchor orders, the case 3 counts) are rendered into **[`out/nordic_supply/FACTS.md`](../../../out/nordic_supply/FACTS.md)**
by `python3 -m dsgen nordic_supply check`. This file explains what to ask and what kind of answer the data
holds; read the two side by side. "Today" is the as-of date, "last month" the calendar month
before it, "the first of next month" the next month start.

## Case 1 — Self-service dashboard (analyst)

The model sees `sql/ai-schema-h2.txt` (or the PostgreSQL variant, plus today's date) and writes SQL; rows are rendered in the
widget only. Prompts from the design chips and the business-case document:

| Prompt | What the data holds | Notes for the demo |
|---|---|---|
| "Which orders shipped after the promised date last month, by customer" | A third of last month's dispatches were late; the top customers have 3–5 late orders each (FACTS → Case 1) | Grid. The widget description should read "orders shipped after the promised ship date, <month>, by customer". |
| "Same thing as a chart, by week" | One ISO week stands out (FACTS → *Late dispatches by ISO week*) | Column chart. The spike is the Göteborg outage: dispatches planned for the outage week left 3–6 days late, in the following week. Clicking the bar should list those orders. |
| "Late shipments last month" (chip) | Seeded widget #1 (`saved_widgets`) | Shows the intended shape: title, plain-English description, SQL. |
| "Claims open over 7 days" / "Show me open claims that have been open over a week" (chip) | A few dozen claims (FACTS → *Claims open for more than 7 days*); nothing older than 120 days is open | Grid, oldest first. Seeded widget #2. |
| "Backorder lines by category" (chip) | Lines in most categories, led by Tents & Shelters (Fjellvind, short stock) and Winter Sports (pre-season) (FACTS → *Backorder lines by category*) | `inventory` agrees: those products have no free stock and a `next_inbound_date`. |
| "Which carrier delivered late most often last month?" | Baltic Freight Line, at roughly double the others' rate (FACTS → *Late deliveries by carrier*) | A second, findable cause beside the outage. `delivery_events` of type `DELAYED` carry reasons. |
| "Which warehouse caused the spike?" | GOT, in the week after the outage | Answerable from `shipments.warehouse_id`; the schema text also states the outage window. |

Ambiguity the AI should resolve out loud: "late" can mean dispatched after `promised_ship_date`
or delivered after `promised_delivery_date` (the `late_shipments` view exposes both); "last
month" is a calendar month.

## Case 2 — Message to claim (support agent)

Six raw messages in `out/documents/emails/` (index in `INDEX.md` there; the matching orders,
shipments, contacts and dates are in FACTS → *Case 2*). None has a claim yet; the agent creates
it. The form's lookups must find the records among thousands (see integration guide, section 5).

| Message | Exercises | Expected claim |
|---|---|---|
| **01 damaged pallet** (the document's example) | Order number only in the quoted confirmation; "Tuesday's delivery" and "second pallet" resolve through `shipments.delivered_at` and `shipment_lines.pallet_number = 2`; photo attachment | DAMAGED · REPLACEMENT · needed by Friday · URGENT/HIGH · claim lines = the pallet-2 lines |
| **02 missing cartons** | No order number at all: sender e-mail → customer, "last Friday" → shipment; quantities in cartons vs. pairs | MISSING_ITEMS · REDELIVERY or CREDIT · 18 pairs affected · HIGH |
| **03 wrong colour** (portal, terse) | Order reference given; wrong variant of the right product | WRONG_ITEM · REPLACEMENT · full quantity · question about keeping the wrong stock |
| **04 late delivery** | Promised vs. actual dates, carrier, percentage credit; **personal data** (a personal mobile, a named employee) for the masking demo; account manager in Cc | LATE_DELIVERY · CREDIT 10% of `orders.total_net` · HIGH |
| **05 quality defect** (Swedish) | Delivery three weeks ago; part of the quantity; return label requested | QUALITY_DEFECT · REPLACEMENT · 6 affected |
| **06 pricing dispute** (forwarded thread) | Promotion existed but list price was charged; difference computable from `promotions` and `order_lines` | PRICING_DISPUTE · CREDIT of the difference · LOW/NORMAL |

Validation moments worth showing: a `needed_by` before today, a quantity affected larger than the
ordered quantity, a claim type that hides/reveals sections (pallet number only for DAMAGED,
promised vs. actual dates only for LATE_DELIVERY, price fields only for PRICING_DISPUTE).

## Case 3 — Supervised bulk change (catalogue manager)

Prompt: *"raise prices 4% on everything from this supplier from the first of next month, except
products already on promotion"* with **Fjellvind AS** selected or named.

* Fjellvind has exactly **240** active products in three categories (FACTS → *Case 3*).
* "Already on promotion" has two defensible readings: on promotion **today** or on promotion **on
  the first of next month**. The promotions are laid out so the two differ by a few products
  (FACTS gives both counts and the resulting row counts). The AI should say which reading it used;
  the review list lets the manager remove the borderline rows either way.
* Effective date: insert `price_history` rows with `valid_from` = first of next month and close
  the current rows the day before (docs/integration-guide.md, section 7). Fjellvind has no scheduled
  future price, so the happy path has no conflicts; 25 products of other suppliers do, which is
  the edge case to show if asked.
* Rounding: current prices end in .00/.50/.90; show current → new per row and let the manager
  decide.
* Undo: delete the inserted rows and re-open the previous ones; `bulk_change_batches` and
  `bulk_change_items` record it.

## Regenerating with another date

`python3 -m dsgen nordic_supply check --as-of 2026-11-02` moves every anchor (outage, Tuesday
delivery, e-mail dates, promotions) and re-renders `out/nordic_supply/FACTS.md`. Nothing in this file needs
editing.
