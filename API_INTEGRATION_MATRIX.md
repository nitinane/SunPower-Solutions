# Operations API integration matrix

Inspection snapshot before implementation (2026-11-01). All paths below are under `/api/v1`.

| Operations area | Existing backend | Existing frontend | Planned integration |
| --- | --- | --- | --- |
| Customers | `GET /customers/{customer_id}` exists but its repository is a stub; no list route. A malformed site POST route is present. Customer/site schemas and models exist. | `OperationsPage.tsx` uses four hardcoded customer records; detail history and site are fabricated. | Add paginated/searchable `GET /customers` and repair detail service to include actual sites and linked enquiry/order/job/warranty data. Do not expose site/customer writes absent a supported workflow. |
| Installations | Router, repository, service and schema are stubs. Models cover jobs, technicians, completion fields, and evidence metadata. | Four hardcoded jobs and fabricated progress/status filters. | Add list/detail reads with schedule/status filters, assignments, completion fields, and evidence metadata using existing models and status enum. Evidence bytes remain behind existing file storage authorization. |
| Inventory | Router, repository, service and schema are stubs. Models cover product balances, immutable movements, serialized units, dispatches. | Four hardcoded products/counts; stock receipt is a fake action. | Add read-only product inventory, movement history, serial lookup and dispatch detail reads. Do not expose stock mutation in this UI. |
| Reports | Dashboard router/repository/service/schema are stubs. Redis cache helper supports `dashboard_summary` (30s) and `financial_report` (60s). | All report numbers and bars are hardcoded “demo adapter” values. | Add database aggregates for requested metrics with SQL Decimal arithmetic; cache permission-scoped report reads through the existing Redis helper. |
| Settings | User router/repository/service/schema are stubs. `User` has profile/role/active fields but no preference/settings columns. Auth dependency and auth router are stubs. | Profile, company, preferences and user records are fabricated; save only shows a toast. | Add authenticated current-profile and role-authorized user list/detail reads. Preferences can only be browser-local because schema has no persistence. User writes are unavailable because no supported mutation service/policy exists. |

## Cross-cutting findings

- `GET /api/health/ready` is real; business routers are otherwise mostly stubs except customer detail, whose repository is currently a stub.
- `get_current_user` and `require_role` currently raise `NotImplementedError`; the frontend sends an optional bearer token but has no login screen. The seeded demo accounts use placeholder hashes, so they do not supply login credentials.
- Existing backend error envelope is `{ "error": { "code", "message", "fields" } }`; frontend `apiFetch` currently drops `fields` and does not distinguish unauthorized responses.
- Fixed enum values already live in `backend/app/core/enums.py`. No enum model module will be added.
- React Query is not currently installed, despite being part of the requested frontend stack; the implementation will add it as a direct dependency for the explicitly requested query/mutation behavior.
- Current UI includes fake create/edit/stock-receipt flows; they will be removed or made read-only where no corresponding supported backend operation exists, rather than showing successful fake writes.

## Delivered status

| Operations area | Live API and frontend status | Remaining backend limits |
| --- | --- | --- |
| Customers | Real `GET /customers` (paged/search) and `GET /customers/{id}` are wired to the demo rows, sites, enquiries, orders, jobs, and warranties. | Site/customer writes remain unavailable. |
| Installations | Real `GET /installations`, `GET /installations/{id}`, and `GET /installations/{id}/evidence/{evidence_id}` support status/schedule filters, completion data, technician assignments, and private evidence reads. Technicians only see assigned jobs. | Status mutations remain in the existing technician workflow and are not exposed in this read-only Operations page. |
| Inventory | Real read APIs: `GET /inventory`, `/inventory/movements`, `/inventory/serialized-units/{serial_number}`, `/inventory/dispatches`, and `/inventory/dispatches/{id}`. UI displays stock, movement ledger, serial lookup, and dispatch lines. | The schema has no reorder threshold, so the filter accurately shows zero-available stock; no low-stock threshold is available. Stock writes remain unavailable in this UI. |
| Reports | Real `GET /dashboard/reports` and `/dashboard/summary` use PostgreSQL Numeric aggregates for completed order/service revenue, order/service invoice dues, operations counts, and per-installation margin. Financial report cache is user/role scoped. | Report period filters are not represented in the current UI/service. |
| Settings | Real `GET /users/me`, `GET /users`, and `GET /users/{id}`; sign in uses `POST /auth/login`. Frontend preferences are persisted locally. | Seeded demo passwords are placeholders and cannot authenticate. User creation/modification and server-persisted preferences are unavailable because the current user model has no preference fields or mutation workflow. |

The frontend has no hardcoded Operations record fixtures or success-toasts for nonexistent writes. The production build succeeds, and the five routes surface real API loading, empty, unauthorized, forbidden, and failure states.
