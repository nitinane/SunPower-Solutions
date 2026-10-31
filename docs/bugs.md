# Click-test bug list

- **Date:** 2026-11-01
- **Commit tested:** `bbe55e4` (branch `frontend`)
- **How:** Playwright 1.64.1 (Chromium) driving the real app at http://localhost:5173 against fresh demo data
  (`scripts/demo_reset.ps1`). Port 5173 was already held by a local `npm run dev` (vite, same code,
  proxying `/api` to `localhost:8000`), so the `frontend-dev` container could not bind; the remaining reset steps
  (migrate, seed, seed_demo) were run by hand and the tests ran against that vite server.
- **Re-run:** reset demo data first (the chain uses a fixed phone number), then `cd e2e; npx playwright test`.
  Logs per test: `e2e/artifacts/log-*.json`; screenshots: `e2e/artifacts/*.png`.

## Totals

| Severity | Count |
| --- | --- |
| blocker | 2 |
| major | 6 |
| minor | 6 |
| cosmetic | 3 |
| **total** | **17** |

## Passed checks

Demo chain (Test A)
- Public enquiry (no login) returns reference `ENQ-000010`.
- Same phone submitted again: no second enquiry (DB has 1 row; same reference returned).
- Office inbox shows the enquiry: new, Website, 3.00 kW, Home, On Grid.
- Call sheet (400 sq ft, ₹3000 bill, grid suitable) -> qualified.
- Survey booked with Raju Technician (tech1) for tomorrow.
- tech1 My day -> "All my surveys" lists the survey; opens it.
- Survey submitted: south, 15°, 20 m -> submitted.
- Director approves the survey.
- Quote builder: 3 kW on-grid + installation -> parts list (≥10 lines incl. panels, 3 kW inverter, installation) appears automatically.
- Quote sent; printable view opens and Print calls `window.print()`.
- Quote accepted -> order ORD-000006 created.
- Advance ₹50,000 UPI with reference recorded -> balance ₹130,900.40 due; pick list and installation job are created.
- Warehouse opens the order's dispatch from the list.
- Wrong-product serial (INV-1K) -> visible error "This is a INV-1K; this order needs INV-3K, CC-MPPT-40" (409 `SERIAL_WRONG_PRODUCT`, expected).
- Send is disabled while scans are incomplete.
- Correct serials (DSD-INV3K-1001, CC-MPPT-40-0005) -> counters complete.
- Undo one scan, counter drops, Send disabled again, re-scan completes it.
- Send dispatch -> dispatched.
- Deliver (receiver "Test Customer") -> warranties shown: 2-year equipment and 20-year panel warranties.
- Crew calendar shows the job with Raju + Kiran (state for this was prepared via API, see BUG-001).
- Booking tech1 on ORD-000002 the same day -> double-booking error shown ("Raju Technician already has ORD-000006 on 1 Nov", 409 `TECHNICIAN_DOUBLE_BOOKED`, expected).
- tech1 My day lists the job; opens it.
- Start installation -> in_progress.
- Small PNG photo upload -> Photo link shown.
- Complete is disabled while the signature is empty.
- Signature drawn -> Complete -> completed.
- Support search by phone, inverter serial and "Test Customer" each find the customer with warranty "active".
- Ticket on the inverter (fault E-01) created; assigned to tech1; tech1 sees it in My day.
- tech1 resolves (1 h) -> support "not fixed" -> back to open -> re-assigned -> resolved -> confirmed -> closed.
- Ticket total ₹0.00, under warranty.
- Director dashboard today / week / month lists ORD-000006 in profit per job.
- Share link created (201); opens without login showing numbers.
- Revoked link then shows "Report unavailable".

Role smoke (Test B): every sidebar link opened without a crash screen, blank page, endless spinner, "undefined"/"NaN"/"[object Object]" text or broken icon, for
director, manager, office, warehouse, tech1 and support (problems listed below). All tabs on /office/*, /director/* and Settings opened.

Mobile (Test C): no horizontal page scroll on any field screen at 360x740 (tech1: today, survey, job, ticket; warehouse: dispatches, dispatch detail, receiving, inventory).

---

### BUG-001 [blocker] Manager cannot book the crew for the demo order once it has been delivered
- Role / screen / URL: manager / Crew calendar "Book pending job" / `/manager/schedule`
- Steps: Run the chain to step 6 (order ORD-000006 delivered), log in as manager, open `/manager/schedule`, open "Confirmed order".
- Expected: The order's planned installation job can be picked and booked for tech1 + tech2 today.
- Actual: The dropdown only lists `confirmed` orders (`GET /api/v1/orders?status=confirmed`), so ORD-000006 (status `delivered`, job `planned`) and seed ORD-000003 (delivered, planned) never appear. Only ORD-000002 is offered. The demo chain cannot continue in the UI. State prepared via API: `POST /installation-jobs/6/schedule` succeeded, so the backend accepts it.
- Screenshot: e2e/artifacts/a07-crew-calendar-assign-tech1-tech2-to-the-new-job-today.png
- Likely layer: frontend, `frontend/src/pages/manager/ManagerPages.tsx` (`/orders?status=confirmed`). Should list jobs in `planned`/`scheduled`, or orders in confirmed/dispatched/delivered.
- PDF requirement: R7
- Status: fixed in `fix(BUG-001): list all planned installation jobs`

### BUG-002 [blocker] Opening an invoice crashes the Office page
- Role / screen / URL: office / Invoices / `/office/invoices`
- Steps: Office -> Invoices -> click `INV/2026-27/000001 · Test Customer`.
- Expected: Printable GST invoice view with a Print / Save PDF button.
- Actual: The whole page is replaced by the React Router error screen. Console: `Error: Objects are not valid as a React child (found: object with keys {id, address_line1, address_line2, city, state, pincode})`. The UI renders `invoice.data.buyer.address`, but the API returns the address as an object.
- Screenshot: e2e/artifacts/a11-invoice-invoices-list-contains-the-order-invoice-printable-view-open.png
- Likely layer: contract mismatch. `frontend/src/pages/office/OfficePage.tsx` InvoicesTab (`{invoice.data.buyer.address}`) and the `Invoice` type in `frontend/src/api/sales.ts` vs `GET /api/v1/invoices/{id}`.
- PDF requirement: R15
- Status: fixed in `fix(BUG-002): render invoice address fields`

### BUG-003 [major] Customer search crashes the Customers page; Repairs search shows a blank customer
- Role / screen / URL: office and support / Customers / `/customers`. Also office / Repairs / `/office/repairs`.
- Steps: Customers -> search `9123456780`. Office -> Repairs -> search `9123456780`.
- Expected: Customer card with name, phone, sites, orders, units and warranty.
- Actual: `/customers` crashes to the React Router error screen. Console: `TypeError: Cannot read properties of undefined (reading 'slice')` at OperationsPage.tsx (`match.customer.full_name.slice(0,1)`). On Repairs the card heading is just "·" (name and phone empty). `GET /api/v1/support/search` returns `customer: {id, name, phone, email}`, but the frontend reads `full_name` / `phone_e164`.
- Screenshot: e2e/artifacts/a02-office-inbox-customer-created-customers-search.png, e2e/artifacts/probe-office-repairs-search.png
- Likely layer: contract mismatch. `frontend/src/pages/operations/OperationsPage.tsx` (CustomersModule), `frontend/src/pages/office/OfficePage.tsx` (RepairsTab), `searchSupport` / `getCustomerMatches` types. The `/support` screen (field contracts) uses `name` and works.
- PDF requirement: R11
- Status: fixed in `fix(BUG-003): match support search customer fields`

### BUG-004 [major] Login sends manager, technician and warehouse users to the mock Owner dashboard
- Role / screen / URL: manager, tech1, warehouse / Login / `/login`
- Steps: Sign in as manager@, tech1@ or warehouse@.
- Expected: Their work screen (`/manager/schedule`, `/technician/today`, `/warehouse/dispatches`).
- Actual: All three land on `/`, the mock "Owner Workspace" with fake numbers. The login role map points to routes that do not exist (`/manager/calendar`, `/technician/day`, `/warehouse/pick`, `/technician/surveys`), which the `*` route redirects to `/`. Office, director and support land correctly.
- Screenshot: e2e/artifacts/a03-survey-submit-tech1-login-lands-on.png, e2e/artifacts/a06-dispatch-warehouse-login-lands-on.png, e2e/artifacts/a07-crew-calendar-manager-login-lands-on.png
- Likely layer: frontend, `frontend/src/pages/operations/OperationsPage.tsx` LoginPage `roleHome`.
- PDF requirement: R7, R10
- Status: fixed in `fix(BUG-004): send staff to existing role routes`

### BUG-005 [major] Field screens have no navigation and no sign-out
- Role / screen / URL: tech1 `/technician/today`, `/technician/jobs/:id`, `/technician/surveys/:id`, `/technician/tickets/:id`; warehouse `/warehouse/dispatches`, `/warehouse/receiving`; manager `/manager/schedule`; support `/support/tickets/:id`
- Steps: Open any of these from the sidebar.
- Expected: Staff sidebar (or a mobile header) to move between screens and sign out.
- Actual: The page renders without any sidebar, menu or sign-out. The only way out is the browser back button or typing a URL.
- Screenshot: e2e/artifacts/b-tech1-smoke-tech1-technician-today-page-has-no-sidebar-navigation.png, e2e/artifacts/b-warehouse-smoke-warehouse-warehouse-dispatches-page-has-no-sidebar-navigatio.png, e2e/artifacts/b-manager-smoke-manager-manager-schedule-page-has-no-sidebar-navigation.png
- Likely layer: frontend, `frontend/src/routes.field.tsx` (field routes are not wrapped in `StaffLayout`/`MobileLayout`).
- PDF requirement: R10
- Status: fixed in `fix(BUG-005): give field screens staff navigation and sign out`

### BUG-006 [major] Installations page always fails with "Pick at most 62 days"
- Role / screen / URL: office, manager, director / Installations / `/installations`
- Steps: Open Installations.
- Expected: Scheduled jobs for the default range.
- Actual: Error state on load. `GET /api/v1/schedule?from=2026-10-02&to=2026-12-31&page=1&page_size=100 -> 422 {"error":{"code":"validation_error","message":"Pick at most 62 days","fields":{"to":"Range too long"}}}`. The default range is today-30 to today+60 (91 days), but the backend allows at most 62.
- Screenshot: (no exception; see log `e2e/artifacts/log-b-office-smoke.json`)
- Likely layer: frontend, `frontend/src/pages/operations/OperationsPage.tsx` InstallationsModule `istDate(-30)` / `istDate(60)`.
- PDF requirement: R7
- Status: fixed in `fix(BUG-006): use a valid default schedule range`

### BUG-007 [major] New share link is never shown, only copied to the clipboard
- Role / screen / URL: director / Shared links / `/director/sharing`
- Steps: Pick a period -> "Create & copy link".
- Expected: The new URL is visible (with a copy button) so the director can send it.
- Actual: `POST /api/v1/dashboard/share -> 201` with the URL, but the page shows only "month report · Expires …" and no link. The URL is only written via `navigator.clipboard.writeText`. Where the clipboard is unavailable or denied (a non-HTTPS deployment, or a browser without permission), the link is lost: without clipboard permission the first run logged an unhandled `NotAllowedError: Failed to execute 'writeText' on 'Clipboard'`. The list endpoint deliberately does not return the URL, so it cannot be recovered.
- Screenshot: e2e/artifacts/a10-director-dashboard-new-share-link-is-visible-on-screen-not-only-copied-to-clipb.png
- Likely layer: frontend, `frontend/src/pages/director/DirectorPage.tsx` Shares.
- PDF requirement: R18
- Status: fixed in `fix(BUG-007): retain share URLs when copying fails`

### BUG-008 [major] Public enquiry page and shared report page show the staff sidebar
- Role / screen / URL: anonymous / `/public` and `/share/:token`
- Steps: Open either page without logging in.
- Expected: A clean public page. The shared report is read-only, with numbers only.
- Actual: Both pages render the full staff sidebar: Owner/Tech/Warehouse pills, AI Copilot, Owner Dashboard, Technician Demo, Warehouse Demo and Collapse Menu, which is 5 interactive controls on the "read-only" report. Each load calls `GET /api/v1/auth/me -> 401 {"error":{"code":"unauthorized","message":"Please log in"}}`, logged as a console error.
- Screenshot: e2e/artifacts/a10-director-dashboard-share-link-opens-read-only-without-login.png
- Likely layer: frontend, `frontend/src/layouts/PublicLayout.tsx` (renders `SharedSidebar`).
- PDF requirement: R18, R1
- Status: fixed in `fix(BUG-008): remove staff layout from public pages`

### BUG-009 [minor] Sales inbox does not show the subsidy request
- Role / screen / URL: office / Sales inbox / `/office/enquiries`
- Steps: Submit a public enquiry with "interested in a government subsidy" ticked; open the inbox.
- Expected: The card shows that a subsidy was requested.
- Actual: The card shows "3.00 kW · Home · On Grid · Website" and nothing about the subsidy, although `subsidy_requested` is stored.
- Screenshot: e2e/artifacts/a02-office-inbox-inbox-card-shows-subsidy-request.png
- Likely layer: frontend, `frontend/src/pages/office/OfficePage.tsx` EnquiriesTab card.
- PDF requirement: R1
- Status: fixed in `fix(BUG-009): show subsidy requests in the inbox`

### BUG-010 [minor] Survey form has no recommended system size field
- Role / screen / URL: tech1 / Field survey / `/technician/surveys/8`
- Steps: Open the survey.
- Expected: Fields for direction, tilt, cable distance and recommended kW (the test script asks for "recommended 3 kW").
- Actual: There is no recommended-kW field. The backend `SurveySubmit` also has no such field (`extra="forbid"`). The test put "Recommended system: 3 kW" in Findings instead.
- Screenshot: e2e/artifacts/a03-survey-submit-survey-form-has-a-recommended-kw-field.png
- Likely layer: backend + frontend (schema `backend/app/schemas/surveys.py`, `frontend/src/pages/technician/FieldPages.tsx`). The PDF R3 lists only direction, tilt and cable distance, so this is a demo-script gap.
- PDF requirement: R3
- Status: won't fix: PDF R3 lists only direction, tilt and cable distance

### BUG-011 [minor] Order screen shows pick list and job as raw JSON; accept alert shows an internal id
- Role / screen / URL: office / Orders & payments / `/office/orders`, and Quotes / `/office/quotes`
- Steps: Accept a quote; open the order.
- Expected: "Pick list DSP-… (draft)" and "Installation job #… (planned, not scheduled)", and the order number in the confirmation.
- Actual: `Pick list: {"id":6,"status":"draft"}` and `Installation job: {"id":6,"status":"planned","scheduled_date":null}`. The accept confirmation is a browser `alert("Order 6 created from quote.")` that shows the database id, not ORD-000006.
- Screenshot: e2e/artifacts/a05-quote-order-payment-pick-list-job-shown-readably-not-raw-json.png
- Likely layer: frontend, `frontend/src/pages/office/OfficePage.tsx` (OrdersTab `JSON.stringify`, QuotesTab `window.alert`).
- PDF requirement: R7, R6
- Status: fixed in `fix(BUG-011): display readable order workflow references`

### BUG-012 [minor] Delivery warranty list shows unit ids, not products
- Role / screen / URL: warehouse / Dispatch detail after delivery / `/warehouse/dispatches/6`
- Steps: Deliver the dispatch.
- Expected: Each warranty labelled with product / serial (e.g. "Solar inverter 3 kW DSD-INV3K-1001: 2026-11-01 – 2028-11-01").
- Actual: Lines read "Unit 5: 2026-11-01 – 2028-10-31", with unit ids or order-item ids and no product name, so the inverter and panel warranties cannot be told apart on screen.
- Screenshot: e2e/artifacts/a06-dispatch-warranty-list-names-the-product-not-only-unit-ids.png
- Likely layer: frontend (+ contract: `WarrantyRead` has no product name/serial), `frontend/src/pages/warehouse/Dispatches.tsx`.
- PDF requirement: R9
- Status: fixed in `fix(BUG-012): label delivery warranties with product and serial`

### BUG-013 [minor] My day logs a 404 on every load when there is no pay run
- Role / screen / URL: tech1 / My day / `/technician/today`
- Steps: Open My day in a month without a pay run.
- Expected: "No pay run for this month" without errors.
- Actual: The UI text is right, but every load does `GET /api/v1/me/pay?month=2026-11 -> 404 {"error":{"code":"not_found","message":"No pay run for 2026-11 yet"}}` and logs a console error.
- Screenshot: (log `e2e/artifacts/log-b-tech1-smoke.json`)
- Likely layer: contract mismatch. The backend uses 404 for "no data yet"; it could return 200 with `null`, or the frontend could skip the console noise.
- PDF requirement: R17
- Status: open

### BUG-014 [minor] Field screens on a phone: tap targets below 40 px, inventory table wider than screen
- Role / screen / URL: tech1 and warehouse at 360x740: `/technician/today`, `/technician/jobs/6`, `/warehouse/dispatches`, `/warehouse/dispatches/6`, `/inventory`
- Steps: Open the screens at 360x740.
- Expected: Controls at least ~40 px; all actions reachable without sideways scrolling.
- Actual: Work-item links are 15–20 px tall ("Test Customer · completed" 204x20, "TKT-000006 · closed" 121x15, "DSP-000006 · ORD-000006" 215x20). The "Power test passed" checkbox is 13x13. Back links "My day" (56x20) and "Pick lists" (66x20) and the photo link "Photo #7" (51x15) are small. On `/inventory` the table's "View lines" buttons sit at x=817 px inside a horizontally scrolling table (79x35), and the filter input is 36 px tall. No page-level horizontal scroll.
- Screenshot: e2e/artifacts/c-tech1-mobile-tech1-technician-today-controls-smaller-than-40-px.png, e2e/artifacts/c-tech1-mobile-tech1-technician-jobs-6-controls-smaller-than-40-px.png, e2e/artifacts/c-warehouse-mobile-warehouse-warehouse-dispatches-controls-smaller-than-40-px.png, e2e/artifacts/c-warehouse-mobile-warehouse-inventory-controls-cut-off-at-right-edge.png
- Likely layer: frontend, `frontend/src/pages/field/ui.tsx` (Page styles cover button/select only, not links/checkboxes) and OperationsPage inventory table.
- PDF requirement: R10
- Status: open

### BUG-015 [cosmetic] Dispatch scan counters show "1/1.000 scanned"
- Role / screen / URL: warehouse / Dispatch detail / `/warehouse/dispatches/6`
- Steps: Scan a serial.
- Expected: "1/1 scanned".
- Actual: "1/1.000 scanned", "0/1.000 scanned" (the qty decimal string is printed as is).
- Screenshot: (seen in check output; log `e2e/artifacts/log-a06-dispatch.json` from the first run)
- Likely layer: frontend, `frontend/src/pages/warehouse/Dispatches.tsx`.
- PDF requirement: R8
- Status: open

### BUG-016 [cosmetic] React warning on the Shared links form
- Role / screen / URL: director / Shared links / `/director/sharing`
- Steps: Open the tab.
- Expected: No console errors.
- Actual: Console: "Use the `defaultValue` or `value` props on <select> instead of setting `selected` on <option>." (Expires select, `<option value="72" selected>`).
- Screenshot: (log `e2e/artifacts/log-b-director-smoke.json`)
- Likely layer: frontend, `frontend/src/pages/director/DirectorPage.tsx` Shares.
- PDF requirement: R18
- Status: open

### BUG-017 [cosmetic] Sidebar background stops partway down long pages
- Role / screen / URL: office (any long staff page, e.g. `/office/quotes`)
- Steps: Open a page taller than the window; scroll down.
- Expected: Sidebar column fills the full page height.
- Actual: The white sidebar ends at about the window height (~720 px); below it the page background shows through.
- Screenshot: visible in e2e/artifacts/a05-quote-order-payment-pick-list-job-shown-readably-not-raw-json.png (full-page shot)
- Likely layer: frontend, `frontend/src/styles.css` (`.shared-sidebar` height / sticky).
- PDF requirement: —
- Status: open
