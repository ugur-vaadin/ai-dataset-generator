# Review queue — Nordic Supply

60 items, 12 demo-critical (score ≥ 80), 12 approved, 0 overridden. Answer in `domains/nordic_supply/review/overrides.toml` (approve | reject | replace by id); overrides apply on the next generation.

| Score | Status | Id | Why | Sample |
|---:|---|---|---|---|
| 100 | approve | `doc:emails/05-quality-defect-trailhead-umea-sv.eml` | per-item document the demo reads aloud; language sv, needs a native reader | From: Sofia Johansson <sofia.johansson@trailhead.example> To: orders@nordicsupply.example Date: Mon, 07 Sep 2026 11:38:21 +0200 Subject: Rek |
| 90 | approve | `doc:emails/01-damaged-pallet-retkiaitta-tampere.eml` | per-item document the demo reads aloud | From: "Elina Järvinen" <elina.jarvinen@retkiaitta.example> To: Nordic Supply Order Desk <orders@nordicsupply.example> Date: Mon, 07 Sep 2026 |
| 90 | approve | `doc:emails/02-missing-cartons-trailhead-umea.eml` | per-item document the demo reads aloud | From: Sofia Johansson <sofia.johansson@trailhead.example> To: orders@nordicsupply.example Date: Mon, 07 Sep 2026 10:15:40 +0200 Subject: sho |
| 90 | approve | `doc:emails/03-wrong-colour-nordkapp-tromso-portal.txt` | per-item document the demo reads aloud | Channel: CUSTOMER PORTAL message Customer: Nordkapp Sports Tromsø (C-10004) Sent by: Vegard Olsen <vegard.olsen@nordkapp.sports.example> Sen |
| 90 | approve | `doc:emails/04-late-delivery-fjallbutiken-kiruna.eml` | per-item document the demo reads aloud | From: Gustav Strand <gustav.strand@fjallbutiken.example> To: orders@nordicsupply.example; lars.nygaard@nordicsupply.example Date: Sun, 06 Se |
| 90 | approve | `doc:emails/06-pricing-dispute-sportmagasinet-aarhus.eml` | per-item document the demo reads aloud | From: Jonas Sørensen <jonas.sorensen@sportmagasinet.example> To: orders@nordicsupply.example Date: Mon, 07 Sep 2026 13:05:55 +0200 Subject:  |
| 80 | approve | `anchor:case2.A1_damaged_pallet` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007391", "order_id": 12500, "customer": "Retkiaitta Tampere", "customer_number": "C-10001", "customer_id": 1, "con |
| 80 | approve | `anchor:case2.A2_missing_cartons` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007392", "order_id": 12501, "customer": "Trailhead Umeå", "customer_number": "C-10003", "customer_id": 3, "contact |
| 80 | approve | `anchor:case2.A3_wrong_colour` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007393", "order_id": 12502, "customer": "Nordkapp Sports Tromsø", "customer_number": "C-10004", "customer_id": 4,  |
| 80 | approve | `anchor:case2.A4_late_delivery` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007394", "order_id": 12503, "customer": "Fjällbutiken Kiruna", "customer_number": "C-10002", "customer_id": 2, "co |
| 80 | approve | `anchor:case2.A5_quality_defect_sv` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007395", "order_id": 12504, "customer": "Trailhead Umeå", "customer_number": "C-10003", "customer_id": 3, "contact |
| 80 | approve | `anchor:case2.A6_pricing_dispute` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007396", "order_id": 12505, "customer": "Sportmagasinet Aarhus", "customer_number": "C-10005", "customer_id": 5, " |
| 60 | open | `row:claims.CL-2025-00008.description` | personal data in free text (47 rows in this column); confirm it is intended | 12 x Boreal Summit Tunnel Tent 1P Moss Green on pallet 1 arrived with crushed cartons and torn packaging. Outer wrap was torn on arrival. Ca |
| 60 | open | `row:claims.CL-2025-00015.description` | personal data in free text (47 rows in this column); confirm it is intended | 1 x Älv Fjell Lite Water Filter Forest returned by end customers: pole segment split at the joint. Customer contact: Camilla Jørgensen, +45  |
| 60 | open | `row:claims.CL-2025-00031.description` | personal data in free text (47 rows in this column); confirm it is intended | 10 x Lumi Kaamos XT Snow Shovel Black returned by end customers: buckle cracked in the cold. Call back Kaisa on +358 40 552 6466. |
| 60 | open | `row:orders.SO-2025-000017.notes` | personal data in free text (719 rows in this column); confirm it is intended | Receiver: Jørgen Dahl, +47 987 75 852 |
| 60 | open | `row:orders.SO-2025-000050.notes` | personal data in free text (719 rows in this column); confirm it is intended | Contact Frida (frida.holm@ruskashop.example) if the loading bay is closed |
| 60 | open | `row:orders.SO-2025-000067.notes` | personal data in free text (719 rows in this column); confirm it is intended | Receiver: Juhani Korhonen, +358 40 300 2640 |
| 50 | open | `template:claim_lines.issue_note:5d73bdb1` | template text repeated 74 times; one bad sentence repeats 74 times | Carton crushed |
| 50 | open | `template:claim_lines.issue_note:5f56e218` | template text repeated 76 times; one bad sentence repeats 76 times | Short against packing list |
| 50 | open | `template:claim_lines.issue_note:bb210253` | template text repeated 78 times; one bad sentence repeats 78 times | Product surface scratched |
| 50 | open | `template:claims.resolution_note:1a6ae744` | template text repeated 125 times; one bad sentence repeats 125 times | Redelivery completed, customer confirmed. |
| 50 | open | `template:claims.resolution_note:3d2a23ba` | template text repeated 123 times; one bad sentence repeats 123 times | Goodwill credit agreed with account manager. |
| 50 | open | `template:claims.resolution_note:7bba758f` | template text repeated 118 times; one bad sentence repeats 118 times | Repair completed by supplier. |
| 50 | open | `template:orders.notes:4a810b3a` | template text repeated 1559 times; one bad sentence repeats 1559 times | Deliver before store opening |
| 50 | open | `template:orders.notes:b7f8ca4a` | template text repeated 1487 times; one bad sentence repeats 1487 times | Part of annual pre-order |
| 50 | open | `template:orders.notes:deb031d3` | template text repeated 1512 times; one bad sentence repeats 1512 times | Season opener stock |
| 40 | open | `row:claim_lines.314.amount` | outlier: 29078.40 vs median 154.50 | 29078.4 |
| 40 | open | `row:claim_lines.565.amount` | outlier: 29371.20 vs median 154.50 | 29371.2 |
| 40 | open | `row:claim_lines.917.amount` | outlier: 18955.20 vs median 154.50 | 18955.2 |
| 40 | open | `row:claims.CL-2025-00275.claimed_amount` | outlier: 30038.40 vs median 276.84 | 30038.4 |
| 40 | open | `row:claims.CL-2026-00093.approved_amount` | outlier: 20698.52 vs median 173.70 | 20698.52 |
| 40 | open | `row:claims.CL-2026-00093.claimed_amount` | outlier: 20698.52 vs median 276.84 | 20698.52 |
| 40 | open | `row:claims.CL-2026-00155.approved_amount` | outlier: 33886.00 vs median 173.70 | 33886.0 |
| 40 | open | `row:claims.CL-2026-00155.claimed_amount` | outlier: 33886.00 vs median 276.84 | 33886.0 |
| 40 | open | `row:claims.CL-2026-00457.approved_amount` | outlier: 20418.00 vs median 173.70 | 20418.0 |
| 40 | open | `row:order_lines.24594.line_total` | outlier: 74501.28 vs median 432.00 | 74501.28 |
| 40 | open | `row:order_lines.25034.line_total` | outlier: 78422.40 vs median 432.00 | 78422.4 |
| 40 | open | `row:order_lines.31190.list_price` | outlier: 1134.00 vs median 60.90 | 1134.0 |
| 40 | open | `row:order_lines.31190.unit_price` | outlier: 1134.00 vs median 60.90 | 1134.0 |
| 40 | open | `row:order_lines.355.list_price` | outlier: 1134.00 vs median 60.90 | 1134.0 |
| 40 | open | `row:order_lines.355.unit_price` | outlier: 1134.00 vs median 60.90 | 1134.0 |
| 40 | open | `row:order_lines.36020.list_price` | outlier: 1134.00 vs median 60.90 | 1134.0 |
| 40 | open | `row:order_lines.36020.unit_price` | outlier: 1134.00 vs median 60.90 | 1134.0 |
| 40 | open | `row:order_lines.49415.line_total` | outlier: 73430.40 vs median 432.00 | 73430.4 |
| 40 | open | `row:orders.SO-2026-004083.total_net` | outlier: 85299.36 vs median 3436.12 | 85299.36 |
| 40 | open | `row:orders.SO-2026-004250.total_net` | outlier: 125584.00 vs median 3436.12 | 125584.0 |
| 40 | open | `row:orders.SO-2026-006975.total_net` | outlier: 96130.38 vs median 3436.12 | 96130.38 |
| 40 | open | `row:price_history.4612.list_price` | outlier: 1124.90 vs median 60.90 | 1124.9 |
| 40 | open | `row:price_history.4613.list_price` | outlier: 1164.50 vs median 60.90 | 1164.5 |
| 40 | open | `row:price_history.4615.list_price` | outlier: 1134.00 vs median 60.90 | 1134.0 |
| 40 | open | `row:products.FJP-WTR-0015.weight_kg` | outlier: 23.04 vs median 0.41 | 23.041 |
| 40 | open | `row:products.FJP-WTR-0020.weight_kg` | outlier: 17.22 vs median 0.41 | 17.222 |
| 40 | open | `row:products.KAJ-WTR-0001.weight_kg` | outlier: 18.80 vs median 0.41 | 18.801 |
| 40 | open | `row:promotions.246.promo_price` | outlier: 717.90 vs median 46.09 | 717.9 |
| 40 | open | `row:promotions.3.promo_price` | outlier: 682.90 vs median 46.09 | 682.9 |
| 40 | open | `row:promotions.95.promo_price` | outlier: 655.00 vs median 46.09 | 655.0 |
| 40 | open | `row:shipments.SH-2025-001666.weight_kg` | outlier: 884.50 vs median 21.70 | 884.5 |
| 40 | open | `row:shipments.SH-2025-002709.weight_kg` | outlier: 1279.10 vs median 21.70 | 1279.1 |
| 40 | open | `row:shipments.SH-2026-000134.weight_kg` | outlier: 845.40 vs median 21.70 | 845.4 |

Scores: 100 non-English document · 90 document · 80 anchor record · 60 personal data in free text · 50 repeated template · 40 numeric outlier.
