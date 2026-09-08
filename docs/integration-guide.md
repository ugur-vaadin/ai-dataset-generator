# Integration guide: using the dataset in the demo application

Code-level wiring for a Spring Boot + Vaadin Flow application. All snippets assume Java 21,
Spring Boot 3/4 and the `vaadin-ai-components-flow` modules (`DatabaseProvider`,
`GridAIController`, `ChartAIController`, `FormAIController`). Adjust package names to taste.

## 1. Files to copy

| From `out/nordic_supply/` | To |
|---|---|
| `csv/*.csv` | `src/main/resources/data/` |
| `sql/schema-h2.sql` | `src/main/resources/schema.sql` |
| `sql/load-h2-classpath.sql` | `src/main/resources/data.sql` (or keep the name and point the property at it) |
| `sql/readonly-user-h2.sql` | `src/main/resources/readonly-user.sql` |
| `sql/pii-columns.json` | `src/main/resources/pii-columns.json` (drives the masking step) |
| `sql/ai-schema-h2.txt` | `src/main/resources/ai-schema.txt` |
| `documents/emails/*`, `documents/photos/*` | `src/main/resources/demo-documents/` |

### Alternative: ship the database file

`python3 -m dsgen nordic_supply check --h2-file` writes `out/nordic_supply/db/nordic_supply.mv.db`
with schema, data and the `ai_reader` user already in place. Copy it and use
`jdbc:h2:file:./db/nordic_supply` — no CSV load at startup. Regenerate the file when the data changes.

### Alternative: PostgreSQL

`sql/schema-postgres.sql`, `sql/load-postgres.sql` (psql `\copy`), `sql/readonly-user-postgres.sql`
and `sql/ai-schema-postgres.txt` are the same artefacts for PostgreSQL; `check --pg` proves them
against a container. In a Spring Boot app, load with Flyway/Liquibase plus a CSV import step, or run
the loader once against the database with `psql`.

## 2. Two data sources: the application's and the AI's

```properties
# application.properties
spring.datasource.url=jdbc:h2:mem:nordic;DB_CLOSE_DELAY=-1
spring.datasource.username=sa
spring.datasource.password=
spring.sql.init.mode=always
spring.sql.init.schema-locations=classpath:schema.sql
spring.sql.init.data-locations=classpath:data.sql,classpath:readonly-user.sql

# the AI connects as the read-only user created by readonly-user.sql
demo.ai.datasource.url=${spring.datasource.url}
demo.ai.datasource.username=ai_reader
demo.ai.datasource.password=ai_reader

# the demo's "today" — must match manifest.json's as_of (see section 6)
demo.as-of=2026-09-07
```

```java
@Configuration
public class AiDataSourceConfig {

    @Bean
    @Qualifier("aiDataSource")
    DataSource aiDataSource(
            @Value("${demo.ai.datasource.url}") String url,
            @Value("${demo.ai.datasource.username}") String user,
            @Value("${demo.ai.datasource.password}") String password) {
        var ds = new org.springframework.jdbc.datasource.DriverManagerDataSource(url, user, password);
        ds.setDriverClassName("org.h2.Driver");
        return ds;
    }
}
```

`ai_reader` has `SELECT` on the exposed tables and the three views only. It cannot read
`customer_contacts`, `saved_widgets` or `activity_log`, and it cannot write. The H2 smoke test in
`python3 -m dsgen nordic_supply check` proves both.

## 3. The `DatabaseProvider` (case 1)

```java
public class NordicSupplyDatabaseProvider implements DatabaseProvider {

    private final transient DataSource readOnly;
    private final String schemaText;      // sql/ai-schema-h2.txt
    private final Clock clock;            // frozen to demo.as-of, see section 6

    public NordicSupplyDatabaseProvider(DataSource readOnly, String schemaText, Clock clock) {
        this.readOnly = readOnly;
        this.schemaText = schemaText;
        this.clock = clock;
    }

    @Override
    public String getSchema() {
        // The generated text says "The application tells you today's date" — this is where.
        return schemaText + "\nToday is " + LocalDate.now(clock) + ".\n";
    }

    @Override
    public List<Map<String, Object>> executeQuery(String sql) {
        try (var conn = readOnly.getConnection();
             var stmt = conn.createStatement();
             var rs = stmt.executeQuery(sql)) {
            var meta = rs.getMetaData();
            var rows = new ArrayList<Map<String, Object>>();
            while (rs.next()) {
                var row = new LinkedHashMap<String, Object>();
                for (int i = 1; i <= meta.getColumnCount(); i++) {
                    row.put(meta.getColumnLabel(i), rs.getObject(i));
                }
                rows.add(row);
            }
            return rows;
        } catch (SQLException e) {
            // Relayed to the model so it can fix its query. H2 messages name columns and
            // tables, never row values — safe here; re-check for another database.
            throw new ToolException("Query failed: " + e.getMessage(), e);
        }
    }
}
```

Load the text once (`new String(getClass().getResourceAsStream("/ai-schema.txt").readAllBytes(), UTF_8)`)
and create one provider per widget (each widget has its own `AIOrchestrator` and controller).

Because `CURRENT_DATE` inside H2 is the real clock, the `product_current_prices` view and any
`CURRENT_TIMESTAMP` arithmetic the model writes follow real time, not `demo.as-of`. Either keep
the two equal (regenerate before the demo) or tell the model in the schema text to use the literal
date you append instead of `CURRENT_DATE`. See section 6.

## 4. Saved widgets

`saved_widgets` shows the shape: owner, title, a plain-English `description` ("orders shipped
after the promised ship date, August 2026, by week"), the `query_sql` the widget runs, and
`state_json` for the controller's state. Persist the controller state from the listener:

```java
gridController.addStateChangeListener(state ->
        widgetRepository.saveState(widgetId, objectMapper.writeValueAsString(state)));
```

and restore with `restoreState(...)` when the dashboard opens. Asking the model for the
description is the application's job (component gap in the business-case document): send a
follow-up prompt "describe in one sentence, in business terms, what this widget contains and what
was counted" and store the answer with the widget.

## 5. Claim form lookups (case 2)

The form's selection fields must search the live data; a combo box with 2,400 customers cannot
be handed to the model (200-option cap). Register query callbacks:

```java
controller.fieldValueOptions(ValueOptions.forField(customerField)
        .options((filter, limit) -> customerRepository.search(filter, limit)));  // name, number, city, contact e-mail

controller.fieldValueOptions(ValueOptions.forField(orderField)
        .options((filter, limit) -> orderRepository.searchForCustomer(customerField.getValue(), filter, limit)));
        // order_number, customer_reference, delivered date ("Tuesday"), product names on the lines

controller.fieldValueOptions(ValueOptions.forField(orderLineField)
        .options((filter, limit) -> orderLineRepository.searchForOrder(orderField.getValue(), filter, limit)));
        // product name, SKU, pallet number via shipment_lines

controller.fieldValueOptions(ValueOptions.forField(claimTypeField)
        .options(List.of(ClaimType.values())));   // DAMAGED, MISSING_ITEMS, WRONG_ITEM, LATE_DELIVERY, QUALITY_DEFECT, PRICING_DISPUTE, RETURN_REQUEST
```

Useful search predicates the data supports: `customer_contacts.email = sender`,
`customers.name ILIKE`, `orders.customer_id = ? AND shipments.delivered_at BETWEEN ...`,
`shipment_lines.pallet_number = 2`. Sections per claim type (pallet number only for DAMAGED,
promised vs. actual dates for LATE_DELIVERY, invoiced vs. expected price for PRICING_DISPUTE) are
plain `setVisible()` on the form layout; the controller only sees visible fields.

Personal data: the e-mails contain names, phone numbers and one personal mobile. The masking step goes
into a `RequestInterceptor` registered on the orchestrator: it receives the request before it leaves and can
rewrite the user message with `setUserMessage(...)` (the prompt-preprocessing hook the business-case document
asked for; it exists in the AI core module). `sql/pii-columns.json` lists the columns and classes to mask.

## 6. Freezing "today"

Everything in the data is relative to `manifest.json → as_of`. Two ways to keep the story valid:

* **Regenerate** before each demo/release: `python3 -m dsgen nordic_supply check --as-of <today>`
  and copy `out/` again. Cheap and honest; the numbers in `FACTS.md` change.
* **Freeze the clock**: `@Bean Clock demoClock(@Value("${demo.as-of}") LocalDate d) { return Clock.fixed(d.atStartOfDay(ZoneId.of("Europe/Helsinki")).toInstant(), ZoneId.of("Europe/Helsinki")); }`
  and use it in the provider (section 3), in the claim form's date defaults, and in the activity
  log. Append `Today is <date>.` to the schema text and add the hint "use this date instead of
  CURRENT_DATE" so the model's SQL follows the frozen clock.

## 7. Case 3: applying a bulk price change

A proposal row is (product, current list price, new price, effective 1st of next month).
Applying the accepted rows, in one transaction:

```sql
UPDATE price_history SET valid_to = DATEADD('DAY', -1, DATE '2026-10-01')
 WHERE product_id = ? AND valid_to IS NULL;
INSERT INTO price_history (id, product_id, list_price, currency, valid_from, valid_to, reason, created_by, created_at)
VALUES (NEXT VALUE FOR price_history_seq, ?, ?, 'EUR', DATE '2026-10-01', NULL, 'Supplier increase (bulk change #?)', ?, CURRENT_TIMESTAMP);
```

(create a sequence starting above `MAX(id)` at startup, or switch the column to an identity
column in `schema.sql`). Record each row in `bulk_change_items` with the new `price_history_id`;
undo deletes those rows and sets the previous rows' `valid_to` back to NULL. The 25 products of
other suppliers that already carry a scheduled row are the edge case to show: a second future row
for the same product needs the manager's decision.

## 8. Activity log

`activity_log` columns map to the hooks: `RequestListener` (prompt, prompt_sent, data_scope),
`ResponseListener` (`ResponseEvent.getMetadata()` → finish reason and token usage; `ResponseMetadata` carries
no model name, so take `model_name` from the provider you configured),
controller state-change listeners (proposal, decision), form validation rejections
(rejection_rule). One row per turn, `user_id` from the signed-in user.
