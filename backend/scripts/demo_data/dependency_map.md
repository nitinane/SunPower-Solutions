# Demo data dependency map

This map was prepared from the registered SQLAlchemy models in
`backend/app/models/__init__.py` before writing seed records. Parent tables are
listed before the tables that reference them. Composite foreign keys are noted
where they affect record pairing.

## Insert order

| Phase | Tables | Required parent links |
| --- | --- | --- |
| 1. Reference data | `products`, `solar_packages`, `users` | None |
| 2. Catalogue stock | `inventory`, `package_components`, `serialized_units` | `inventory` and `serialized_units` → products; `package_components` → packages and products |
| 3. Customer journey | `customers`, `sites`, `enquiries`, `site_surveys`, `quotes`, `quote_items` | Customer → creator; site → customer; enquiry → customer/site/assignees; survey → enquiry/site/surveyor/reviewer; quote → enquiry/survey/package/creator; quote item → quote/product |
| 4. Orders | `orders`, `order_items` | Order → customer/site/accepted quote/creator; order item → order+quote, quote item+quote+product, and product |
| 5. Fulfillment | `dispatches`, `dispatch_items`, `installation_jobs`, `job_technicians`, `installation_evidence` | Dispatch → order/warehouse user; dispatch item → dispatch, order item+matching product, product, and optional serialized unit+matching product; job → order+matching site; assignments/evidence → job and users |
| 6. Stock and warranty | `stock_movements`, `warranties` | Movement → product/optional order/actor; warranty → order item+matching order+product and optional serialized unit+matching product |
| 7. Service | `support_tickets`, `ticket_charges`, `ticket_work_logs` | Ticket → customer+matching site, optional warranty/serial/assignee; charge → ticket/product/optional replacement serial+matching product; work log → ticket/technician |
| 8. Billing and finance | `invoices`, `invoice_items`, `payments`, `subsidy_applications`, `technician_payments`, `audit_log` | Invoice → exactly one order or ticket; invoice item → invoice; payment → exactly one order or ticket/recorder; subsidy → customer+matching site/optional order; technician payment → job/technician; audit → actor |

## Complete foreign-key map

| Table | Depends on |
| --- | --- |
| `users` | — |
| `products` | — |
| `solar_packages` | — |
| `audit_log` | `users` |
| `customers` | `users` |
| `inventory` | `products` |
| `package_components` | `products`, `solar_packages` |
| `serialized_units` | `products` |
| `sites` | `customers` |
| `enquiries` | `customers`, `sites`, `users` |
| `site_surveys` | `enquiries`, `sites`, `users` |
| `quotes` | `enquiries`, `site_surveys`, `solar_packages`, `users` |
| `orders` | `customers`, `quotes`, `sites`, `users` |
| `quote_items` | `products`, `quotes` |
| `dispatches` | `orders`, `users` |
| `installation_jobs` | `orders`, `users` |
| `order_items` | `orders`, `products`, `quote_items` |
| `stock_movements` | `orders`, `products`, `users` |
| `subsidy_applications` | `customers`, `orders`, `sites` |
| `dispatch_items` | `dispatches`, `order_items`, `products`, `serialized_units` |
| `installation_evidence` | `installation_jobs`, `users` |
| `job_technicians` | `installation_jobs`, `users` |
| `technician_payments` | `installation_jobs`, `users` |
| `warranties` | `order_items`, `orders`, `products`, `serialized_units` |
| `support_tickets` | `customers`, `serialized_units`, `sites`, `users`, `warranties` |
| `invoices` | `orders`, `support_tickets` |
| `payments` | `orders`, `support_tickets`, `users` |
| `ticket_charges` | `products`, `serialized_units`, `support_tickets` |
| `ticket_work_logs` | `support_tickets`, `users` |
| `invoice_items` | `invoices` |

`dashboard` is not a persistent table. `files` has no table; evidence metadata
is stored in `installation_evidence`.
