# Review queue — Nordic Supply

60 items, 12 demo-critical (score ≥ 80), 60 approved, 0 overridden. Answer in `domains/nordic_supply/review/overrides.toml` (approve | reject | replace by id, or approve a whole kind); overrides apply on the next generation.

| Score | Status | Id | Why | Sample |
|---:|---|---|---|---|
| 100 | approve | `doc:emails/05-quality-defect-sv.eml` | per-item document the demo reads aloud; language sv, needs a native reader | From: Sofia Johansson <sofia.johansson@stigfinnare.example> To: orders@nordicsupply.example Date: Mon, 07 Sep 2026 11:38:21 +0200 Subject: R |
| 90 | approve | `doc:emails/01-damaged-pallet.eml` | per-item document the demo reads aloud | From: "Elina Järvinen" <elina.jarvinen@eravakka.example> To: Nordic Supply Order Desk <orders@nordicsupply.example> Date: Mon, 07 Sep 2026 0 |
| 90 | approve | `doc:emails/02-missing-cartons.eml` | per-item document the demo reads aloud | From: Sofia Johansson <sofia.johansson@stigfinnare.example> To: orders@nordicsupply.example Date: Mon, 07 Sep 2026 10:15:40 +0200 Subject: s |
| 90 | approve | `doc:emails/03-wrong-colour-portal.txt` | per-item document the demo reads aloud | Channel: CUSTOMER PORTAL message Customer: Fjellkroken Sport Tromsø (C-10004) Sent by: Vegard Olsen <vegard.olsen@fjellkroken.sport.example> |
| 90 | approve | `doc:emails/04-late-delivery.eml` | per-item document the demo reads aloud | From: Gustav Strand <gustav.strand@vidderna.sport.example> To: orders@nordicsupply.example; lars.nygaard@nordicsupply.example Date: Sun, 06  |
| 90 | approve | `doc:emails/06-pricing-dispute.eml` | per-item document the demo reads aloud | From: Jonas Sørensen <jonas.sorensen@kystlinje.sport.example> To: orders@nordicsupply.example Date: Mon, 07 Sep 2026 13:05:55 +0200 Subject: |
| 80 | approve | `anchor:case2.A1_damaged_pallet` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007365", "order_id": 12421, "customer": "Erävakka Tampere", "customer_number": "C-10001", "customer_id": 1, "conta |
| 80 | approve | `anchor:case2.A2_missing_cartons` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007366", "order_id": 12422, "customer": "Stigfinnare Umeå", "customer_number": "C-10003", "customer_id": 3, "conta |
| 80 | approve | `anchor:case2.A3_wrong_colour` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007367", "order_id": 12423, "customer": "Fjellkroken Sport Tromsø", "customer_number": "C-10004", "customer_id": 4 |
| 80 | approve | `anchor:case2.A4_late_delivery` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007368", "order_id": 12424, "customer": "Vidderna Sport Kiruna", "customer_number": "C-10002", "customer_id": 2, " |
| 80 | approve | `anchor:case2.A5_quality_defect_sv` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007369", "order_id": 12425, "customer": "Stigfinnare Umeå", "customer_number": "C-10003", "customer_id": 3, "conta |
| 80 | approve | `anchor:case2.A6_pricing_dispute` | demo anchor record; a wrong detail breaks the script | {"order_number": "SO-2026-007370", "order_id": 12426, "customer": "Kystlinje Sport Aarhus", "customer_number": "C-10005", "customer_id": 5,  |
| 60 | approve | `row:claims.CL-2025-00001.description` | personal data in free text (45 rows in this column); confirm it is intended | 1 x Älv Summit Tarp Petrol on pallet 1 arrived with crushed cartons and torn packaging. Also affected: Skjærgård Palsa Hiking Shorts L Fores |
| 60 | approve | `row:claims.CL-2025-00036.description` | personal data in free text (45 rows in this column); confirm it is intended | 1 x Vuoma Storm II Synthetic Sleeping Bag -20°C Forest on pallet 1 arrived with crushed cartons and torn packaging. Driver noted the damage  |
| 60 | approve | `row:claims.CL-2025-00048.description` | personal data in free text (45 rows in this column); confirm it is intended | Delivery promised 2025-09-01 arrived 2025-09-03 (2 days late). Second late delivery this quarter, customer escalates. Call back Ebba on +46  |
| 60 | approve | `row:orders.SO-2025-000007.notes` | personal data in free text (748 rows in this column); confirm it is intended | Noora asked for delivery after 10:00, mobile +358 40 587 2869 |
| 60 | approve | `row:orders.SO-2025-000066.notes` | personal data in free text (748 rows in this column); confirm it is intended | Call Elin Karlsson on +46 70 239 33 06 30 min before delivery |
| 60 | approve | `row:orders.SO-2025-000083.notes` | personal data in free text (748 rows in this column); confirm it is intended | Nils asked for delivery after 10:00, mobile +46 70 435 42 79 |
| 50 | approve | `template:claim_lines.issue_note:b7ba0f45` | template text repeated 77 times; one bad sentence repeats 77 times | Torn outer wrap |
| 50 | approve | `template:claim_lines.issue_note:bb210253` | template text repeated 81 times; one bad sentence repeats 81 times | Product surface scratched |
| 50 | approve | `template:claim_lines.issue_note:f757888b` | template text repeated 77 times; one bad sentence repeats 77 times | Carton missing |
| 50 | approve | `template:claims.resolution_note:13b1d8e5` | template text repeated 110 times; one bad sentence repeats 110 times | Credit note issued. |
| 50 | approve | `template:claims.resolution_note:1a6ae744` | template text repeated 114 times; one bad sentence repeats 114 times | Redelivery completed, customer confirmed. |
| 50 | approve | `template:claims.resolution_note:3d2a23ba` | template text repeated 130 times; one bad sentence repeats 130 times | Goodwill credit agreed with account manager. |
| 50 | approve | `template:orders.notes:4a810b3a` | template text repeated 1444 times; one bad sentence repeats 1444 times | Deliver before store opening |
| 50 | approve | `template:orders.notes:b7f8ca4a` | template text repeated 1505 times; one bad sentence repeats 1505 times | Part of annual pre-order |
| 50 | approve | `template:orders.notes:deb031d3` | template text repeated 1505 times; one bad sentence repeats 1505 times | Season opener stock |
| 40 | approve | `row:claim_lines.205.amount` | outlier: 16128.00 vs median 168.80 | 16128.0 |
| 40 | approve | `row:claim_lines.810.amount` | outlier: 17275.20 vs median 168.80 | 17275.2 |
| 40 | approve | `row:claim_lines.900.amount` | outlier: 17275.20 vs median 168.80 | 17275.2 |
| 40 | approve | `row:claims.CL-2025-00202.claimed_amount` | outlier: 16342.00 vs median 319.78 | 16342.0 |
| 40 | approve | `row:claims.CL-2025-00213.approved_amount` | outlier: 12772.50 vs median 172.32 | 12772.5 |
| 40 | approve | `row:claims.CL-2025-00305.approved_amount` | outlier: 10857.11 vs median 172.32 | 10857.11 |
| 40 | approve | `row:claims.CL-2026-00411.approved_amount` | outlier: 17275.20 vs median 172.32 | 17275.2 |
| 40 | approve | `row:claims.CL-2026-00411.claimed_amount` | outlier: 17275.20 vs median 319.78 | 17275.2 |
| 40 | approve | `row:claims.CL-2026-00496.claimed_amount` | outlier: 17925.16 vs median 319.78 | 17925.16 |
| 40 | approve | `row:order_lines.16318.line_total` | outlier: 70269.60 vs median 433.20 | 70269.6 |
| 40 | approve | `row:order_lines.17837.list_price` | outlier: 1134.00 vs median 61.00 | 1134.0 |
| 40 | approve | `row:order_lines.17837.unit_price` | outlier: 1134.00 vs median 61.00 | 1134.0 |
| 40 | approve | `row:order_lines.23517.list_price` | outlier: 1134.00 vs median 61.00 | 1134.0 |
| 40 | approve | `row:order_lines.23517.unit_price` | outlier: 1134.00 vs median 61.00 | 1134.0 |
| 40 | approve | `row:order_lines.26392.line_total` | outlier: 71748.96 vs median 433.20 | 71748.96 |
| 40 | approve | `row:order_lines.5537.line_total` | outlier: 70580.16 vs median 433.20 | 70580.16 |
| 40 | approve | `row:order_lines.6297.list_price` | outlier: 1134.00 vs median 61.00 | 1134.0 |
| 40 | approve | `row:order_lines.6297.unit_price` | outlier: 1134.00 vs median 61.00 | 1134.0 |
| 40 | approve | `row:orders.SO-2025-001983.total_net` | outlier: 79757.87 vs median 3297.11 | 79757.87 |
| 40 | approve | `row:orders.SO-2025-003983.total_net` | outlier: 80467.66 vs median 3297.11 | 80467.66 |
| 40 | approve | `row:orders.SO-2026-006048.total_net` | outlier: 87697.62 vs median 3297.11 | 87697.62 |
| 40 | approve | `row:price_history.4612.list_price` | outlier: 1124.90 vs median 60.90 | 1124.9 |
| 40 | approve | `row:price_history.4613.list_price` | outlier: 1164.50 vs median 60.90 | 1164.5 |
| 40 | approve | `row:price_history.4615.list_price` | outlier: 1134.00 vs median 60.90 | 1134.0 |
| 40 | approve | `row:products.FJP-WTR-0015.weight_kg` | outlier: 23.04 vs median 0.41 | 23.041 |
| 40 | approve | `row:products.FJP-WTR-0020.weight_kg` | outlier: 17.22 vs median 0.41 | 17.222 |
| 40 | approve | `row:products.KAJ-WTR-0001.weight_kg` | outlier: 18.80 vs median 0.41 | 18.801 |
| 40 | approve | `row:promotions.246.promo_price` | outlier: 717.90 vs median 46.09 | 717.9 |
| 40 | approve | `row:promotions.3.promo_price` | outlier: 682.90 vs median 46.09 | 682.9 |
| 40 | approve | `row:promotions.95.promo_price` | outlier: 655.00 vs median 46.09 | 655.0 |
| 40 | approve | `row:shipments.SH-2026-000595.weight_kg` | outlier: 1062.50 vs median 21.20 | 1062.5 |
| 40 | approve | `row:shipments.SH-2026-002066.weight_kg` | outlier: 916.10 vs median 21.20 | 916.1 |
| 40 | approve | `row:shipments.SH-2026-006463.weight_kg` | outlier: 1054.00 vs median 21.20 | 1054.0 |

Scores: 100 non-English document · 90 document · 80 anchor record · 60 personal data in free text · 50 repeated template · 40 numeric outlier.

## Name inventory

Every company-like name in the pack and the data, by source. All must be fictional: no real brand, retailer or carrier, not even as a stem, and no generic shop word next to a real town. The offline denylist check ran in `verify`; search the web for the ones you do not recognise and add real ones to `[names] deny` in a pools file.

* **pools/catalogue.toml [naming.model_names]** (52): Aapa, Alpine, Arctic, Bre, Elv, Fjell, Fjord, Glacier, Hav, Hyrsky, Inari, Joki, Kaamos, Kaira, Kaldo, Kallio, Kero, Kilpis, Kulku, Kuru, Loiste, Myrsky, Nietos, Nordic, Nordvik, Nuten, Pallas, Palsa, Polar, Rauk, Revontuli, Ridge, Ruska, Selja, Selkä, Skare, Skog, Storm, Summit, Suvanto, Sylarna, Tind, Trail, Tundra, Tuuli, Ultra, Varanger, Vinter, Vuoma, Vuori, Ylläs, Åreskutan
* **pools/catalogue.toml [[supplier]].name** (36): Aurora Gear AB, Baltic Trail OÜ, Bergtatt Packs AS, Brenner Gas GmbH, Fjellvind AS, Fjord Paddle AS, Gråsten Boots AB, Halla Textiles Oy, Hygge Camp ApS, Isbre Winter AS, Isvidde Alpine AB, Jäkälä Outdoor Oy, Kaamos Outdoor Oy, Kajakk & Co AS, Kelo Kitchen Oy, Loimu Optics AB, Myrsky Rainwear Oy, Nietos Ski Oy, Nordvind Apparel AB, Nordwald Trek GmbH, Peak Hütte GmbH, Peilung Navigation GmbH, Polarlys Electronics AS, Rondane Sleep Systems AS, Ruska Footwear Oy, Saimaa Water Gear Oy, Skarv Climbing AS, Skjærgård Wool AS, Stig Trail Running AB, Suvanto Hardware AB, Taiga Merino Oy, Tundra Works ApS, Velo Nord ApS, Vuoma Equipment AS, Älv Outdoor AB, Øresund Cycle A/S
* **pools/names.toml [customers.independent_words]** (33): Aapa, Arctic, Aurora, Basecamp, Compass, Erä, Fjord, Fjäll, Forest, Hiker's, Kaamos, Kaira, Kalotti, Kayak, Kero, Lake, Loiste, Metsä, Nietos, Nordlys, Polar, Rakka, Ridge, Ruska, Selkä, Skog, Summit, Suvanto, Trail, Vaara, Vidde, Vinter, Vuoma
* **pools/names.toml [customers.independent_suffix]** (13): Adventure, Camping, Friluft, Fritid, Outdoor, Outfitters, Retki, Sport, Sport & Fritid, Sports, Trekking, Turutstyr, Urheilu
* **config.toml [[chains]].name** (8): Brevidde Friluft, Erävakka, Fjellkroken Sport, Kairankulma, Kystlinje Sport, Stigfinnare, Suuntima Sport, Vidderna Sport
* **config.toml [carriers].names** (6): Baltic Freight Line, Botnia Cargo, Havnelast, Kalott Freight, Nordfrakt, Polarpost
* **warehouses.name** (3): Göteborg Distribution Centre, Oslo Cross-dock, Vantaa Central Warehouse
* **suppliers.name** (36): Aurora Gear AB, Baltic Trail OÜ, Bergtatt Packs AS, Brenner Gas GmbH, Fjellvind AS, Fjord Paddle AS, Gråsten Boots AB, Halla Textiles Oy, Hygge Camp ApS, Isbre Winter AS, Isvidde Alpine AB, Jäkälä Outdoor Oy, Kaamos Outdoor Oy, Kajakk & Co AS, Kelo Kitchen Oy, Loimu Optics AB, Myrsky Rainwear Oy, Nietos Ski Oy, Nordvind Apparel AB, Nordwald Trek GmbH, Peak Hütte GmbH, Peilung Navigation GmbH, Polarlys Electronics AS, Rondane Sleep Systems AS, Ruska Footwear Oy, Saimaa Water Gear Oy, Skarv Climbing AS, Skjærgård Wool AS, Stig Trail Running AB, Suvanto Hardware AB, Taiga Merino Oy, Tundra Works ApS, Velo Nord ApS, Vuoma Equipment AS, Älv Outdoor AB, Øresund Cycle A/S
* **customers.name** — 2,400 distinct values, built from the pools above
* **customers.chain_name** (8): Brevidde Friluft, Erävakka, Fjellkroken Sport, Kairankulma, Kystlinje Sport, Stigfinnare, Suuntima Sport, Vidderna Sport
* **shipments.carrier** (6): Baltic Freight Line, Botnia Cargo, Havnelast, Kalott Freight, Nordfrakt, Polarpost
