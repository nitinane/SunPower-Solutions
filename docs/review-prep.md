# Review preparation

Answers describe this checkout, not a future UI or an unmeasured production system. Start with the short answer, then open the cited module or linked document if asked for evidence.

## Round 1 — Introduction

1. **Who is this for?** SunPower's office, warehouse, technicians, support and director, handling about 40 installations a month with 15 technicians. The aim is to keep enquiries, equipment and money connected across those handoffs.
2. **What problem did you solve first?** The automatic chain: a first payment creates the warehouse and crew work, and delivery starts warranties and creates an invoice. Services commit those related changes together instead of relying on staff to enter each record twice.
3. **What can you demonstrate today?** The backend workflows, their validation failures, seed scenarios and profit calculations through `/api/docs`. The React role pages and role guard are still placeholders, so we do not present them as a completed product UI.
4. **Why is a survey approval mandatory?** A quote must describe the roof that was inspected. `services/quotes.py` rejects a submitted but unapproved survey with `SURVEY_NOT_APPROVED`.
5. **How do you know which equipment reached a customer?** Dispatch items connect an order line to its scanned serialized unit, and warranties preserve that link. Support can search by normalized serial or phone.
6. **What happens when the same button is clicked twice?** Payment requests support idempotency keys and dispatch scanning repeats the same serial on the same pick list safely. Database unique constraints back up the service checks.
7. **What makes the warranty experience different?** Coverage is decided when the ticket opens, and covered repairs/replacements have zero customer charge while retaining internal costs. Replacements keep the remaining coverage of the original warranty.
8. **Who closes a repair?** Support or office records the customer's confirmation after resolution; a negative confirmation reopens the ticket. This records a customer statement through staff, not an independently verified customer login.
9. **What does the director see?** SQL-calculated job revenue less material, installation labour and warranty service cost, plus receipts, unfinished installations and open repairs. A public share is read-only, expires and can be revoked.
10. **What is deliberately left out?** The roadmap includes instant estimates, QR complaint stickers, customer tracking, AI call sheets, WhatsApp/SMS integration, credit notes and HSN codes. Completing frontend workflows is also outstanding; serialized warranty swaps are already built.

## Round 2 — Technical depth

1. **Why a modular monolith?** Payment, dispatch, warranty and billing actions need atomic updates to related tables. One deployable API with Router → Service → Repository keeps those transactions local and fits the team's scale without service coordination overhead.
2. **Why synchronous SQLAlchemy?** The code uses sync database sessions and plain `def` endpoints, which FastAPI runs in a thread pool. That keeps the transaction code straightforward; throughput still depends on workers, thread capacity and database connections.
3. **What prevents invalid relationships?** Foreign keys and composite foreign keys tie order/site/customer and order-item/product/serial pairs together; checks enforce statuses, nonnegative values and exactly one invoice/payment parent. `app/models` and Alembic migrations are the source of truth; the README diagram is a subset of those constraints.
4. **How do you avoid races?** Each action locks its main row, and stock rows are locked in a consistent order before deductions. Scheduling also locks technician user rows in id order, so two different jobs cannot both pass the same person's availability check concurrently.
5. **Where are transactions committed?** Services commit the whole action after state changes and audit inserts; repositories do not commit. A validation failure or integrity failure rolls back the database changes, though file storage is separate from the database and can leave orphaned files if a later commit fails.
6. **How is idempotency scoped?** Payments have unique idempotency keys and references; replay returns the existing payment rather than creating another pick list/job. A key belonging to another order is rejected, and reusing a key is not a mechanism for changing a payment payload.
7. **How do you avoid floating-point and time bugs?** Money uses Decimal, two decimal places and ROUND_HALF_UP, with JSON money strings. Timestamps are UTC, but business days, warranty dates and reporting/month boundaries use Asia/Kolkata (`core/dates.py` and service period helpers).
8. **Why are invoice numbers gapless?** `repositories/invoices.py` inserts an FY sequence row if missing and locks it before incrementing, inside the invoice transaction. Rollback also rolls back the increment; invoices have no update/delete route, and corrections still need future credit-note support.
9. **What protects authentication and uploads?** Signed session cookies are HttpOnly and Secure in production, routes enforce roles and crew ownership, and Nginx applies limits and security headers. Installation uploads use magic-byte/size checks and random private storage keys; these checks are not a full image decoder or malware scanner.
10. **What do the tests prove and miss?** The current fresh-clone run has 230 passing tests and 90% statement coverage of `app/services`, using a real isolated Postgres database. They cover workflow rules and API authentication, but do not prove a finished UI, independent customer confirmation, arbitrary production capacity, or a complete penetration test.

## Round 3 — Functionality and growth

1. **What happens if the warehouse scans the wrong model?** The service compares the unit's product against the order lines and returns `SERIAL_WRONG_PRODUCT`. Stock remains unchanged and the warehouse can scan the correct unit.
2. **Can you send a partially scanned order?** No: every serialized line must be complete, and all bulk stock must be available before deductions. `services/dispatch.py` rejects the action with `SCAN_INCOMPLETE` or `INSUFFICIENT_STOCK` in the same transaction.
3. **Can two crews book the same technician?** A scheduled/in-progress job blocks another job for that technician on the same IST date. Managers can reschedule an eligible job, replacing crew assignments and taking a fresh hourly-rate snapshot.
4. **What does a completed installation prove?** The assigned crew recorded a passed power test, capacity, at least one photo and a PNG signature within the configured limits. Elapsed hours round up to a quarter hour and feed cost/pay calculations; this does not verify that the signature is authentic or the image is nonblank beyond the size heuristic.
5. **Does free warranty work affect profit?** Yes: part/replacement costs and assigned-technician labour cost reduce the original job's profit even when customer charges are zero. Repair labour cost in this view uses the technician's current rate, so it is less historically stable than installation rate snapshots.
6. **How do you keep GST consistent?** Invoice lines copy the saved order or repair charges; intra-state GST splits into half-up CGST and the remainder SGST, otherwise IGST. Financial years start in April, and order invoices are created on the current IST date at delivery rather than a backdated delivery timestamp.
7. **How do subsidies and payroll stay controlled?** Subsidy transitions require the next step and the relevant documents/installation state, and disbursement cannot exceed sanctioned amount. Draft pay runs can be recalculated; paid runs are locked, and repair pay uses per-visit labour charge timestamps to avoid paying cumulative reopened work twice.
8. **What does the load test support?** The recorded laptop/dev run sustained about 119.5 total requests/second across three read endpoints at 50 virtual users, with 0% errors and all endpoint p95s below a second. It does not measure write contention, 10,000 concurrent users or production TLS/proxy behavior.
9. **How would you scale it?** Start with workers/replicas and database/query measurements, then PgBouncer and a dashboard read replica/cache as needed; evidence storage must be shared and release migrations coordinated. Fixed development host ports cannot be replicated unchanged, and a queue for outbound messages is a later boundary worth separating.
10. **What would you change with more time?** Complete the role screens and browser tests, add stronger evidence validation and orphan cleanup, snapshot warranty labour cost, and review token revocation/CSRF and production infrastructure. Then implement credit notes, HSN and queued notifications around actual customer needs rather than adding microservices prematurely.

## If you do not know

“I have not verified that yet; here is what the code currently guarantees, and here is the specific measurement or test I would run before promising more.”

Evidence: [decisions](decisions.md), [API handoff](api-changelog.md), [dependency audit](security-audit.md), [load run](loadtest.md), [fresh-clone check](fresh-clone-check.md), and the actual services/models/tests under `backend/`.
