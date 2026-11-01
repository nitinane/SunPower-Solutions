# SunPower Solutions — Initial PostgreSQL schema

This schema is the first implementation of the agreed 30-table design. It uses PostgreSQL 16 and SQLAlchemy 2.x synchronous ORM models. No seed data or business workflows are included.

## Tables by domain

| Domain | Tables |
|---|---|
| Identity and audit | `users`, `audit_log` |
| Customer and enquiry | `customers`, `sites`, `enquiries`, `site_surveys` |
| Catalog and quotes | `products`, `solar_packages`, `package_components`, `quotes`, `quote_items` |
| Orders and billing | `orders`, `order_items`, `payments`, `invoices`, `invoice_items` |
| Warehouse and dispatch | `inventory`, `stock_movements`, `serialized_units`, `dispatches`, `dispatch_items` |
| Installation and warranty | `installation_jobs`, `job_technicians`, `installation_evidence`, `warranties` |
| Service | `support_tickets`, `ticket_charges`, `ticket_work_logs` |
| Finance extensions | `subsidy_applications`, `technician_payments` |

`dashboard` is a query/projection domain, not a persistent table. File bytes live under `STORAGE_DIR`; `installation_evidence.storage_key` stores the relative key. No public file URL or image blob is stored in PostgreSQL.

## Integrity rules implemented

- Domain values are centralized in `backend/app/core/enums.py`; string CHECK constraints are built with `sql_in("column", DomainEnum)` (and `sql_not_in` for reviewed survey states). Status columns stay SQL `String` columns. `EnquirySource` includes `whatsapp`, `OrderStatus` includes `installed` and `completed`, and package, product, and payment-type values match the problem statement.
- Enquiries retain the originally submitted address and system requirements. These fields remain on the enquiry even when a `Site` is created after qualification.
- Technician assignment rows store required `hours_worked` and an `hourly_rate` snapshot copied from the user rate at assignment time. Subsequent edits to `users.hourly_rate` do not change the snapshot.
- Installation completion, support confirmation, ticket part quantity, and subsidy JSONB document checklist fields are stored on their owning records.

- `users.email` is normalized to lowercase/trimmed and has a case-insensitive unique index.
- User roles, workflow statuses, categories, payment methods, and evidence types use `CHECK` constraints.
- Customer phone numbers are normalized to E.164, indexed but deliberately **not unique** because a family may share a phone number.
- `enquiries` can exist without a `customer_id`; raw and normalized phone values are kept separately.
- Composite foreign keys ensure a survey belongs to the enquiry/site pair, a quote uses a survey from the same enquiry, and a site attached to an order/ticket/subsidy belongs to the stated customer.
- Quote and order line items retain SKU/name, quantity, prices, GST, and warranty-period snapshots.
- A payment and an invoice must reference exactly one parent: an order or a support ticket.
- Payment idempotency keys are required and unique.
- Inventory quantities cannot go below zero or have more reserved than on hand. The atomic reservation itself remains a service/repository transaction.
- Serial numbers are uppercase and trimmed, unique per product, and separately indexed for scanner lookup.
- Dispatch line composite FKs make the scanned unit's product match the order line's product; serialized quantities must equal one.
- Warranty rows support either a serialized unit or a bulk quantity. Warranty status is intentionally derived from dates and `voided_at`, not stored as a stale status field.
- Ticket charges distinguish part/labour, internal cost, customer price, warranty coverage, and replacement serial unit.
- Audit records use PostgreSQL `JSONB` for old/new snapshots.

## Application-level rules still required

Database constraints cannot replace authorization or multi-step business validation. FastAPI must still:

1. Verify the authenticated user is allowed to access the customer, site, order, job, ticket, or file (prevent IDOR).
2. Enforce role requirements such as technician-only assignments and surveyor/reviewer permissions.
3. Normalize user/email/phone/serial values before writes.
4. Reserve/release stock with one atomic conditional `UPDATE` inside a transaction and append a matching `stock_movements` row in that same transaction.
5. Enforce state transitions (for example, dispatched to delivered only once), generate warranties after confirmed delivery, and use idempotency keys for retried operations.
6. Calculate totals and copy quote/product snapshots server-side; never trust prices, customer IDs, product IDs, or warranty periods supplied by the browser.
7. Authorize access to `storage_key` before returning a file or streaming its bytes.

## Generate and apply the first migration

Run from the project root in PowerShell after copying this model update into the project:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -w /app api alembic revision --autogenerate -m "initial solar schema"
```

Review the generated file under `backend/alembic/versions/`. Check that it creates all 30 tables, indexes, foreign keys, and constraints. Then apply it:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec -w /app api alembic upgrade head
```

Verify in PostgreSQL:

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml exec db psql -U sunpower -d sunpower -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;"
```

Do not run `docker compose down -v`; it deletes the persistent Postgres volume.
