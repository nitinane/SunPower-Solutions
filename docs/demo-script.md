# Five-minute demo

## Before the room opens

Use a disposable demo database. Run the demo reset documented in the README, then rehearse twice. Reset again after rehearsal: these actions accept a quote, take money, deliver stock and close tickets. Never reset a real customer database.

The role pages currently say “Placeholder”; there are no functioning quote, dispatch or dashboard buttons to click in this checkout. Present the working backend in Swagger at `/api/docs` (not `/docs`). The screen names below are the handoff targets for the frontend; the exact working clicks are the Swagger fallback beside each step. Do not claim the UI is finished. If Swagger's CDN assets are unavailable, use its displayed request examples with a cookie-capable HTTP client against the same endpoints.

Open four separate browser profiles/windows with independent cookie jars at `http://localhost/api/docs` (or the deployed origin + `/api/docs`). In each, expand **auth → POST /api/v1/auth/login → Try it out**, replace the body, click **Execute**. Use `office@sunpower.in`, `warehouse@sunpower.in`, `support@sunpower.in`, and `director@sunpower.in` respectively; every password is **see DEMO_PASSWORD**, not a password embedded in this document. A manager login is `manager@sunpower.in`; technicians are `tech1@sunpower.in`, `tech2@sunpower.in`, `tech3@sunpower.in`. Swagger uses the returned HttpOnly cookie automatically; there is no bearer token to paste into Authorize.

An isolated tech2 browser is useful for a live repair resolution. Prepare the profiles before starting the clock; several logins from the same IP can hit Nginx's 5/minute limit. Check `/api/v1/auth/me` in each profile. Keep IDs and response panels ready. For every operation below, expand the stated method, click **Try it out**, enter path/query/body values and click **Execute**.

Preflight records (fetch IDs rather than assuming a database has never been used):

| Record | Lookup and what to keep |
| --- | --- |
| Fatima Begum, survey waiting for approval | Office: `GET /api/v1/enquiries?search=Fatima`, then `GET /api/v1/surveys?enquiry_id=<id>`; keep submitted survey id. |
| A 2 kW on-grid package | Office: `GET /api/v1/packages?package_type=on_grid&kw=2`; keep the first package id. |
| Venkatesh Goud, sent quote | Office: find enquiry with `search=Venkatesh`, then `GET /api/v1/quotes?enquiry_id=<id>`; keep sent quote id. |
| Ravi Kumar (demo), expired inverter | Support: `GET /api/v1/support/search?q=INV-3K-0001`; keep customer id and assigned inverter ticket id. Fresh reset ticket number is TKT-000002. |
| Kavitha Naidu, repair waiting for confirmation | Support: `GET /api/v1/support/search?q=Kavitha`; keep resolved ticket id. Fresh reset ticket number is TKT-000003. |
| Available serials for Venkatesh's 4 kW order | After a fresh reset, `INV-4K-0001` and `CC-MPPT-40-0006` are unused. Wrong product example: `BAT-150AH-0004`. If the demo has been used, reset it first. |

Anil Yadav already has delivery warranties and an invoice, Priya Sharma is paid awaiting dispatch, Lakshmi Reddy has an overdue enquiry, and Mohammed Irfan has a completed warranty replacement. Keep these as backup examples. The manager can show `GET /api/v1/schedule?from=<today>&to=<today>` and a technician can show `GET /api/v1/me/today` if asked after the timed demo. Dates are Asia/Kolkata business dates.

## 0:00–0:40 — Office: the approval gate

Target screen: Office → Surveys → Fatima Begum → Create quote. This screen is pending; use **quotes → POST /api/v1/quotes** in the office Swagger profile.

```json
{"survey_id":2,"package_id":2,"include_installation":true}
```

These are the verified IDs after a fresh reset; replace them with the numeric IDs from preflight if they differ. Show **409 SURVEY_NOT_APPROVED**, with no quote created. Do not approve Fatima during this demo.

Say: “We cannot promise a priced system until someone has approved the actual roof survey.”

## 0:40–1:20 — Office: one payment creates two work queues

Target screen: Office → Quotes → Venkatesh Goud → Accept → Record payment. Swagger: **POST /api/v1/quotes/{quote_id}/accept** for Venkatesh's sent quote. Copy `order_id`. Then **orders → POST /api/v1/orders/{order_id}/payments**:

```json
{"amount":"1000.00","method":"cash"}
```

Set the optional `Idempotency-Key` header to `demo-venkatesh-first-payment` so a click retry is safe. Show `payment.kind=advance`, `order.status=confirmed`, `pick_list.id` and `installation_job.id` in the one response. Keep the pick list id for the warehouse. Do not create this payment on an already confirmed seeded order; use the newly accepted Venkatesh order.

Say: “Recording the first advance creates the pick list and crew job together, so neither team waits for a second entry.”

## 1:20–1:55 — Warehouse: reject the wrong serial

Target screen: Warehouse → Pick lists → Venkatesh → Scan. Swagger warehouse profile: **GET /api/v1/dispatches/{id}**, then **POST /api/v1/dispatches/{id}/scan**:

```json
{"serial":"BAT-150AH-0004"}
```

Show **409 SERIAL_WRONG_PRODUCT**. Repeat with `{"serial":"INV-4K-0001"}` and then `{"serial":"CC-MPPT-40-0006"}`. Both should return 200. Show that each serialized line is fully scanned; bulk lines do not require serial scans.

Say: “The scanner knows this order needs a 4 kW inverter, and stops a battery from being sent by mistake.”

## 1:55–2:35 — Warehouse and Office: delivery starts coverage and billing

Target screen: Warehouse → Send → Deliver; Office → Invoices. Swagger warehouse profile: **POST /api/v1/dispatches/{id}/send**, then **POST /api/v1/dispatches/{id}/deliver**:

```json
{"receiver_name":"Venkatesh Goud"}
```

Show `warranties_created` and the warranty dates in the delivery response. In office profile use **GET /api/v1/invoices?search=Venkatesh**, then **GET /api/v1/invoices/{id}**. Invoice search accepts customer name, invoice number or phone digits, not order number. Show GST split and the `INV/<financial year>/<sequence>` number. The response contains invoice data; there is no server PDF and the current placeholder UI cannot print a finished invoice screen.

Say: “Delivery is the single event that starts the warranties and issues the GST invoice.”

## 2:35–3:20 — Support: serial to expired warranty to exact bill

Target screen: Support → Search → Serial → Repair. Swagger support profile: **GET /api/v1/support/search?q=INV-3K-0001**. Show Ravi Kumar (demo), the inverter's expired warranty, and its assigned repair ticket. Open **GET /api/v1/tickets/{id}** for that inverter ticket; show `under_warranty=false` and `coverage_label`.

In the pre-authenticated tech2 profile, **POST /api/v1/tickets/{id}/resolve**:

```json
{"work_notes":"Reset inverter and verified stable output","labour_hours":"1.00","parts":[]}
```

Show labour 500.00, GST 90.00 and total 590.00 with default settings. If labour settings differ, use the response values. The seeded ticket is already assigned to tech2; do not create a duplicate ticket just for this demonstration.

Say: “One serial finds the customer and expired coverage; the server calculates a bill from the recorded work.”

## 3:20–4:05 — Support: work done is not customer-confirmed

Target screen: Support → Kavitha Naidu → Resolved repair → Customer confirmation. Swagger support profile: **GET /api/v1/tickets/{Kavitha resolved ticket id}**. Show `status=resolved` and `total=0.00` because it was opened under warranty. There is no “technician closes ticket” endpoint.

Use **POST /api/v1/tickets/{id}/confirm**:

```json
{"confirmed":true,"customer_name":"Kavitha Naidu","note":"Customer confirms the output is stable"}
```

Show `status=closed`, confirmation name and timestamp. Explain that `confirmed=false` would reopen it. This is a staff-recorded customer statement, not a customer-authenticated portal action.

Say: “The technician can finish the work, but the repair stays open until support records the customer's confirmation.”

## 4:05–5:00 — Director: profit and a revocable share

Target screen: Director → Dashboard → Month → Profit ascending → Share. Swagger director profile: **GET /api/v1/dashboard/summary?period=month&sort=profit_asc**. Show `profit_per_job` including `material_cost`, `labour_cost`, `warranty_service_cost`, and the stock purchases card. Point to Mohammed Irfan's replacement cost; a cost can reduce profit even though the customer paid zero for the warranty repair. If a row is negative, point it out; do not promise a seeded loss if the values are positive.

Use **POST /api/v1/dashboard/share**:

```json
{"period":"month","expires_in_hours":24}
```

Keep returned `id` and token from `url=/share/<token>`. The `/share/...` frontend page is not implemented yet. In a private window open **`/api/v1/public/dashboard/<token>`** to show the working read-only JSON summary without a login. Back in the director profile, **DELETE /api/v1/dashboard/share/{id}**, then refresh the private window to show 404. Swagger fallback is the same public GET operation, with no login in that profile.

Say: “We can see margin after installation and warranty costs, then share a read-only view that expires or can be revoked.”

End: “The backend enforces the chain; the remaining frontend work is connecting these API contracts to the role screens.”
