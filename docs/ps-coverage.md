# Problem-statement coverage audit

Audited 2026-11-01 against [problem-statement.pdf](problem-statement.pdf), the actual routes,
services and PostgreSQL-backed tests. R1–R20 use the requirement numbering in BUILD_PLAN.md.
**17 DONE / 3 PARTIAL / 0 MISSING.** DONE means a passing test proves the core backend rule;
it does not claim a finished frontend or production deployment. PARTIAL records an essential
delivery gap even where the backend portion has passing tests. No requirement is wholly absent.

Endpoint paths below have the `/api/v1` prefix. Service names refer to
`backend/app/services/<module>.py`; test names refer to `backend/tests/<file>.py`.
The [frontend checklist](frontend-checklist.md) contains exact roles, inputs, output fields,
status gates and errors from the [live OpenAPI snapshot](openapi-audit.json).

## Evidence

| R# | Requirement | Status | Endpoints and service functions | Passing tests | Gap / boundary |
| --- | --- | --- | --- | --- | --- |
| R1 | Enquiries from web, calls and WhatsApp persist with contact, address, kW and subsidy needs | DONE | POST `/enquiries/public`, POST/GET `/enquiries`, GET `/enquiries/{enquiry_id}`, GET `/enquiries/{enquiry_id}/history`; `enquiries.create_public_enquiry`, `create_staff_enquiry`, `close_enquiry` | `test_ps_audit::test_enquiry_sources_retained_with_history` (all three sources, both customer types); `test_e2e_chain::test_public_enquiry_to_closed_repair_and_dashboard` | Calls and WhatsApp are logged by staff; there is no WhatsApp webhook. Retries retain one record and closing retains the row and history; frontend inbox still needs implementation. |
| R2 | Qualification records shadow-free roof area, bill and suitable grid | DONE | POST `/enquiries/{enquiry_id}/qualification`; `enquiries.record_qualification` | `test_orders_payments::test_qualification_requires_all_call_checks`; `test_e2e_chain::test_public_enquiry_to_closed_repair_and_dashboard` | Missing checks are rejected with field errors; grid=false cannot qualify. |
| R3 | Technician measures direction, tilt and cable distance; survey reviewed | DONE | POST `/enquiries/{enquiry_id}/surveys`, GET `/surveys`, POST `/surveys/{survey_id}/submit`, POST `/surveys/{survey_id}/approve` or `/reject`; `surveys.schedule_survey`, `submit_survey`, `_review` | `test_e2e_chain::test_public_enquiry_to_closed_repair_and_dashboard` | Assigned technician submits; director/admin reviews. Manager is not a reviewer. |
| R4 | Quote blocked until approved survey | DONE | POST `/quotes`; `quotes.create_quote` | `test_quotes::test_survey_not_approved_is_409`; `test_e2e_chain::test_public_enquiry_to_closed_repair_and_dashboard` | Server returns SURVEY_NOT_APPROVED, independent of UI. |
| R5 | Ready packages automatically expand exact parts and installation service | DONE | GET `/packages`, POST `/quotes`, GET `/quotes/{quote_id}`; `catalog.list_packages`, `quotes.create_quote` | `test_quotes::test_5kw_on_grid_parts_list`, `test_off_grid_has_batteries_and_panel_set_has_no_inverter`, `test_include_installation_adds_service_at_18_percent`, `test_seed_catalog_twice_is_idempotent` | Seed supplies panel set/on-grid/off-grid 1–5 kW and installation service. Quote print UI remains frontend work. |
| R6 | Advance/full payment confirms order | DONE | POST `/quotes/{quote_id}/accept`, POST `/orders/{order_id}/payments`; `quotes.accept_quote`, `orders.record_payment` | `test_orders_payments::test_advance_then_balance_starts_work_once`, `test_first_full_payment`, `test_overpayment_changes_nothing`, `test_idempotent_retry_returns_existing_payment` | Server selects advance/full/balance kind and enforces exact balance. |
| R7 | Confirmation creates warehouse packing work and crew job without a phone call | DONE | POST `/orders/{order_id}/payments`, GET `/dispatches`, GET `/orders/{order_id}`, POST `/installation-jobs/{job_id}/schedule`, GET `/me/today`; `orders.record_payment`, `schedule.schedule_job`, `my_today` | `test_orders_payments::test_advance_then_balance_starts_work_once`; `test_installations::test_me_today_shows_only_my_items`; `test_ps_audit::test_manager_can_load_crew_dropdown_without_private_costs` | Payment creates a planned, unscheduled job. Manager selects date/crew before it appears in that technician's day. Manager now has access to the active employee picker. |
| R8 | Inverter, battery and controller serial scanning and customer traceability | DONE | POST `/dispatches/{dispatch_id}/scan`, POST `/dispatches/{dispatch_id}/send`, GET `/support/search`, POST `/stock/receipts`; `dispatch.scan`, `send`, `tickets.search`, `stock.create_receipt` | `test_dispatch::test_unknown_and_wrong_product_serial`, `test_unavailable_serial`, `test_send_blocked_until_all_scanned`, `test_scan_normalized_idempotent_and_line_limit`; `test_stock::test_receipt_adds_stock_movements_and_cost_price`; `test_tickets::test_support_search_phone_serial_and_name` | All requires-serial lines must be complete. Camera UI is not implemented; API accepts typed/scanner serial text. |
| R9 | Delivery automatically starts per-unit warranties, 24 months equipment / 240 months panels | DONE | POST `/dispatches/{dispatch_id}/deliver`; `dispatch.deliver`, `warranties.create_for_delivery` | `test_dispatch::test_delivery_creates_serial_and_bulk_warranties_in_ist`, `test_warranty_failure_rolls_back_delivery`; `test_dates::test_add_months` | Inverter/panel dates and count are asserted; battery uses the same product warranty-month rule. Panel coverage is one quantity-bearing order-line record, not one serial per panel. |
| R10 | Phone/tablet installation form, times, kW, power test, roof photos, homeowner signature and installed equipment | PARTIAL | GET `/installation-jobs/{job_id}`, POST `/installation-jobs/{job_id}/start`, `/photos`, `/complete`, GET `/evidence/{evidence_id}/file`; `installations.start_job`, `add_photo`, `complete_job`, `get_job_read` | `test_installations::test_photo_type_from_bytes_and_size_limit`, `test_complete_needs_photo_power_test_and_real_signature`, `test_hours_rounded_up_rate_snapshot_and_dashboard_labour`, `test_start_needs_delivery_and_crew_membership` | Backend works, with server-recorded start/finish and installed serials. Phone UI/signature canvas and authenticated customer view are absent. Despite the test name, signature checks prove PNG prefix/size/base64 checks, not decoded nonblank image content. |
| R11 | Support finds customer, exact serial and warranty quickly | DONE | GET `/support/search?q=`; `tickets.search` | `test_tickets::test_support_search_phone_serial_and_name`; `test_replacement::test_under_warranty_swap_is_free_and_keeps_end_date` | Phone normalization, exact normalized serial and name-prefix search; max 10 results. Local search p95 was 625 ms in [loadtest.md](loadtest.md), not a production guarantee. |
| R12 | Warranty repair/replacement free; expired coverage bills parts and labour | DONE | POST `/tickets`, POST `/tickets/{ticket_id}/assign`, `/replace-unit`, `/resolve`; `tickets.create_ticket`, `replace_unit`, `resolve` | `test_tickets::test_under_warranty_free_but_parts_consumed`, `test_expired_warranty_billed_exactly`; `test_replacement::test_under_warranty_swap_is_free_and_keeps_end_date`, `test_out_of_warranty_swap_billed_with_full_new_warranty` | Parts and labour pricing is automatic and tested. Support/technician parts-selection API is a UI integration gap listed below; existing actions require product IDs. |
| R13 | Complaint remains a ticket until customer confirms working | DONE | POST `/tickets/{ticket_id}/resolve`, POST `/tickets/{ticket_id}/confirm`; `tickets.resolve`, `confirm` | `test_tickets::test_confirmation_is_only_close_path_and_rejection_reopens`, `test_technician_access_is_own_only` | Confirmation is recorded by Support/Office after customer contact; it is not an independently authenticated customer action. False reopens the complaint. |
| R14 | Director sees profits/losses, unfinished stages, advances, purchases and technician hours | DONE | GET `/dashboard/summary?period=month&sort=profit_asc`; `dashboard.summary`, `repositories/dashboard.summary_blocks` | `test_dashboard::test_profit_uses_snapshots_and_labour_sql`, `test_free_warranty_replacement_lowers_profit_and_sorts_first`, `test_stock_purchases_card_is_exact`, `test_advance_and_technician_hours_cards_use_period_not_order_date` | Added separate advance_payments and technician_hours cards. Profit rows capped at 50; warranty labour cost uses current technician rate, as previously documented. |
| R15 | Invoices ready to send | PARTIAL | GET `/invoices`, GET `/invoices/{invoice_id}`, POST `/orders/{order_id}/invoice`; `invoices.create_for_order`, `create_for_ticket`, `to_read` | `test_invoices::test_delivery_creates_one_invoice_equal_to_order_igst_out_of_state`, `test_numbers_are_consecutive_and_reset_each_financial_year`, `test_paid_repair_gets_service_invoice_warranty_repair_none`, `test_backfill_endpoint_idempotent_and_needs_delivery` | Immutable GST invoice JSON and seller/buyer/line/tax/payment data are ready. No rendered print/PDF view or send integration exists; frontend must render a printable invoice. |
| R16 | Subsidy paperwork and stages tracked | DONE | GET `/subsidies`, GET `/subsidies/{subsidy_id}`, POST `/orders/{order_id}/subsidy`, PATCH `/subsidies/{subsidy_id}/documents/{doc_type}`, POST `/subsidies/{subsidy_id}/documents/{doc_type}/file`, POST `/subsidies/{subsidy_id}/advance`; `subsidies.create_on_first_payment`, `set_document`, `upload_document`, `advance` | `test_subsidies::test_auto_created_on_first_payment_only_when_requested`, `test_applied_blocked_until_documents_received`, `test_inspection_needs_completed_install_and_certificate`, `test_skipping_a_step_and_rejection_reason`, `test_document_file_upload_rules` | File upload exists; no subsidy document retrieval endpoint yet. |
| R17 | Monthly technician pay from installation and repair hours | DONE | POST/GET `/pay-runs`, GET `/pay-runs/{run_id}`, POST `/pay-runs/{run_id}/mark-paid`, GET `/me/pay`; `technician_pay.calculate`, `mark_paid`, `my_pay` | `test_pay::test_exact_amount_two_jobs_one_repair_and_ist_month`, `test_recalculation_replaces_lines_and_paid_run_is_locked`, `test_technician_sees_only_own_pay_and_non_director_403` | Install rates are booking snapshots; repair rates are current rates. This records payment, not a bank transfer. |
| R18 | Today/week/month, profit/jobs/open repairs and read-only sharing | DONE | GET `/dashboard/summary`, POST `/dashboard/share`, DELETE `/dashboard/share/{share_id}`, GET `/public/dashboard/{token}`; `dashboard.summary`, `create_share`, `revoke`, `public_summary` | `test_dashboard::test_period_boundaries_are_ist`, `test_share_public_expired_revoked_and_unknown_are_identical`, `test_dashboard_director_only_and_expiry_limit` | Links are hashed, expiring, revocable, live read-only summaries. Frontend `/share/:token` route still required. |
| R19 | Homes and small factories supported | DONE | POST `/enquiries/public`, POST `/enquiries`; `enquiries.create_public_enquiry`, `create_staff_enquiry` | `test_ps_audit::test_enquiry_sources_retained_with_history` (home/factory for every source) | customer_type is persisted on the enquiry; both use the same downstream workflow. No separate industrial design/engineering module is claimed. |
| R20 | Production-ready: deployed, secure, tested | PARTIAL | POST `/auth/login`, GET `/auth/me`, `/auth/logout` (POST), GET `/health/ready` and `/api/health/ready`; `auth.login`, `core/deps.get_current_user`, `require_role`, `main.create_app` | `test_route_protection::test_private_route_requires_cookie`, `test_session_cookie_flags`, `test_production_cors`, `test_readiness`, `test_readiness_dependency_failure`, `test_unexpected_error_hides_details`; full suite below | Deployment configuration and local fresh-clone evidence exist. No live URL, server rollout, real HTTPS mobile checks or green remote CI were independently verified in this audit. |

## Small gaps fixed

1. Manager crew/visit assignment screens could not fetch `/users` although the role can schedule
   jobs and assign repairs. Added manager to this existing read-only endpoint. Its response still
   contains only id, full_name, role and phone; the regression test also checks technicians remain forbidden.
2. Director cards exposed all received payments and stock purchases but lacked separate advances
   and hours. Added Decimal-string `advance_payments` and `technician_hours` in the existing cards
   query, including the public summary. No additional query per card and no database changes.
3. Added six HTTP regression cases proving web/phone/WhatsApp inputs, both home/factory values,
   idempotent retry, inbox visibility, preserved kW/subsidy and retained closed-record audit history.

Advance totals mean completed payments whose **payment_type=advance**, selected by paid_at.
They exclude full and balance payments, and do not represent outstanding receivables. Hours are
**person-hours**: sum each crew member's hours for installations completed within the period plus
one labour-charge quantity per repair visit created within the period. Reopened visits count once
per performed visit. These metrics use the same IST period start / current-time exclusive end as
the other timestamp cards; they do not depend on when an order was confirmed.

## Verification

- Baseline: `docker compose exec api python -m pytest -q` — **230 passed**, 2 dependency deprecation warnings.
- Targeted: `docker compose exec api python -m pytest -q tests/test_ps_audit.py tests/test_dashboard.py`
  — **15 passed**, after correcting a test's comparison of equivalent Decimal strings (`3.0` / `3.00`).
- Final: `docker compose exec api python -m pytest -q` — **238 passed**, same 2 warnings.
- `docker compose exec api ruff check app tests` — clean.
- HTTP GET `/api/openapi.json` — captured 76 operations / 132 component schemas after restarting
  the local API with the changed response schema. Contract used for all 23 frontend screen checklists.
- Production storage default unchanged; tests use the session's temporary directory.
- No database migration, no production data changes, no frontend source edits and no deployment.

## Roadmap

- R10: implement and device-test the mobile installation form, camera uploads, signature canvas,
  installed-equipment display and customer access; this crosses frontend, authentication and acceptance testing.
- R10: decode and validate image contents, reject blank signatures and safely handle malformed images;
  current magic-byte/size checks do not prove a valid signed image. Choose an image decoder and limits with tests.
- R15: implement quote/invoice browser print layouts and file export; add email/WhatsApp delivery only
  with provider configuration and delivery/error handling. The API currently returns printable data, not a document.
- R20: deploy to the actual HTTPS domain, replace production placeholders/secrets, verify backups and
  storage permissions, confirm current CI and rehearse on real mobile devices; no deployed URL is supplied here.
- R12: agree a minimal read-only parts picker for Support/Technician with product ID/name/stock and permitted
  pricing, without exposing purchase costs; then wire it to repair forms. Neither role can currently load `/stock`
  or `/packages`, so the checklist explicitly avoids inventing a catalog endpoint.
- R16: add authorized subsidy-document retrieval with an ownership/access policy and file-not-found handling;
  uploads currently return a private storage key, not a downloadable URL.
- R18: add share-link history/listing if revocation must survive losing the creation response's id.
- R13: agree an Office ticket read/confirmation queue policy; Office can create/confirm but cannot
  list/read tickets, so the current confirmation action needs a resolved ticket ID from Support.
- All roles: complete and test the placeholder frontend screens against [frontend-checklist.md](frontend-checklist.md).
- Optional integrations already deferred: WhatsApp Business API ingestion, SMS (DLT), customer tracking links,
  QR stickers, estimates, credit notes and HSN invoice codes. Staff-entered WhatsApp enquiries work today.

The larger items require interface/access decisions, UI implementation, new dependencies, external
credentials or real deployment validation; they are not represented as completed backend fixes.
