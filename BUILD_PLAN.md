# BUILD_PLAN.md — SunPower Solutions backend: everything left to build

## How to use this file (for Claude Code)
- The user starts each session with `/clear`, then: "Do the next task in BUILD_PLAN.md" (or names a task ID).
- "Next task" = the first unchecked box in PROGRESS, top to bottom.
- Do exactly that one task. Follow CLAUDE.md. The task text is the full spec: execute the steps in order. Don't plan, don't ask.
- When it passes: tick its box in PROGRESS (`- [x]`), include this file in the task's commit, then give the report.
- If you must STOP (a missing DB item, or a blocker you can't solve in 3 attempts): don't tick the box. Report what blocks you and which RECOVERY TASK the user should run.
- If the user says "short on time": do the SIMPLE version where a task has one.

## Facts about this repo (trust these over older text)
- Run docker compose from the repo root. Tests: `docker compose exec api python -m pytest -q` (real Postgres).
- db-requests.md is at the repo root. Decisions go in docs/decisions.md (one line each).
- Host port 5432 may be taken by another project (container ev-backend-db-1). If db won't start, tell the user to run `docker stop ev-backend-db-1`. Don't change compose files for this.
- Status names come from app/core/enums.py (DB names win). Known: order "waiting for payment" = pending_payment.
- Ticket columns follow the mapping in docs/decisions.md: ticket_number, faulty_serial_unit_id, issue_description, under_warranty, confirmed_by_name, customer_confirmed_at. Ticket parts and labour are rows in ticket_charges (charge_type part / labour; customer_price = unit price snapshot).
- Numbered records (ENQ-, QT-, ORD-): insert with a temporary unique value, then set `PREFIX-{id:06d}` in the same transaction. Copy this for new numbered records (tickets: TKT-). Invoices are different (see P2-2).
- Tests currently write into the dev database (fixed in P3-1).
- frontend/ belongs to the frontend teammate: never edit frontend/src. Build and deploy config for the frontend is allowed when a task says so.
- Seed script: scripts/seed.py (users + seed_catalog).

## After every task (in addition to CLAUDE.md "Finish every task")
Append to docs/api-changelog.md a section `## <task id>` listing every new or changed endpoint: method, path, roles, request body, response shape, error codes. The user forwards it to the frontend teammate.

## PROGRESS
- [x] DB-FIX — real initial migration + Phase 1 schema
- [x] P1-0 — Quotes + catalog seed
- [x] S0 — Setup
- [x] P1-1 — Payments create the pick list and crew job
- [x] P1-2 — Serial scanning, dispatch, warranties on delivery
- [x] P1-3 — Service tickets, director dashboard, full-chain test  (PHASE 1 CHECKPOINT)
- [ ] P3-2 — Security pass, production deploy files, CI  (done early on purpose: deploy early)
- [ ] P2-1 — Crew schedule + installation form
- [ ] P2-2 — Invoices
- [ ] P2-3 — Subsidy tracking + technician pay
- [ ] P3-1 — Test database, rule coverage, demo seed, load test
- [ ] P3-3 — README, diagrams, demo script, review prep, fresh-clone check

---

## S0 — Setup
1. In CLAUDE.md under "## How to work" add: `- Build plan: BUILD_PLAN.md. "Next task" = first unchecked box in its PROGRESS list.`
2. Create docs/api-changelog.md with a `## P1-0` section describing the existing catalog and quote endpoints (read the routes).
3. Commit: "docs: build plan setup".

---

## P1-1 — Payments create the pick list and crew job

CONTEXT
Accepting a quote already creates an order in pending_payment (app/services/quotes.py). Now: recording the FIRST payment must automatically create the warehouse pick list and the installation (crew) job, in the same transaction.

STEP 1 — Read only these
app/core/enums.py, app/core/deps.py, app/exceptions.py, app/schemas/common.py, app/services/quotes.py, app/api/routes/quotes.py, app/schemas/quotes.py, app/repositories/orders.py, app/models/orders.py, app/models/payments.py, app/models/dispatch.py, app/models/installations.py, app/services/enquiries.py (idempotency-key pattern only).

STEP 2 — DB check (if anything is missing: db-requests.md and STOP)
- payments: order_id, amount, kind, method, reference UNIQUE, idempotency_key, received_by, paid_at
- a pick-list / dispatch row linked to the order (one per order)
- installation_jobs linked to the order (one per order)
- order statuses meaning pending_payment, confirmed, cancelled

STEP 3 — Two small fixes first
a. Qualification with outcome "qualified" must have shadow_free_roof_area_sqft, monthly_bill_amount and grid_connection_suitable filled, else 422 with fields[...] for each missing one. 1 test.
b. In quote accept: set the enquiry status to converted (if that status exists) with an audit entry. 1 test.

STEP 4 — Build
Files: app/schemas/orders.py, app/repositories/orders.py (extend), app/repositories/payments.py, app/services/orders.py, app/api/routes/orders.py (register the router like quotes). If an orders endpoint already exists, extend it. Don't duplicate.

ENDPOINTS
POST /orders/{order_id}/payments            roles: OFFICE, DIRECTOR
  idempotency key: same pattern as enquiries
  body: amount (Decimal > 0), method (enum value), reference (required unless method is cash), paid_at (optional, default now)
  201 -> {payment: PaymentRead, order: OrderRead}
GET  /orders                                 roles: OFFICE, MANAGER, DIRECTOR
  filters: status, search (order number / customer name / phone), page, page_size. Newest first.
GET  /orders/{order_id}                      roles: OFFICE, MANAGER, WAREHOUSE, DIRECTOR
  OrderRead: number, status, customer, site, items (sku, name, qty, unit_price, line_total, requires_serial), subtotal, gst, total, amount_paid, balance_due, payments[], pick_list {id, status}, installation_job {id, status, scheduled_date}
  amount_paid and balance_due are computed with SQL SUM, not stored.

RULES — record_payment(), in this order, one transaction
1. Lock the order. Status must be pending_payment or confirmed, else 409 ORDER_NOT_PAYABLE.
2. Idempotency key already used -> return the existing payment (200). Create nothing.
3. amount <= balance_due, else 409 OVERPAYMENT (message shows the balance in ₹).
4. The server decides the payment kind, never the client: first payment == total -> FULL; first payment < total -> ADVANCE; later -> BALANCE.
5. Insert the payment. IntegrityError on reference -> 409 DUPLICATE_PAYMENT_REFERENCE.
6. If this is the order's FIRST payment:
   a. order status -> confirmed (set confirmed_at)
   b. create the pick list (dispatch row in its first status)
   c. create the installation job in its first status (unscheduled; the crew is assigned in P2-1)
   d. audit: payment.recorded, order.confirmed, pick_list.created, installation_job.created
   Never create a second pick list or job: check first; the DB unique constraint is the backup.
7. Later payments: audit payment.recorded only.

STEP 5 — Tests: tests/test_orders_payments.py
- advance: exactly 1 pick list + 1 job, order confirmed, kind ADVANCE
- balance: kind BALANCE, still 1 pick list + 1 job, balance_due "0.00"
- full payment first: kind FULL
- overpayment -> 409 OVERPAYMENT, nothing saved
- duplicate reference -> 409, nothing saved
- same idempotency key twice -> 1 payment
- cancelled order -> 409 ORDER_NOT_PAYABLE
- technician -> 403
- money exact: total 150000.00, advance 50000.00 -> balance_due "100000.00"
- plus the 2 tests from STEP 3

Commit: "feat(orders): payments trigger pick list and crew job"

---

## P1-2 — Serial scanning, dispatch, warranties on delivery

CONTEXT
After the first payment each order has a pick list (dispatch row in its first status). The warehouse scans a serial for every inverter, battery and charge controller, sends the order, and marks it delivered. Delivery must create every warranty row automatically, same transaction.
Dispatch statuses used (map to enums.py by meaning, ignore others): PICK -> DISPATCHED -> DELIVERED.

STEP 1 — Read only these
app/models/dispatch.py, app/models/inventory.py, app/models/warranties.py, app/models/catalog.py, app/models/orders.py, app/core/validators.py (normalize_serial), app/services/orders.py, scripts/seed.py.

STEP 2 — DB check (if anything is missing: db-requests.md and STOP)
- serialized_units: serial UNIQUE (indexed), product_id, status
- dispatch_items: serialized_unit_id UNIQUE, FK to order_items(id, product_id), quantity
- inventory quantity per product; stock_movements
- products.requires_serial, products.warranty_months
- warranties: order, product, order_item, start_date, end_date, serialized_unit_id NULLABLE, quantity

STEP 3 — Build
Files: app/core/dates.py (add_months(date, n): clamp to month end, no new library), app/schemas/dispatch.py, app/repositories/dispatch.py, app/repositories/inventory.py, app/repositories/warranties.py, app/services/dispatch.py, app/services/warranties.py, app/api/routes/dispatch.py. Seed: add seed_stock() to scripts/seed.py.

ENDPOINTS (roles: WAREHOUSE, DIRECTOR)
GET    /dispatches?status=&page=          warehouse queue, oldest first
GET    /dispatches/{id}                   order number, customer, site address, status, lines: [{order_item_id, sku, name, qty, requires_serial, scanned, serials: [...]}]
POST   /dispatches/{id}/scan {serial}     -> 200 with the updated lines
DELETE /dispatches/{id}/scan/{dispatch_item_id}   undo a wrong scan (PICK only)
POST   /dispatches/{id}/send              -> DISPATCHED
POST   /dispatches/{id}/deliver {receiver_name, delivered_at?}  -> DELIVERED + {warranties_created, warranties: [...]}

RULES — scan (lock the dispatch)
1. Must be PICK, else 409 DISPATCH_LOCKED.
2. serial = normalize_serial(input). Unknown -> 404 SERIAL_NOT_FOUND.
3. Already scanned on THIS dispatch -> 200, no change (scanners double-fire).
4. Product not on this order -> 409 SERIAL_WRONG_PRODUCT ("This is a BAT-150AH; this order needs INV-3K").
5. That line already fully scanned -> 409 LINE_ALREADY_COMPLETE.
6. Unit not in stock -> 409 SERIAL_ALREADY_SHIPPED if shipped, else SERIAL_NOT_IN_STOCK.
7. Insert dispatch_item. IntegrityError on serialized_unit_id -> 409 SERIAL_ALREADY_SHIPPED.

RULES — send (one transaction)
1. Lock the dispatch. Must be PICK, else 409.
2. Every requires_serial line fully scanned, else 409 SCAN_INCOMPLETE listing what's missing ("Inverter 0/1, Battery 1/2").
3. Lock inventory rows of the non-serial products ordered by product_id (avoids deadlocks). Any shortage -> 409 INSUFFICIENT_STOCK naming the product. Nothing changes.
4. Deduct non-serial quantities. Serialized units -> shipped/dispatched status. One stock_movement per product (type out, reference = dispatch id).
5. Dispatch -> DISPATCHED (dispatched_at, dispatched_by). Order -> dispatched if that status exists. Audit.

RULES — deliver (one transaction)
1. Lock the dispatch. Must be DISPATCHED, else 409 (already delivered -> ALREADY_DELIVERED).
2. Dispatch -> DELIVERED with receiver_name and delivered_at.
3. start_date = delivered_at converted to an Asia/Kolkata date.
4. One warranty per scanned serial unit: end_date = add_months(start_date, product.warranty_months).
5. One warranty per non-serial order line with warranty_months > 0 (panels: 240 months).
6. warranty_months = 0 -> no warranty. Audit warranty.created with the count.

SEED — seed_stock() (safe to run twice)
Each requires_serial product: 10 units, serial "{SKU}-0001" .. "{SKU}-0010", in stock.
Each other product: inventory 500 (panels 1000, wire 2000 metres).

STEP 4 — Tests: tests/test_dispatch.py, tests/test_dates.py
- add_months: 2027-01-31 + 1 = 2027-02-28; 2028-01-31 + 1 = 2028-02-29; +240 months correct
- unknown serial -> 404; wrong product -> 409; already shipped -> 409; over line qty -> 409
- same serial twice on the same dispatch -> 200, count unchanged
- send before all scanned -> 409 SCAN_INCOMPLETE
- send deducts stock + writes movements; shortage -> 409 and stock unchanged
- deliver: inverter warranty = start + 24 months, panels = start + 240 months, count correct
- deliver twice -> 409 ALREADY_DELIVERED
- OFFICE scanning -> 403

Commit: "feat(dispatch): serial scanning, stock out, warranties on delivery"

---

## P1-3 — Service tickets, director dashboard, full-chain test

CONTEXT
Months after installation a customer calls with a fault. Support finds them in seconds by phone, name or serial, sees the warranty, and opens a ticket: free if under warranty, billed (parts + labour) if not. Staff can't close a ticket; only the customer's confirmation does. The director sees profit per job, unfinished jobs and open repairs for today/week/month and can share a read-only link.
Ticket statuses (map by meaning): OPEN -> ASSIGNED -> RESOLVED (waiting for customer) -> CLOSED. Customer says "not fixed" -> back to OPEN.
Column names: use the docs/decisions.md mapping (see "Facts" above), not the names in this text.

STEP 1 — Read only these
app/models/service_tickets.py, app/models/warranties.py, app/models/customers.py, app/models/inventory.py, app/models/installations.py, app/core/config.py, app/core/validators.py, app/services/dispatch.py, docs/decisions.md, app/api/routes/*.py (paths only).

STEP 2 — DB check (if anything is missing: db-requests.md and STOP)
ticket fields per the mapping; ticket_charges; dashboard_share_links (token_hash UNIQUE, period, expires_at, revoked_at, created_by); indexes on customers.phone_e164, serialized_units.serial, ticket status.

STEP 3 — Build
Files: app/schemas/tickets.py, app/repositories/tickets.py, app/services/tickets.py, app/api/routes/tickets.py, app/api/routes/support.py, app/schemas/dashboard.py, app/repositories/dashboard.py, app/services/dashboard.py, app/api/routes/dashboard.py.
Config: SERVICE_LABOUR_RATE_PER_HOUR (default 500), SERVICE_LABOUR_GST_PERCENT (default 18) in Settings and .env.example.

ENDPOINTS — support and tickets
GET  /support/search?q=                  roles: SUPPORT, OFFICE, DIRECTOR. Max 10 results.
  q parses as a phone -> match phone_e164; else exact normalized serial; else name ILIKE 'q%'.
  Each result: customer, sites, orders (number, status), units [{serial, product, warranty_end, warranty_status: active|expired, days_left}], open tickets. "Today" = Asia/Kolkata date.
POST /tickets                            roles: SUPPORT, OFFICE
  body: customer_id, serial unit id OR order_item_id (exactly one, else 422), fault_code, issue description, priority
  The server finds the warranty and saves under_warranty (end_date >= today IST) at creation.
  Response includes coverage_label: "Under warranty – free" or "Out of warranty – billable".
GET  /tickets?status=&assigned_to_me=&page=   roles: SUPPORT, MANAGER, DIRECTOR, TECHNICIAN (own only)
GET  /tickets/{id}                       detail + charges + history (audit rows)
POST /tickets/{id}/assign {technician_id, visit_date}   roles: SUPPORT, MANAGER. OPEN -> ASSIGNED
POST /tickets/{id}/resolve {work_notes, labour_hours, parts: [{product_id, qty}]}   roles: the ASSIGNED technician, SUPPORT. ASSIGNED -> RESOLVED
POST /tickets/{id}/confirm {confirmed, customer_name, note?}   roles: SUPPORT, OFFICE. RESOLVED only.
  true -> CLOSED (confirmed_by_name, customer_confirmed_at). false -> OPEN, note in audit.

RULES — resolve (one transaction)
1. Parts: non-serial products only (swapping a serialized unit = roadmap; add to decisions.md). Lock inventory rows by product_id; shortage -> 409 INSUFFICIENT_STOCK. Deduct + stock_movement (type service, reference = ticket id). Charge rows with customer_price = product sale price.
2. Under warranty: every charge amount and the totals = "0.00" (still save parts + hours).
3. Not under warranty: parts = qty x sale price, GST at each product's rate; labour = labour_hours x SERVICE_LABOUR_RATE_PER_HOUR, GST at SERVICE_LABOUR_GST_PERCENT. Quantize each line.
4. Only /confirm can set CLOSED. No other code path sets CLOSED.

ENDPOINTS — dashboard (role: DIRECTOR)
GET /dashboard/summary?period=today|week|month
  Period in Asia/Kolkata: today from 00:00, week from Monday 00:00, month from the 1st. Use orders.confirmed_at.
  cards: new_enquiries, orders_confirmed, payments_received, profit, unfinished_jobs, open_repairs
  profit_per_job (confirmed in period, newest first, max 50): order_number, customer, system_kw, revenue (subtotal excl. GST), material_cost (sum qty x unit_cost snapshot), labour_cost (job hours x hourly_cost snapshot, 0 if none yet), profit, margin_percent
  unfinished_jobs: confirmed but not completed: order_number, customer, stage, days_open
  open_repairs: ticket number, customer, under_warranty, status, days_open
  All in app/repositories/dashboard.py with SQL SUM / GROUP BY. One query per block. No Python loops to compute totals.
POST   /dashboard/share {period, expires_in_hours = 72, max 168} -> {url: "/share/<token>", expires_at}
       token = secrets.token_urlsafe(32); store only its SHA-256 hash.
DELETE /dashboard/share/{id}             revoke
GET    /public/dashboard/{token}         NO login. Same summary, read-only. unknown / expired / revoked -> the same 404. Reuse the public enquiry route's rate limit if it has one.

STEP 4 — Tests: tests/test_tickets.py, tests/test_dashboard.py, tests/test_e2e_chain.py
- search finds the same customer from "98765 43210", "+91-98765-43210", the serial and the name
- in-warranty ticket total "0.00"
- expired warranty (fixture sets end_date in the past): exact parts + labour + GST total
- confirm before resolve -> 409; confirm false -> OPEN; confirm true -> CLOSED
- technician not assigned resolving -> 403
- dashboard profit for a known order = revenue - material - labour, exact
- order confirmed last month is NOT in period=week
- share link works; expired -> 404; revoked -> 404; non-director -> 403
- E2E via the API only (take paths from routes): public enquiry -> qualify -> survey -> approve -> quote -> send -> accept -> advance payment -> scan all serials -> send -> deliver -> search by serial -> ticket -> assign -> resolve -> confirm -> CLOSED; dashboard lists the order.

Commit: "feat(support,dashboard): tickets, dashboard, share link, e2e chain"
Report line for the user: "PHASE 1 CHECKPOINT: push, then the next task prepares deployment."

---

## P3-2 — Security pass, production deploy files, CI

CONTEXT
Review round 3 checks security and that the app is deployed. Prepare everything so the user only has to create a VM and run documented commands.

STEP 1 — Read only these
docker-compose.yml, docker-compose.dev.yml, the nginx config, backend/Dockerfile, backend/entrypoint.sh, app/main.py, app/core/config.py, app/core/deps.py, app/api/routes/auth.py, .gitignore, .env.example, Makefile, frontend/package.json (scripts only).

STEP 2 — Security checks (fix what fails)
1. tests/test_route_protection.py: for every APIRoute NOT in PUBLIC = {POST /api/v1/auth/login, POST /api/v1/enquiries/public, GET /api/v1/public/dashboard/{token}, health routes, /docs, /redoc, /openapi.json}: call it with no cookie (path params "1", JSON body {} for POST/PUT/PATCH) -> expect 401. Anything else = missing auth: fix the route.
2. Session cookie: HttpOnly, SameSite=Lax, Path=/, Secure when ENVIRONMENT=production. Test it.
3. Rate limits in Nginx: zone for /api/v1/auth/login (5r/m, burst 5), general zone for /api/ (10r/s, burst 20). Keep slowapi if already used.
4. CORS: no wildcard. Production: same-origin (no CORS origins). Dev: http://localhost:5173 only.
5. Production errors: no stack traces or SQL in responses; generic 500 with the request id.
6. Secrets: `git ls-files` must list no .env file except .env.example. If one is tracked: `git rm --cached`, add to .gitignore, and tell the user to change those secrets.
7. Nginx: server_tokens off; X-Content-Type-Options nosniff; X-Frame-Options DENY; Referrer-Policy strict-origin-when-cross-origin; Content-Security-Policy "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'"; client_max_body_size 6m.
8. Health: GET /health (process up) and GET /health/ready (DB SELECT 1 + Redis PING; 503 if either fails). Compose healthchecks use /health/ready.
9. pip-audit (pin it in requirements-dev.txt) on requirements.txt; upgrade only packages with HIGH/CRITICAL issues; list results in the report.

STEP 3 — Production files
1. docker-compose.prod.yml (override): no code mounts, no --reload; several workers (WEB_CONCURRENCY, default 2) using what the Dockerfile supports; restart: unless-stopped; db and redis not published; named volumes for postgres data and uploaded files.
2. Frontend in production: nginx serves the built frontend. If not already done, add a multi-stage nginx Dockerfile: stage 1 node (version from frontend/package.json "engines", else node:20.18.0-alpine) runs `npm ci && npm run build`; stage 2 copies dist into the nginx html folder. SPA fallback `try_files $uri /index.html`. /api proxied to the api upstream.
3. HTTPS: a caddy service (image caddy:2.8.4) only in docker-compose.prod.yml, ports 80 and 443, Caddyfile `{$DOMAIN} { reverse_proxy nginx:80 }`, volumes for caddy data and config. nginx has no public ports in prod.
4. .env.production.example: every setting, ENVIRONMENT=production, DOMAIN=, secret placeholders with the note "generate with: openssl rand -hex 32".
5. entrypoint runs `alembic upgrade head` before the server starts (keep if already there).
6. deploy/DEPLOY.md — exact steps for the user:
   - VM: Ubuntu 24.04, 2 vCPU / 4 GB, open ports 22, 80, 443 only.
   - Install Docker: `curl -fsSL https://get.docker.com | sh`
   - git clone; `cp .env.production.example .env`; fill secrets; DOMAIN = your domain, or `<VM-IP-with-dashes>.sslip.io` (example 203-0-113-10.sslip.io) if you have none.
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`
   - seed users + catalog + stock (the real seed command)
   - open https://DOMAIN and log in.
   - Updates: deploy/deploy.sh (git pull, up -d --build, show status).
   - Backup: a nightly pg_dump cron line. Logs: `docker compose logs -f api`.
7. Local check: `docker compose -f docker-compose.yml -f docker-compose.prod.yml config -q` passes.

STEP 4 — CI: .github/workflows/ci.yml
- on push and pull_request to main.
- job backend: ubuntu-latest; services postgres + redis with the SAME image tags as docker-compose.yml and health options; actions/checkout@v4; actions/setup-python@v5 (python 3.12, pip cache); install requirements.txt + requirements-dev.txt; ruff check; alembic upgrade head; python -m pytest -q. Env vars point at the service containers.
- job frontend: actions/setup-node@v4; npm ci; npm run build (in frontend/).
- job compose: `docker compose -f docker-compose.yml -f docker-compose.prod.yml config -q`.

TESTS: route protection; cookie flags with production settings; /health/ready returns 200 with DB + Redis up.
Commit: "chore(prod): security pass, prod compose, https, ci"
Report must end with "WHAT YOU DO BY HAND": the DEPLOY.md steps, plus any secret that must be changed.

---

## P2-1 — Crew schedule + installation form

CONTEXT
After the first payment each order has an unscheduled installation job. A manager books a crew and a date (no double-booking). On the day the technician uses a phone form: START, photos, confirm kW, power test, the customer sees the installed items with serials and signs on screen, FINISH. Hours feed profit per job and technician pay.
Job statuses (map by meaning): UNSCHEDULED -> SCHEDULED -> IN_PROGRESS -> COMPLETED.

STEP 1 — Read only these
app/models/installations.py, app/models/users.py, app/models/dispatch.py, app/services/dispatch.py, app/services/orders.py, app/storage/* (if present), app/core/config.py, the nginx config.

STEP 2 — DB check (if anything is missing: db-requests.md and STOP)
- installation_jobs: scheduled_date, started_at, finished_at, system_kw, power_test_passed, signer_name
- job_technicians: job_id, user_id, hours NUMERIC(5,2), hourly_cost snapshot; UNIQUE (job_id, user_id)
- users.hourly_rate NUMERIC(10,2)
- installation_evidence: job_id, kind (photo/signature), storage_key, content_type, size_bytes, uploaded_by, created_at
- an order status meaning installed/completed

STEP 3 — Build
Files: app/schemas/installations.py, app/repositories/installations.py, app/services/installations.py, app/services/schedule.py, app/api/routes/installations.py, app/api/routes/me.py.
Storage: reuse app/storage if it has a helper; else app/core/storage.py with save(bytes, ext) -> storage_key "<yyyy>/<mm>/<uuid4>.<ext>" under settings.STORAGE_DIR (a named volume in compose) and open(storage_key). Never use the uploaded filename on disk.

ENDPOINTS
GET  /schedule?from=&to=                     roles MANAGER, OFFICE, DIRECTOR: jobs in range with crew names, order number, customer, address, status
POST /installation-jobs/{id}/schedule {scheduled_date, technician_ids}   roles MANAGER, DIRECTOR
GET  /me/today                               role TECHNICIAN: my surveys, installation jobs and ticket visits today (Asia/Kolkata)
GET  /installation-jobs/{id}                 crew, MANAGER, OFFICE, DIRECTOR: job, crew, order lines, installed units with serials (from the dispatch), photo ids, status
POST /installation-jobs/{id}/start           crew technician
POST /installation-jobs/{id}/photos          crew technician, multipart file -> evidence id
POST /installation-jobs/{id}/complete {system_kw, power_test_passed, signer_name, signature_png_base64}   crew technician
GET  /evidence/{id}/file                     any logged-in staff role; streams the file with its content type (cookie auth works in <img>)

RULES — schedule (lock the job)
1. Status UNSCHEDULED or SCHEDULED, else 409 JOB_NOT_SCHEDULABLE. scheduled_date >= today (IST), else 422.
2. 1 to 6 technician_ids; each an active user with role TECHNICIAN, else 422.
3. One installation job per technician per date: on another SCHEDULED/IN_PROGRESS job with the same date -> 409 TECHNICIAN_DOUBLE_BOOKED ("Ravi already has ORD-000012 on 14 Nov").
4. Replace this job's crew rows; hourly_cost = the user's current hourly_rate (snapshot). Status -> SCHEDULED. Audit.

RULES — start
1. Actor on the crew, else 403. Status SCHEDULED, else 409.
2. The order's dispatch must be DELIVERED, else 409 MATERIAL_NOT_DELIVERED.
3. Status -> IN_PROGRESS, started_at = now. Audit.

RULES — photo
1. Actor on the crew; status IN_PROGRESS, else 409. Max 10 photos per job (409).
2. Max 5 MB -> else 413 FILE_TOO_LARGE. Type from the first bytes, never the filename or header: JPEG FF D8 FF; PNG 89 50 4E 47 0D 0A 1A 0A; WEBP "RIFF" + "WEBP" at bytes 8-11. Else 422 FILE_TYPE_NOT_ALLOWED.
3. Save with the storage helper; evidence row kind=photo.

RULES — complete (one transaction)
1. Actor on the crew; status IN_PROGRESS, else 409.
2. power_test_passed must be true, else 422. system_kw between 0.5 and 50.
3. At least 1 photo, else 409 PHOTO_REQUIRED.
4. Signature: base64-decode; PNG magic bytes; 1 KB to 500 KB, else 422 SIGNATURE_INVALID (under 1 KB counts as a blank canvas). Save as evidence kind=signature.
5. finished_at = now. hours = finished_at - started_at in hours, rounded UP to 0.25, minimum 0.25; the same hours on every crew row.
6. Job -> COMPLETED; order -> installed/completed status. Audit.

TESTS: tests/test_installations.py (set started_at directly in fixtures for time math)
- double booking -> 409; same technician on another date OK; non-technician in crew -> 422
- start before delivery -> 409 MATERIAL_NOT_DELIVERED; technician not on crew -> 403
- text file renamed .jpg -> 422; 6 MB -> 413; valid PNG -> 201
- complete without photo -> 409; power test false -> 422; blank signature -> 422
- started 10:00, finished 12:10 -> 2.25 hours per crew member; hourly_cost unchanged after the user's rate changes
- /me/today shows only my items
- dashboard profit for that order now includes labour cost

Commit: "feat(installations): crew schedule, install form, photos, signature"

---

## P2-2 — Invoices

CONTEXT
GST invoices with gapless sequential numbers. An order invoice is created automatically when the order is delivered (the moment of supply). A repair invoice is created automatically when a billable ticket is closed. Invoices never change after creation (corrections = credit notes, roadmap). The frontend prints them with print CSS; no server PDF.

STEP 1 — Read only these
app/models/invoices.py, app/services/dispatch.py (deliver), app/services/tickets.py (confirm), app/models/customers.py, app/core/config.py.

STEP 2 — DB check (if anything is missing: db-requests.md and STOP)
- invoices: invoice_number UNIQUE, financial_year, kind (order/service), order_id UNIQUE NULL, ticket_id UNIQUE NULL, customer_id, invoice_date, place_of_supply_state, taxable_amount, cgst, sgst, igst, total, created_by
- invoice_lines: invoice_id, description, sku, qty, unit_price, gst_percent, taxable, gst_amount
- invoice_sequences: financial_year PRIMARY KEY, last_number

STEP 3 — Build
Files: app/schemas/invoices.py, app/repositories/invoices.py, app/services/invoices.py, app/api/routes/invoices.py.
Config (Settings + .env.example): COMPANY_NAME="SunPower Solutions", COMPANY_GSTIN (placeholder), COMPANY_ADDRESS, COMPANY_STATE="Telangana".

RULES — numbering (inside the caller's transaction)
1. financial_year from invoice_date (IST), April to March: 2026-11-01 -> "2026-27"; 2027-03-31 -> "2026-27"; 2027-04-01 -> "2027-28".
2. INSERT the sequence row if missing (ON CONFLICT DO NOTHING), then SELECT ... FOR UPDATE, last_number + 1. Format "INV/2026-27/000001". Gapless because it shares the invoice's transaction: a rollback undoes both.

RULES — create_for_order(order): called inside deliver, same transaction
1. Invoice already exists for the order -> return it.
2. Lines = copies of order_items (snapshots). taxable, gst and total must equal the order's exactly.
3. Tax split by the site's state: same as COMPANY_STATE (case-insensitive) -> cgst = (gst / 2) quantized, sgst = gst - cgst, igst = 0. Otherwise igst = gst.
4. Audit invoice.created.

RULES — create_for_ticket(ticket): called inside confirm when the ticket becomes CLOSED, is not under warranty and its total > 0. Lines = ticket_charges (parts + labour). Same split.

ENDPOINTS (roles OFFICE, DIRECTOR)
GET  /invoices?kind=&from=&to=&search=&page=
GET  /invoices/{id}   printable: seller (settings), buyer (name, address, phone, GSTIN if any), number, date, place of supply, lines, taxable, cgst + sgst or igst, total; for orders also amount paid and balance due.
POST /orders/{id}/invoice   create if missing; order must be delivered, else 409 ORDER_NOT_DELIVERED. (For orders delivered before this feature.)
No update or delete endpoints.

TESTS: tests/test_invoices.py
- deliver creates exactly 1 invoice; totals == order totals exactly
- 3 invoices -> 000001, 000002, 000003 in the same FY; an invoice dated 2027-04-01 -> INV/2027-28/000001
- Telangana: cgst + sgst == gst exactly (gst 101.01 -> 50.51 + 50.50); Karnataka: igst only
- billable ticket closed -> service invoice; warranty ticket closed -> none
- POST /orders/{id}/invoice twice -> same invoice; not delivered -> 409

SIMPLE version: skip the FY-rollover test.
Commit: "feat(invoices): gst invoices, gapless numbers, auto-create on delivery and paid repairs"

---

## P2-3 — Subsidy tracking + technician pay

### Part A — Subsidy
CONTEXT
Home customers can get a government rooftop solar subsidy. The office tracks the paperwork per order until the money arrives.
Statuses (map by meaning): DOCUMENTS_PENDING -> APPLIED -> INSPECTED -> SANCTIONED -> DISBURSED; REJECTED from any step before DISBURSED.
Required documents (one checklist row each): electricity_bill, id_proof, bank_details, roof_photos, net_meter_application, installation_certificate. Track "received" and an optional file only. Never store ID numbers.

DB check (STOP if missing): subsidy_applications (order_id UNIQUE, status, application_number, applied_on, inspected_on, sanctioned_amount, sanctioned_on, disbursed_amount, disbursed_on, rejection_reason, notes); subsidy_documents (application_id, doc_type, received, received_on, storage_key NULL; UNIQUE (application_id, doc_type)).

Build: app/schemas/subsidies.py, app/repositories/subsidies.py, app/services/subsidies.py, app/api/routes/subsidies.py. Roles OFFICE, DIRECTOR.
Auto-create: in record_payment (services/orders.py), when the FIRST payment confirms the order and the enquiry had subsidy_requested = true, create the application (DOCUMENTS_PENDING) with all 6 document rows, same transaction.

ENDPOINTS
GET   /subsidies?status=&page=     with order number, customer, missing document count, days in current status
GET   /subsidies/{id}
POST  /orders/{id}/subsidy         create manually (409 if it exists)
PATCH /subsidies/{id}/documents/{doc_type} {received}
POST  /subsidies/{id}/documents/{doc_type}/file   same upload rules as installation photos, plus PDF (%PDF magic bytes)
POST  /subsidies/{id}/advance {to_status, application_number?, date, amount?, reason?}

RULES — advance (lock the application)
1. Only the next status in the chain, or REJECTED (reason required). Else 409 INVALID_SUBSIDY_STEP.
2. -> APPLIED: every document except installation_certificate received, else 409 DOCUMENTS_MISSING listing them; application_number required.
3. -> INSPECTED: the order's installation job COMPLETED and installation_certificate received, else 409.
4. -> SANCTIONED: amount > 0 (sanctioned_amount).
5. -> DISBURSED: 0 < amount <= sanctioned_amount, else 422.
6. Dates are IST dates. Audit every step.

### Part B — Technician pay
CONTEXT
Technicians are paid monthly for hours on installation jobs and repair visits.

DB check (STOP if missing): pay_runs (month CHAR(7) UNIQUE like "2026-11", status draft/paid, paid_on, payment_reference, created_by); pay_run_lines (pay_run_id, technician_id, install_hours, repair_hours, rate, amount; UNIQUE (pay_run_id, technician_id)); users.hourly_rate; tickets have labour_hours and the assigned technician.

Build: app/schemas/pay.py, app/repositories/pay.py, app/services/pay.py, app/api/routes/pay.py.

ENDPOINTS
POST /pay-runs {month}                 DIRECTOR. Creates or recalculates the draft for that month.
GET  /pay-runs; GET /pay-runs/{id}     DIRECTOR: lines + breakdown (job numbers with hours, ticket numbers with hours)
POST /pay-runs/{id}/mark-paid {paid_on, payment_reference}   DIRECTOR
GET  /me/pay?month=                    TECHNICIAN: own line and breakdown only

RULES
1. Month range in Asia/Kolkata: 1st 00:00 to next month's 1st 00:00.
2. Install pay = job_technicians.hours x that row's hourly_cost snapshot, for jobs finished in the month. Repair pay = labour_hours of tickets resolved in the month by that technician x their current hourly_rate. Amounts quantized. Computed with SQL GROUP BY.
3. Draft exists -> delete its lines and recompute. PAID -> 409 PAY_RUN_LOCKED.
4. Each job or visit belongs to exactly one month (by finish/resolve time), so nothing is paid twice.

TESTS: tests/test_subsidies.py, tests/test_pay.py
- subsidy auto-created on first payment only when requested; APPLIED blocked with missing docs (list correct); INSPECTED blocked before install completed; disbursed > sanctioned -> 422; skipping a step -> 409; REJECTED needs a reason
- pay: exact amount for 2 jobs + 1 repair; job finished 2026-10-31 23:30 IST counts in 2026-10, not 2026-11 (UTC trap); recalculation replaces lines; paid run -> 409 on recalculation; technician sees only own pay; non-director -> 403

SIMPLE version: no subsidy file uploads; pay without the per-line breakdown.
Commit: "feat(subsidy,pay): subsidy tracking, monthly technician pay"

---

## P3-1 — Test database, rule coverage, demo seed, load test

STEP 1 — Separate test database
- Tests use their own database `<db name>_test` on the same Postgres. In tests/conftest.py at session start: create it if missing (connect to the "postgres" database with AUTOCOMMIT), run alembic upgrade head against it (programmatic, URL override), TRUNCATE every table except alembic_version (RESTART IDENTITY CASCADE), then seed users + catalog + stock. Point the app's get_db (and any session used by tests) at the test database.
- Prove the dev database is untouched: count enquiries in the dev DB before and after a full test run; report both numbers.
- CI must still pass with its own database.

STEP 2 — Rule coverage. Make sure a test exists for each (add missing ones):
quote blocked without approved survey; parts list auto-expands; first payment creates pick list + job; wrong-model and already-shipped serials rejected; dispatch blocked until all scanned; delivery creates warranties (24 / 240 months); search by phone variants and serial; in-warranty repair free; out-of-warranty repair billed exactly; ticket closes only via customer confirmation; dashboard periods in IST; gapless invoice numbers; double booking blocked; route protection.
Add pytest-cov (pinned) to requirements-dev.txt; report coverage for app/services (no minimum).

STEP 3 — Demo seed: scripts/seed_demo.py (idempotent: skip if the customer "Ravi Kumar (demo)" exists)
- One login per role: director, manager, office, warehouse, 3 technicians, support. Password from env DEMO_PASSWORD (add to .env.example). Never print passwords.
- Customers at every stage, created THROUGH THE SERVICE FUNCTIONS so rules and audit run, with Hyderabad addresses and Indian names: 1 new enquiry (2 days old, overdue), 1 qualified awaiting survey, 1 survey awaiting approval, 1 quote sent, 1 paid awaiting dispatch, 1 delivered awaiting installation, 2 installations completed this month (with crew hours), 1 installed 3 years ago whose inverter warranty has EXPIRED with an open repair ticket, 1 in-warranty ticket resolved and waiting for customer confirmation, 1 closed paid repair with its invoice, 2 subsidy applications at different steps, 1 draft pay run for last month.
- Old dates: set timestamp columns directly AFTER the service call, only in this script.
- Demo reset: scripts/demo_reset.ps1 AND a Makefile target demo-reset: docker compose down -v; up -d (wait healthy); alembic upgrade head; seed; seed_demo.

STEP 4 — Load test (evidence for "what if 10,000 users come?")
- loadtest/k6.js: in setup() log in once as director, read the session cookie from the response and pass it to the virtual users (they send it as a Cookie header; this avoids the login rate limit). 30 s ramp to 50 virtual users, then 60 s steady, on GET /api/v1/enquiries, GET /api/v1/support/search?q=<seeded serial>, GET /api/v1/dashboard/summary?period=month.
- Run with Docker, no install: `docker run --rm -v <repo>/loadtest:/scripts -e BASE_URL=http://host.docker.internal grafana/k6:0.54.0 run /scripts/k6.js`
- docs/loadtest.md: requests/second, p95 latency and error rate per endpoint, the machine used, and 3 sentences on what to scale first.

Commit: "test: separate test db, rule coverage, demo seed, load test"

---

## P3-3 — README, diagrams, demo script, review prep, fresh-clone check

STEP 1 — README.md at the repo root (replace the stub; keep anything already true). Short, plain sections:
1. The problem in 4 sentences (SunPower: 40 jobs/month, 15 technicians, lost enquiries, hand-typed quotes, paper serials, no profit view).
2. What we built: the 13 features, one line each, with the one rule that makes each trustworthy.
3. Live URL + demo logins table (roles only; password "see DEMO_PASSWORD").
4. Architecture: modular monolith; Router -> Service -> Repository. Mermaid flowchart: Browser -> Caddy (HTTPS) -> Nginx (frontend + /api) -> FastAPI workers -> PostgreSQL + Redis.
5. Data model: Mermaid erDiagram of the core tables, generated from the real models.
6. The automatic chain: a short paragraph + Mermaid sequence diagram: payment -> pick list + job; deliver -> warranties + invoice; ticket -> free/billed from the warranty; closes only via the customer.
7. Tech stack table: tool | why (one sentence each).
8. Run locally, run tests, demo reset.
9. Security: what P3-2 did.
10. Testing: what's covered, how to run, coverage, load test summary.
11. How it scales: stateless API -> `docker compose up --scale api=3` behind Nginx; indexes on phone/serial; the DB is the real bottleneck -> PgBouncer, a read replica for the dashboard; a queue for SMS/WhatsApp later; Kubernetes only when needed.
12. Roadmap (left out on purpose): instant estimate, QR complaint stickers, customer tracking link, AI call sheet, WhatsApp Business API, SMS (needs DLT registration), credit notes, HSN codes on invoices, swapping serialized parts in repairs.
13. Key decisions: link docs/decisions.md and list the 8 most important as one-liners.

STEP 2 — docs/demo-script.md: a 5-minute script by role using the demo seed: exact screen, exact click, one sentence to say. The 7 "wow" moments: (1) quote blocked without an approved survey, (2) one payment creates the pick list + crew job, (3) wrong serial rejected live, (4) delivery creates warranties + invoice, (5) serial search -> expired warranty -> billed automatically, (6) ticket closes only on customer confirmation, (7) dashboard profit per job + share link. A Swagger (/docs) fallback for each step if the UI fails.

STEP 3 — docs/review-prep.md: for each review round (1 intro, 2 deep technical, 3 functional/growth): 10 likely questions with 1-2 sentence answers taken from the real code and docs/decisions.md (DB design, transactions and locking, idempotency, why a monolith, why sync SQLAlchemy, security, scaling, testing, what we'd change with more time). Plus an honest one-line pattern for "I don't know".

STEP 4 — Fresh-clone check (report every command and its result)
1. Stop the dev stack. git clone the repo into a temp folder; cp .env.example .env; `docker compose -p sunpower_fresh up -d --build`; migrate; seed; seed_demo; run the e2e test against it; check /health/ready.
2. `docker compose -p sunpower_fresh down -v`; delete the temp folder; restart the dev stack.
3. Anything that failed (missing env var, file, path) -> fix in the repo and repeat.

Commit: "docs: readme, diagrams, demo script, review prep"
Report must end with the user's final checklist: push, deploy latest on the server, run demo reset on the server, rehearse the demo script twice.

---

## RECOVERY TASKS (run only when the user names them)

### DB-UPDATE — apply the open items in db-requests.md
Run only when the user says the DB teammate agreed. If the teammate already pushed the change: just pull, `alembic upgrade head`, run tests, and continue.
Exception for this task only: you MAY edit app/models/*, app/core/enums.py and alembic/versions/*.
1. Apply every open item in db-requests.md to the models. Additive only: no renames, no drops; money NUMERIC(12,2); timestamptz; follow app/db/base.py.
2. A NEW migration (never edit the initial one): `docker compose exec api alembic revision --autogenerate -m "<short name>"`. Make sure the file is on the host in backend/alembic/versions/.
3. Read the file: only additive operations, no drop_table / drop_column. New NOT NULL columns on existing tables get a server_default.
4. alembic upgrade head -> downgrade -1 -> upgrade head. All tests pass.
5. Move the applied items under "## Done" in db-requests.md. Commit: "feat(db): <short name>". Then the user re-runs the blocked task with CONTINUE.

### FIX — a test fails or something is broken
1. Reproduce with the smallest failing test first.
2. Find the cause; make the smallest change that fixes it. No refactors.
3. Full test suite + ruff. Commit "fix: <what>". Report the cause in one sentence.

### CONTINUE — resume the current task
Re-read the first unchecked task, check `git status` and what's already done, and continue from the first unfinished step.

---

## FOR THE HUMAN (Aryan) — the loop
1. In Claude Code: `/clear` + Enter, then "Do the next task in BUILD_PLAN.md". One task per session.
2. When it finishes: `git push`, and send the new section of docs/api-changelog.md to the frontend teammate.
3. If it stops on db-requests.md: send that file to the DB teammate. When he pushes, pull and type "Run CONTINUE". If he agrees you do it: "Run DB-UPDATE", then "Run CONTINUE".
4. If tests keep failing: "Run FIX: <paste the error>". Switch to the stronger model with /model for this.
5. After P3-2: create the VM and follow deploy/DEPLOY.md. After every later task: run deploy/deploy.sh on the server.
6. Short on time: say "short on time" before a task; cut P2-3 first, then explain the missing features on the roadmap. Never skip P3-3.
7. Before the demo: demo reset on the server, then rehearse docs/demo-script.md twice.
