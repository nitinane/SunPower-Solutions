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
