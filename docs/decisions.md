# Decisions

- payments.kind: maps to existing `payment_type` (advance/full/balance already in PaymentType) because same meaning.
- payments.reference: maps to `reference_number`; made UNIQUE via partial index (WHERE NOT NULL) because cash has no reference.
- payments.received_by: maps to `recorded_by` because same meaning.
- orders "waiting-for-payment": maps to `OrderStatus.PENDING_PAYMENT` because same meaning; confirmed/dispatched/cancelled already existed.
- dispatch PICK: maps to `DispatchStatus.DRAFT` (server default) because it is the pick-list stage; `packed` stays unused.
- serialized_units serial: maps to `serial_number`; existing index made unique instead of adding a second index because one unique index covers both.
- serial "shipped": maps to `SerialUnitStatus.DISPATCHED` because same meaning.
- inventory quantity >= 0: maps to `quantity_on_hand` CHECK because already there.
- stock_movements: quantity -> `quantity_delta`, created_by -> `performed_by`, type in/out -> `reason` purchase/dispatch; added `service` value because no existing reason meant a service-ticket part.
- products.requires_serial: maps to `tracks_serial` because same meaning.
- support ticket: number -> `ticket_number`, serialized_unit_id -> `faulty_serial_unit_id`, description -> `issue_description`, is_under_warranty -> `under_warranty`, customer_confirmed_by_name -> `confirmed_by_name`, closed_at -> `customer_confirmed_at` because CLOSED means "customer confirmed it works".
- support ticket money columns: added with spec names (`parts_subtotal`, `labour_amount`, `gst`, `total`) NUMERIC(12,2) default 0 because none existed.
- ticket parts lines: map to `ticket_charges` rows with `charge_type='part'`; qty -> `quantity`, unit_price snapshot -> `customer_price` because the table already stores per-ticket part lines.
- dashboard_share_links.period: plain VARCHAR(20) without enum CHECK because no period enum exists yet.
- tests/test_model_registry.py: added `dashboard_share_links` to EXPECTED_TABLES because the spec adds that table and the test lists every table.
- compose: ran db with a scratch override `ports: !reset []` because host port 5432 is used by another project; repo compose files unchanged.
- quotes notes: stored in `quotes.terms` because quotes has no notes column and terms is the free-text field shown on the quote.
- quote reject reason: kept only in the `quote.rejected` audit entry (`new_data.reason`) because quotes has no reason column.
- quote/order number: inserted with a temporary unique value, then set to `QT-{id:06d}` / `ORD-{id:06d}` in the same transaction because the column is NOT NULL and the pattern needs the id (same pattern as ENQ-{id:06d}).
- quote line_total: qty x unit_price before GST, plus a separate `gst_amount` per line, because the spec computes GST per line and sums the quantized lines.
- solar_packages.base_price: seeded as the sum of component sale prices (preview only; quotes always snapshot live product prices) because the column is NOT NULL.
- GET /packages lives in the catalog router without a /catalog prefix because the spec path is /packages; price preview logic sits in services/catalog.py so the router does no DB work.
- quote accept: sets the enquiry to `converted` (+ `enquiry.converted` audit) because P1-1 asks for it (replaces the earlier "no change" decision).
- 409 codes: SURVEY_NOT_APPROVED, PACKAGE_NOT_AVAILABLE, QUOTE_STATUS_INVALID, ORDER_ALREADY_EXISTS.
- P1-1 installation job: uses `planned` with `scheduled_at=NULL` because it is the existing unscheduled state; pick lists use `draft` and `DSP-{id:06d}`.
- P1-1 idempotency: reject a key belonging to another order with `IDEMPOTENCY_KEY_REUSED` because replay must never mix payment and order records.
- P1-2 service lines: show installation services in dispatch detail but exclude them from stock seeding, stock deductions, and stock movements because service products are never stocked.
- P1-2 warranties: use the product's current `warranty_months` at delivery because the task explicitly specifies product warranty duration; start dates use the delivery timestamp in Asia/Kolkata.
- P1-2 seed stock: insert missing rows only, preserving existing balances and serial statuses, because rerunning the seed must not replenish sold stock.
- P1-2 delivery: also moves the order to `delivered` with an audit entry because subsequent installation and invoice workflows depend on delivery state.
- P1-3 serialized replacement parts remain roadmap; repair parts must be non-serialized stock products because unit swaps need their own warranty and serial workflow.
- P1-3 warranty charges store customer_price=0, while retaining quantities, hours and internal part costs, because the existing warranty_covered_no_customer_charge CHECK requires zero customer prices. Billable prices and GST rates are snapshotted in the resolution audit.
- P1-3 reopened repairs retain previous charges and add each subsequent visit's parts, hours and totals because stock already consumed and work already done must not disappear; total labour hours are limited to the existing NUMERIC(5,2) column.
- P1-3 dashboard reports from IST period start to now; unfinished installation and open repair queues span all periods because unresolved work must remain visible. Installed/completed/cancelled orders are excluded from unfinished installations.
- P1-3 share creation returns its id alongside url and expires_at because the director needs that id to revoke the link; raw tokens are never stored or audited.
- P1-3 support units without an active, non-voided warranty show expired with zero days_left (warranty_end may be null) because the API allows only active/expired coverage labels.

P3-2: Retain the existing Compose service name web; Caddy proxies to web:80 because it already hosts Nginx.
P3-2: ENVIRONMENT takes precedence over legacy ENV; production disables CORS and development permits only localhost:5173.
P3-2: Upgrade FastAPI to permit patched Starlette 1.3.1; pin PyJWT 2.14.0 and python-multipart 0.0.30 to fix high/critical advisories, retaining medium/low findings per task scope.
P3-2: Add frontend Node type definitions and a lockfile because the existing Vite configuration uses process and production requires npm ci.
- installation job statuses: spec UNSCHEDULED -> `planned` (server default), SCHEDULED / IN_PROGRESS / COMPLETED -> same names, because same meaning.
- installation_jobs.scheduled_date: stored in `scheduled_at` as 00:00 Asia/Kolkata of that date because the column exists and GET /orders already reads it as an IST date; no second date column.
- installation_jobs: finished_at -> `completed_at`, system_kw -> `installed_capacity_kw`, signer_name -> `signed_by_name` (+ `signed_at`) because same meaning.
- job_technicians: user_id -> `technician_id`, hours -> `hours_worked` NUMERIC(7,2), hourly_cost -> `hourly_rate` snapshot because same meaning; a technician with no hourly_rate is booked at 0.00 because the column is NOT NULL.
- installation_evidence: kind -> `evidence_type`, size_bytes -> `file_size_bytes` because same meaning.
- storage: added `save_bytes(content, ext)` / `open_bytes(key)` to app/storage/file_storage.py (keys `yyyy/mm/<uuid4>.<ext>`) because the old `save_file` uses the upload's filename and Content-Type header, which the spec forbids; `save_file` left untouched.
- double booking: technician user rows are locked FOR UPDATE (id order) while checking because two parallel bookings on different jobs would otherwise both pass.
- complete: order -> `completed` when already fully paid, else `installed`, because enums.py defines completed = installed + fully paid.
- GET /installation-jobs/{id} crew shows name + hours, not hourly rate, because technicians can open it and rates are cost data.
- GET /schedule returns Page[ScheduleRow] (default page_size 50, range max 62 days) because list endpoints use Page.
- signature_png_base64 may carry a `data:image/png;base64,` prefix (stripped) because canvas.toDataURL() produces it.
- 409 codes: JOB_NOT_SCHEDULABLE, TECHNICIAN_DOUBLE_BOOKED, JOB_STATUS_INVALID, MATERIAL_NOT_DELIVERED, PHOTO_LIMIT_REACHED, PHOTO_REQUIRED; 413 FILE_TOO_LARGE; 422 FILE_TYPE_NOT_ALLOWED, SIGNATURE_INVALID.
