# A domain-generic demo application

Decided 2026-09-09: the AI business-case application should adapt to any domain pack, so that a prospect's own
domain can be generated with dsgen and shown in the same app. This page is the plan and the open questions. It
is not a specification of the Vaadin code; that lives with the application.

## What "generic" has to mean, case by case

| Case | Bound to the order desk today | Generic form |
|---|---|---|
| 1 Self-service dashboard | Nothing: `DatabaseProvider` already works from the pack's schema text and the read-only account. | Load the schema text and the loaders of whichever pack is configured. Saved widgets and the activity log are pack-independent. |
| 2 Message to record | The claim form: its fields, its lookups (customer → order → line), the sections per claim type. | The pack declares the *target record*: which entity a message becomes, which fields the form shows, which lookups fill them and their filter columns, which field selects the visible sections, and which documents are the demo messages. The app renders a `FormAIController` form from that declaration. |
| 3 Supervised bulk change | The catalogue grid and the price-history insert. | The pack declares the *bulk target*: the grid entity and its editable columns, the effective-date column and how a change is written (a new dated row versus an update), and the anchor sentence for the demo. The app builds the review list from that. |

Everything the app needs beyond the data is therefore a small declaration per pack. Proposed shape, a new
section in `domain.toml`:

```toml
[app]
title = "Nordic Supply order desk"
dashboard_chips = ["Late shipments last month", "Claims open over 7 days", "Backorder lines by category"]

[app.message_to_record]
entity = "claims"
documents = "documents/emails/*"                 # the demo messages
lookups = [
  { field = "customer_id", from = "customers", label = "name", search = ["name", "customer_number", "email_domain"] },
  { field = "order_id", from = "orders", label = "order_number", filter_by = "customer_id" },
  { field = "shipment_id", from = "shipments", label = "shipment_number", filter_by = "order_id" },
]
section_selector = "claim_type"                  # its value shows/hides sections
sections = { DAMAGED = ["pallet_number"], LATE_DELIVERY = ["promised_delivery_date", "delivered_at"], PRICING_DISPUTE = ["claimed_amount"] }

[app.bulk_change]
entity = "products"
editable = ["list_price"]
effective_date = { table = "price_history", from = "valid_from", to = "valid_to" }   # a change is a new dated row
example = "raise prices 4% on everything from Skarvind AS from the first of next month, except products already on promotion"
```

`validate` would check the declaration against the entities, so a pack that claims a field the form cannot
show fails before anyone runs the app.

## Phases

1. **Nordic Supply through the declaration.** Add `[app]` to the Nordic pack, make the three views read it, and
   confirm the demo is unchanged. This is the refactoring step; nothing new is shown yet.
2. **A second pack in the same app.** Point the app at `property_maintenance` (fault reports become work
   orders) and fix whatever assumed the order desk. The property pack gets its `[app]` section, the guide and
   the scaffold learn the new section, and the quickstart video ends with the generated domain running in the
   app.
3. **Authoring from the app.** Only after 1 and 2: a view where a person pastes the domain paragraph, the
   assistant authors the pack, and the app reloads it. This reverses the "subscription, not API" decision and
   needs a key and a provider abstraction, so it stays a separate decision.

## Open questions for the team

- **Repository.** New repository for the application, or a module next to the generator? The generator stays
  Python and independent either way; the app consumes `datasets/<name>/` or runs the generator as a build step.
- **Provider stack.** Spring AI or LangChain4j behind the Vaadin AI components; which model; who owns the key
  for a public instance. The generator does not care, the app does.
- **Loading.** H2 in memory from the CSVs at start-up (one command, the case document's starting position) or
  PostgreSQL in a container for a hosted instance. Both loaders exist per pack.
- **Owner and time.** Phase 1 is a refactoring of the existing views; phase 2 is where the generic claims get
  tested. Roughly two to three weeks for one developer for both, excluding the authoring view.

## What the generator will do for this

- Add the `[app]` section to the spec, the validator and the scaffold, with the Nordic Supply and property
  packs filled in (on request, once the app team confirms the shape above).
- Keep `datasets/<name>/` as the contract the app loads, with `summary.html` as the page the app can link to.
