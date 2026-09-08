-- Load the CSV files into H2 with CSVREAD. Run after schema-h2.sql.
-- CSV directory: ./datasets/nordic_supply/csv (regenerate with --csv-path-prefix to point elsewhere).
-- Empty CSV fields become NULL. Column order in the CSVs matches the CREATE TABLE statements.
INSERT INTO users SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/users.csv', NULL, 'charset=UTF-8');
INSERT INTO warehouses SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/warehouses.csv', NULL, 'charset=UTF-8');
INSERT INTO categories SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/categories.csv', NULL, 'charset=UTF-8');
INSERT INTO suppliers SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/suppliers.csv', NULL, 'charset=UTF-8');
INSERT INTO products SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/products.csv', NULL, 'charset=UTF-8');
INSERT INTO price_history SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/price_history.csv', NULL, 'charset=UTF-8');
INSERT INTO promotions SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/promotions.csv', NULL, 'charset=UTF-8');
INSERT INTO inventory SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/inventory.csv', NULL, 'charset=UTF-8');
INSERT INTO customers SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/customers.csv', NULL, 'charset=UTF-8');
INSERT INTO customer_contacts SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/customer_contacts.csv', NULL, 'charset=UTF-8');
INSERT INTO delivery_addresses SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/delivery_addresses.csv', NULL, 'charset=UTF-8');
INSERT INTO orders SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/orders.csv', NULL, 'charset=UTF-8');
INSERT INTO order_lines SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/order_lines.csv', NULL, 'charset=UTF-8');
INSERT INTO shipments SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/shipments.csv', NULL, 'charset=UTF-8');
INSERT INTO shipment_lines SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/shipment_lines.csv', NULL, 'charset=UTF-8');
INSERT INTO delivery_events SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/delivery_events.csv', NULL, 'charset=UTF-8');
INSERT INTO claims SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/claims.csv', NULL, 'charset=UTF-8');
INSERT INTO claim_lines SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/claim_lines.csv', NULL, 'charset=UTF-8');
INSERT INTO saved_widgets SELECT * FROM CSVREAD('./datasets/nordic_supply/csv/saved_widgets.csv', NULL, 'charset=UTF-8');
