# API changelog (for the frontend)

All paths are under `/api/v1`. Auth is the session cookie. `admin` is always allowed in addition to the listed roles.
Money fields are JSON strings (e.g. `"12345.00"`). Errors: `{"error": {"code", "message", "fields"}}`.
Common errors on every endpoint: 401 `unauthorized` (not logged in), 403 `forbidden` (wrong role), 422 `validation_error`.

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
