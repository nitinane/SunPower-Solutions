# API changelog (for the frontend)

All paths are under `/api/v1`. Auth is the session cookie. `admin` is always allowed in addition to the listed roles.
Money fields are JSON strings (e.g. `"12345.00"`). Errors: `{"error": {"code", "message", "fields"}}`.
Common errors on every endpoint: 401 `unauthorized` (not logged in), 403 `forbidden` (wrong role), 422 `validation_error`.

## P1-1

All paths below use `/api/v1`; admin is also allowed. Money is sent as decimal strings.

### Shapes
- `PaymentRead`: `id`, `order_id`, `amount`, `kind` (`advance|full|balance`), `method`, `reference` (nullable), `paid_at`, `received_by` (nullable user id), `created_at`.
- `OrderSummary`: `id`, `order_number`, `status`, `customer_name`, `customer_phone`, `total`, `amount_paid`, `balance_due`, `created_at`.
- `OrderRead`: `id`, `order_number`, `quote_id`, `status`, `customer {id,name,phone,email}`, `site {id,address_line1,address_line2,city,state,pincode}`, `items [{id,product_id,sku,name,qty,unit_price,line_total,requires_serial}]`, `subtotal`, `gst`, `total`, `amount_paid`, `balance_due`, `payments: PaymentRead[]`, `pick_list {id,status}|null`, `installation_job {id,status,scheduled_date}|null`, `confirmed_at`, `created_at`, `updated_at`. Line totals exclude GST. Paid and balance amounts use SQL SUM. Initial pick list status is `draft`; initial installation job status is `planned`, with null scheduled date.

### POST /orders/{order_id}/payments
- Roles: office, director.
- Optional header: `Idempotency-Key` (max 100 characters); reuse returns the existing payment with 200.
- Body: `{amount: positive Decimal (max 2 decimal places), method: PaymentMethod, reference?: string|null, paid_at?: datetime|null}`. Reference required for every method except cash; paid_at defaults to now. Client cannot set kind.
- Response 201 (200 for replay): `{payment: PaymentRead, order: OrderRead}`. First payment confirms order and creates one pick list and one unscheduled installation job atomically. Later payments create neither.
- Errors: 404 `not_found`; 409 `ORDER_NOT_PAYABLE`, `OVERPAYMENT`, `DUPLICATE_PAYMENT_REFERENCE`, `IDEMPOTENCY_KEY_REUSED` (key belongs to another order); 422 `validation_error`.

### GET /orders
- Roles: office, manager, director. No body.
- Query: optional `status`, `search` (order number/customer name/phone), `page=1`, `page_size=20` (max 100).
- Response 200: `Page[OrderSummary]` with newest orders first. Common errors only.

### GET /orders/{order_id}
- Roles: office, manager, warehouse, director. No body.
- Response 200: `OrderRead`. Error: 404 `not_found`, plus common errors.

### POST /enquiries/{enquiry_id}/qualification (changed)
- Roles: office, director (existing).
- Body: `{outcome: qualified|unqualified|contacted, shadow_free_roof_area_sqft?: Decimal|null, monthly_bill_amount?: Decimal|null, grid_connection_suitable?: bool|null, notes?: string|null}`. When outcome is qualified, all three call checks are required; missing values return 422 with an entry in `error.fields` for each missing check. Zero bill and false suitability count as supplied; suitability must still be true to qualify.
- Response 200: existing `EnquiryRead`, including status and call checks. Existing 404 `not_found`, 409 `business_rule_violation`, and common errors remain.

### POST /quotes/{quote_id}/accept (changed)
- Roles: office, director. No body.
- Response 200 unchanged: `{quote: QuoteRead, order_id}`. Also sets enquiry status to `converted` and records `enquiry.converted` in the same transaction.
- Errors unchanged: 404 `not_found`; 409 `ORDER_ALREADY_EXISTS`, `QUOTE_STATUS_INVALID`; common errors.

## P1-0

### Shared shapes
- `PriceLine`: `product_id`, `sku`, `name`, `category` (nullable), `qty`, `unit_price`, `gst_percent`, `line_total` (qty x unit_price, before GST), `gst_amount`.
- `QuoteRead` (printable quote): `id`, `quote_number` (`QT-000001`), `enquiry_id`, `survey_id`, `package_id`, `status` (`draft|sent|accepted|rejected|expired|cancelled`), `customer {id, name, phone, email}`, `site {id, address_line1, address_line2, city, state, pincode}`, `lines: PriceLine[]`, `subtotal`, `gst`, `total`, `notes`, `valid_until` (date), `created_at`, `updated_at`.
- `QuoteSummary` (list row): `id`, `quote_number`, `enquiry_id`, `survey_id`, `package_id`, `status`, `subtotal`, `gst`, `total`, `created_at`, `updated_at`.
- `Page[T]`: `items`, `total`, `page`, `page_size`.

### GET /packages
- Roles: office, director.
- Query: `package_type` (optional, PackageType), `kw` (optional, 0 < kw <= 100).
- Response 200: `PackageRead[]` — `id`, `name`, `package_type`, `kw`, `is_active`, `components: PriceLine[]`, `subtotal`, `gst`, `total` (price preview from live product prices).

### POST /quotes
- Roles: office, director.
- Body: `{"survey_id": int, "package_id": int, "include_installation": bool = false, "notes": string|null (max 5000)}`.
- Response 201: `QuoteRead` (status `draft`, lines copied from the package with frozen prices).
- Errors: 404 `not_found` (survey), 409 `SURVEY_NOT_APPROVED`, 409 `PACKAGE_NOT_AVAILABLE` (package inactive/missing, or installation service unavailable).

### GET /quotes
- Roles: office, director.
- Query: `status` (optional), `enquiry_id` (optional), `page` (default 1), `page_size` (default 20, max 100).
- Response 200: `Page[QuoteSummary]`.

### GET /quotes/{quote_id}
- Roles: office, director.
- Response 200: `QuoteRead`. Errors: 404 `not_found`.

### POST /quotes/{quote_id}/send
- Roles: office, director. No body. `draft -> sent`.
- Response 200: `QuoteRead`. Errors: 404 `not_found`, 409 `QUOTE_STATUS_INVALID`.

### POST /quotes/{quote_id}/accept
- Roles: office, director. No body. `sent -> accepted`, creates the order (status `pending_payment`).
- Response 200: `{"quote": QuoteRead, "order_id": int}`.
- Errors: 404 `not_found`, 409 `QUOTE_STATUS_INVALID`, 409 `ORDER_ALREADY_EXISTS`.

### POST /quotes/{quote_id}/reject
- Roles: office, director. Body: `{"reason": string (3–500)}`. `sent -> rejected`.
- Response 200: `QuoteRead`. Errors: 404 `not_found`, 409 `QUOTE_STATUS_INVALID`.

## P1-2

All endpoints below use `/api/v1` and allow warehouse, director, and admin. Errors use the existing error envelope. Common errors: 401 `unauthorized`, 403 `forbidden`, 404 `not_found` for missing dispatch/item, 422 `validation_error`.

### Shapes
- `DispatchRead`: `id`, `dispatch_number`, `order_id`, `order_number`, `customer {id,name,phone,email}`, `site {id,address_line1,address_line2,city,state,pincode}`, `status`, `lines`, `dispatched_at`, `delivered_at`, `receiver_name`, `created_at`.
- Each line: `{order_item_id,sku,name,qty,requires_serial,scanned,serials:[{dispatch_item_id,serialized_unit_id,serial}]}`. `qty` is a decimal string; `scanned` is an integer count of scanned units. Non-serial/service lines have no serial scans. Use `dispatch_item_id` to undo a scan.
- Dispatch status flow: `draft` (pick list) -> `dispatched` -> `delivered`.
- `WarrantyRead`: `{id,order_id,order_item_id,product_id,serialized_unit_id,quantity,start_date,end_date}`. Quantity is a decimal string, dates are ISO dates; serialized_unit_id is null for bulk warranties.

### GET /dispatches
- No body. Query: optional `status`, `page=1`, `page_size=20` (max 100).
- Response 200: `Page[DispatchRead]`, oldest first. Common errors only.

### GET /dispatches/{id}
- No body. Response 200: `DispatchRead`. Common errors only.

### POST /dispatches/{id}/scan
- Body: `{serial: string}`. Spaces are removed and letters uppercased. Repeated scan on the same dispatch returns 200 with unchanged scans.
- Response 200: `DispatchRead` with updated lines.
- Errors: 404 `SERIAL_NOT_FOUND`; 409 `DISPATCH_LOCKED`, `SERIAL_WRONG_PRODUCT`, `LINE_ALREADY_COMPLETE`, `SERIAL_ALREADY_SHIPPED`, `SERIAL_NOT_IN_STOCK`; common errors.

### DELETE /dispatches/{id}/scan/{dispatch_item_id}
- No body. Draft dispatch only. Response 200: updated `DispatchRead`.
- Errors: 409 `DISPATCH_LOCKED`; common errors (404 if the scan does not belong to this dispatch).

### POST /dispatches/{id}/send
- No body. Response 200: `DispatchRead` with status `dispatched`; order also becomes `dispatched`.
- Requires all serial lines scanned and enough available non-serial stock. Deducts stock and records movements atomically; service lines consume no stock.
- Errors: 409 `DISPATCH_LOCKED`, `SCAN_INCOMPLETE` (message lists missing lines/counts), `INSUFFICIENT_STOCK` (names product), `SERIAL_ALREADY_SHIPPED`, `SERIAL_NOT_IN_STOCK`; common errors.

### POST /dispatches/{id}/deliver
- Body: `{receiver_name: string, delivered_at?: timezone-aware datetime|null}`. Defaults to now; blank receiver names and timezone-free timestamps return 422.
- Response 200: all `DispatchRead` fields plus `{warranties_created: integer, warranties: WarrantyRead[]}`. Order becomes `delivered`.
- Atomically creates one warranty per scanned serialized unit, or one per non-serial order line, for products with warranty_months > 0. Warranty dates start on the Asia/Kolkata delivery date; expiry adds calendar months and clamps to month end.
- Errors: 409 `ALREADY_DELIVERED`, `DISPATCH_LOCKED` (not dispatched); common errors.

## P1-3

All paths use `/api/v1`. Admin is allowed in addition to the roles below. Common errors on protected endpoints: 401 `unauthorized`, 403 `forbidden`, 404 `not_found` for missing records, 422 `validation_error`. Money is sent as strings. Dates are ISO dates; timestamps are UTC. Ticket lists use `Page[TicketRead]` (`items,total,page,page_size`).

### Ticket shapes
- `TicketRead`: `id,ticket_number,customer_id,site_id,faulty_serial_unit_id,order_item_id,warranty_id,status,priority,fault_code,issue_description,under_warranty,coverage_label,assigned_to,visit_date,work_notes,labour_hours,parts_subtotal,labour_amount,gst,total,opened_at,resolved_at,confirmed_by_name,customer_confirmed_at,charges,history`.
- Coverage label is `Under warranty – free` or `Out of warranty – billable`. Coverage is frozen at creation using the IST date, inclusive of the warranty end date. Voided warranties provide no coverage.
- Charge: `id,charge_type,product_id,description,quantity,customer_price,cost_amount,covered_by_warranty,amount`. `customer_price` is the unit price; `amount` is quantity × unit price before GST. Warranty customer prices and amounts are zero. Internal part cost is retained.
- History: existing audit-entry shape `{id,action,actor_user_id,actor_name,old_data,new_data,created_at}`; actor_name may be null. Flow: `open -> assigned -> resolved -> closed`; customer rejection returns `resolved -> open`.

### GET /support/search?q=
- Roles: support, office, director. No body; q required, 1–150 characters.
- Response 200: up to 10 results, each `{customer:{id,name,phone,email},sites:[{id,address_line1,address_line2,city,state,pincode}],orders:[{id,number,status}],units:[{serialized_unit_id,serial,product,warranty_end,warranty_status,days_left}],open_tickets:[{id,ticket_number,status}]}`.
- Phone variants normalize to E.164; otherwise exact normalized serial, then literal name prefix. Unit status is `active|expired`; days_left is nonnegative. Missing/voided warranty is expired, with null end if no warranty exists. Empty or unmatched search returns `[]`. Common errors only.

### POST /tickets
- Roles: support, office.
- Body: `{customer_id,serialized_unit_id?:int|null,order_item_id?:int|null,fault_code:string|null,issue_description:string,priority?:low|normal|high|urgent}`. Exactly one target required; serialized products must use serialized_unit_id. Target must belong to the customer.
- Response 201: `TicketRead`, numbered `TKT-{id:06d}`, status open, coverage set by the server. Common errors only.

### GET /tickets
- Roles: support, manager, director, technician. No body.
- Query: optional `status`, `assigned_to_me=false`, `page=1`, `page_size=20` (max 100).
- Response 200: `Page[TicketRead]`, newest first. Technicians always see their own assigned tickets, even when assigned_to_me=false. Common errors only.

### GET /tickets/{id}
- Roles: support, manager, director, technician (own only). No body.
- Response 200: `TicketRead` including charges and audit history. Common errors only.

### POST /tickets/{id}/assign
- Roles: support, manager.
- Body: `{technician_id:int,visit_date:date}`. Technician must be active with role technician.
- Response 200: `TicketRead`, status assigned. Errors: 409 `TICKET_STATUS_INVALID` (not open); common errors.

### POST /tickets/{id}/resolve
- Roles: support, assigned technician.
- Body: `{work_notes:string,labour_hours:Decimal,parts:[{product_id:int,qty:Decimal}]}`. Hours >=0 (max 2 decimal places); qty >0 (max 3 decimal places); duplicate products rejected. No serialized or service products as parts.
- Response 200: `TicketRead`, status resolved. Parts consume stock even under warranty. Billable repairs use product sale prices/GST and configured labour rate/GST, rounded per line. Reopened tickets retain earlier charges and add new work; total hours across visits must fit 999.99.
- Errors: 409 `TICKET_STATUS_INVALID`, `INSUFFICIENT_STOCK` (names product); common errors. Unauthorized technician gets 403. All changes roll back on failure.

### POST /tickets/{id}/confirm
- Roles: support, office.
- Body: `{confirmed:bool,customer_name:string,note?:string|null}`.
- Response 200: `TicketRead`. True closes and records the customer's name/time. False reopens and saves name/note in audit history. This is the only endpoint that closes tickets.
- Errors: 409 `TICKET_STATUS_INVALID` (not resolved); common errors.

### GET /dashboard/summary?period=today|week|month
- Roles: director. No body; default period month.
- Response 200: `{period,from_at,to_at,cards,profit_per_job,unfinished_jobs,open_repairs}`.
- `cards`: `{new_enquiries,orders_confirmed,payments_received,profit,unfinished_jobs,open_repairs}`. New enquiries counts records created in period; orders/profit use confirmed_at. Payments use completed payments paid in period. Profit covers all matching orders, even beyond the list limit.
- `profit_per_job`: at most 50 newest confirmed orders, each `{order_number,customer,system_kw,revenue,material_cost,labour_cost,profit,margin_percent}`. Revenue excludes GST; costs use order-item and crew-rate snapshots. All money/rates/percentages are strings.
- `unfinished_jobs`: `{order_number,customer,stage,days_open}[]`; excludes installed/completed/cancelled orders. `open_repairs`: `{ticket_number,customer,under_warranty,status,days_open}[]`; excludes closed/cancelled tickets. Both queues span all periods. Days use IST calendar dates.
- Period starts at IST midnight, Monday, or month start and ends now. Totals are SQL aggregates. Common errors only.

### POST /dashboard/share
- Roles: director. Body: `{period:today|week|month,expires_in_hours?:int=72}` (1–168).
- Response 201: `{id,url:"/share/<token>",expires_at}`. Save id for revocation. Token is shown only in the URL; the database stores its SHA-256 hash. Common errors only.

### DELETE /dashboard/share/{id}
- Roles: director. No body. Response 204 with no body.
- Errors: 409 `SHARE_ALREADY_REVOKED`; common errors.

### GET /public/dashboard/{token}
- Public: no login. No body or query.
- Response 200: same `DashboardSummary` as the director endpoint, for the shared period. Read-only.
- Unknown, expired, and revoked tokens all return identical 404 `not_found` responses. No application rate limiter exists on the current public enquiry route to reuse; Nginx rate limits are scheduled for P3-2.

Configuration added: `SERVICE_LABOUR_RATE_PER_HOUR=500`, `SERVICE_LABOUR_GST_PERCENT=18` (Settings and .env.example).

## P3-2
- POST /api/v1/auth/login: public; request {email, password}, response {user, expires_at} unchanged. Session cookie now HttpOnly, SameSite=Lax, Path=/, Secure in production. Existing authentication errors unchanged.
- POST /api/v1/auth/logout: any authenticated role; no body; 204, now 401 without a session. Cookie deletion uses matching flags and path.
- GET /health and existing GET /api/health: public, no body, 200 {status: "ok"}.
- GET /health/ready and existing GET /api/health/ready: public, no body, 200 {status: "ready", database: "ok", redis: "ok"}; 503 http_error if DB or Redis fails.
- All endpoints: unexpected 500 responses contain error {code: "internal_error", message, request_id} and X-Request-ID; exception details stay in server logs.
- Production: same-origin requests only; Nginx adds security headers, caps request bodies at 6 MB, limits login to 5/minute (burst 5), general API to 10/second (burst 20).

## P2-1

### Shared shapes
- `CrewMember`: `user_id`, `name`, `hours` (string, null until completed).
- `ScheduleRow`: `job_id`, `status` (`planned|scheduled|in_progress|completed|cancelled`; `planned` = unscheduled), `scheduled_date` (date), `order_id`, `order_number`, `customer_name`, `customer_phone`, `site {id, address_line1, address_line2, city, state, pincode}`, `crew: CrewMember[]`.
- `JobRead` (job sheet): `id`, `status`, `order_id`, `order_number`, `customer_name`, `customer_phone`, `site`, `scheduled_date`, `started_at`, `finished_at`, `system_kw`, `power_test_passed`, `signer_name`, `crew: CrewMember[]`, `lines: [{order_item_id, sku, name, qty, requires_serial, serials: string[]}]` (serials from the dispatch), `photo_ids: int[]`, `signature_id` (nullable).
- `EvidenceRead`: `id`, `job_id`, `kind` (`photo|signature`), `content_type`, `size_bytes`, `created_at`.

### GET /schedule
- Roles: manager, office, director.
- Query: `from` (date, required), `to` (date, required, >= from, max 62 days later), `page`, `page_size` (default 50, max 100).
- Response 200: `Page[ScheduleRow]`, by date. Errors: 422 (bad range).

### POST /installation-jobs/{id}/schedule
- Roles: manager, director.
- Body: `{"scheduled_date": "2026-11-14", "technician_ids": [int, ...]}` (1-6, duplicates ignored). Rebooking a scheduled job replaces the crew.
- Response 200: `JobRead` (status `scheduled`).
- Errors: 404; 409 `JOB_NOT_SCHEDULABLE` (in progress/completed/cancelled); 409 `TECHNICIAN_DOUBLE_BOOKED` (message e.g. "Ravi already has ORD-000012 on 14 Nov"); 422 date in the past (IST) or a crew member who is not an active technician (`fields.technician_ids`).

### GET /installation-jobs/{id}
- Roles: technician (only if on the crew, else 403), manager, office, director.
- Response 200: `JobRead`.

### POST /installation-jobs/{id}/start
- Roles: technician on the crew (others 403).
- Response 200: `JobRead` (status `in_progress`, `started_at` set).
- Errors: 409 `JOB_STATUS_INVALID` (not scheduled), 409 `MATERIAL_NOT_DELIVERED` (dispatch not delivered).

### POST /installation-jobs/{id}/photos
- Roles: technician on the crew.
- Body: multipart/form-data, field `file`. JPEG/PNG/WEBP detected from the file bytes (filename and Content-Type are ignored). Max 5 MB, max 10 photos per job.
- Response 201: `EvidenceRead`.
- Errors: 409 `JOB_STATUS_INVALID` (not in progress), 409 `PHOTO_LIMIT_REACHED`, 413 `FILE_TOO_LARGE`, 422 `FILE_TYPE_NOT_ALLOWED`.

### POST /installation-jobs/{id}/complete
- Roles: technician on the crew.
- Body: `{"system_kw": "4.32" (0.5-50), "power_test_passed": true, "signer_name": string (2-150), "signature_png_base64": string}` (plain base64 or a `data:image/png;base64,...` URL; PNG 1 KB-500 KB).
- Response 200: `JobRead` (status `completed`, crew `hours` filled: elapsed time rounded up to 0.25 h, min 0.25, same for every crew member). Order becomes `installed` (or `completed` if already fully paid).
- Errors: 409 `JOB_STATUS_INVALID`, 409 `PHOTO_REQUIRED`, 422 `validation_error` (power test false, kW out of range), 422 `SIGNATURE_INVALID` (not PNG, blank canvas under 1 KB, too big, bad base64).

### GET /me/today
- Roles: technician.
- Response 200: `{"date", "surveys": [{id, status, scheduled_at, customer_name, site}], "installation_jobs": ScheduleRow[], "ticket_visits": [{id, ticket_number, status, priority, visit_date, issue_description, customer_name, site}]}` — only the caller's items, today in Asia/Kolkata.

### GET /evidence/{id}/file
- Roles: any logged-in user. Cookie auth, so it works directly in `<img src>`.
- Response 200: the file bytes with its stored content type. Errors: 404.

### Changed
- `GET /dashboard/summary`: `profit_per_job[].labour_cost` now fills from completed jobs (hours x snapshotted rate). No shape change.
