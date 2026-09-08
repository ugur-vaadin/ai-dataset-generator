# Documents for Nordic Supply

Generated from real records in the dataset by dsgen. Each document exercises a different part of the demo flow;
the expectations the verifier checks for each are in `scenarios.toml`.

| File | Scenario | Exercises | Expected outcome |
|---|---|---|---|
| emails/01-damaged-pallet.eml | Damaged pallet (the business-case document's example) | Order number only in the quoted confirmation; 'Tuesday's delivery' and 'second pallet' resolve via shipments.delivered_at and shipment_lines.pallet_number = 2; photo attachment. | DAMAGED · REPLACEMENT · needed by Friday · claim lines = the pallet-2 lines |
| emails/02-missing-cartons.eml | Missing cartons, no order number | No order number at all: sender e-mail → customer, 'last Friday' → shipment; quantities in cartons vs. pairs. | MISSING_ITEMS · REDELIVERY or CREDIT · 18 pairs affected |
| emails/03-wrong-colour-portal.txt | Wrong colour delivered (portal message) | Terse portal message with order reference; wrong variant of the right product. | WRONG_ITEM · REPLACEMENT · full quantity · question about keeping the wrong stock |
| emails/04-late-delivery.eml | Late delivery, credit request, personal data in the text | Promised vs. actual dates, carrier, percentage credit; contains a personal mobile number and a named employee (masking demo); account manager in Cc. | LATE_DELIVERY · CREDIT 10% of orders.total_net · HIGH |
| emails/05-quality-defect-sv.eml | Quality defect, written in Swedish | Non-English message; delivery three weeks ago; part of the quantity affected; return label requested. | QUALITY_DEFECT · REPLACEMENT · 6 affected |
| emails/06-pricing-dispute.eml | Pricing dispute (forwarded thread from accounts payable) | Promotion existed but list price was charged; the difference is computable from promotions and order_lines. | PRICING_DISPUTE · CREDIT of the difference · LOW/NORMAL |
