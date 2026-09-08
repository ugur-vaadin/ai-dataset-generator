-- Read-only account for the AI's DatabaseProvider (H2 syntax).
-- It can SELECT the exposed tables and views and nothing else: no hidden tables, no runtime tables, no writes.
CREATE USER IF NOT EXISTS ai_reader PASSWORD 'ai_reader';
GRANT SELECT ON users TO ai_reader;
GRANT SELECT ON warehouses TO ai_reader;
GRANT SELECT ON categories TO ai_reader;
GRANT SELECT ON suppliers TO ai_reader;
GRANT SELECT ON products TO ai_reader;
GRANT SELECT ON price_history TO ai_reader;
GRANT SELECT ON promotions TO ai_reader;
GRANT SELECT ON inventory TO ai_reader;
GRANT SELECT ON customers TO ai_reader;
GRANT SELECT ON delivery_addresses TO ai_reader;
GRANT SELECT ON orders TO ai_reader;
GRANT SELECT ON order_lines TO ai_reader;
GRANT SELECT ON shipments TO ai_reader;
GRANT SELECT ON shipment_lines TO ai_reader;
GRANT SELECT ON delivery_events TO ai_reader;
GRANT SELECT ON claims TO ai_reader;
GRANT SELECT ON claim_lines TO ai_reader;
GRANT SELECT ON product_current_prices TO ai_reader;
GRANT SELECT ON late_shipments TO ai_reader;
GRANT SELECT ON open_claims TO ai_reader;
