-- Read-only role for the AI's DatabaseProvider (PostgreSQL syntax).
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_reader') THEN
  CREATE ROLE ai_reader LOGIN PASSWORD 'ai_reader'; END IF; END $$;
GRANT USAGE ON SCHEMA public TO ai_reader;
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
GRANT SELECT ON return_authorisations TO ai_reader;
GRANT SELECT ON return_lines TO ai_reader;
GRANT SELECT ON credit_notes TO ai_reader;
GRANT SELECT ON stock_movements TO ai_reader;
GRANT SELECT ON product_current_prices TO ai_reader;
GRANT SELECT ON late_shipments TO ai_reader;
GRANT SELECT ON open_claims TO ai_reader;
GRANT SELECT ON staff TO ai_reader;
