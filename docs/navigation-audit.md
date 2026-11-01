# Navigation audit

Compared the current sidebar against `a3fee0f` and `fb950ae`, and every screen heading in `docs/frontend-checklist.md`.

## Navigation by role

| Role | Main sidebar items |
| --- | --- |
| Director | Owner Dashboard, Director, Office Sales, Receiving, Dispatches, Support, Customers, Installations, Inventory, Reports, Settings |
| Office | Office Sales, Support, Customers, Installations, Inventory, Settings |
| Manager | Crew Schedule, Installations, Settings |
| Technician | My Day, Settings |
| Warehouse | Warehouse Demo, Receiving, Dispatches, Inventory, Settings |
| Support | Support, Customers, Settings |
| Surveyor | My Surveys, Settings |
| Admin | All main items, including all three workspaces and My Surveys |
| Guest | Brand/home, Sign in, collapse/expand menu; no MY WORK or OPERATIONS |

Office Sales has direct child links for Survey booking, Quotes & print, Orders & payments, Invoices & print, Repair intake and Subsidies. Director has direct child links for Survey Review, Technician pay runs and Shared links. My Day includes all assigned surveys, installation jobs, repair visits and monthly pay.

## Historical controls

| Historical item/button | Current disposition |
| --- | --- |
| Brand/home | Retained |
| Owner, Tech, Warehouse workspace pills | Consolidated into authorized workspace links; redundant switches removed to prevent unauthorized navigation |
| Owner Dashboard | Director and admin |
| Technician Workspace / Technician Demo | Admin retains preview; technician navigation uses My Day as explicitly requested |
| Warehouse Workspace / Warehouse Demo | Warehouse and admin |
| AI Copilot | Removed as requested |
| Office Sales | Office, director, admin; director restored |
| Director | Director, admin |
| My Day | Technician, admin |
| Receiving / Dispatches | Warehouse, director, admin; director links restored to match existing route permissions |
| Crew Schedule | Manager, admin |
| Manager Survey Review | Removed: no working route in either field route table, and backend survey approval is director/admin only; authorized Survey Review lives under Director |
| Support | Support, office, director, admin, matching backend search/view permissions |
| Customers / Installations / Inventory / Reports | Retained for authorized roles; director links restored |
| Settings | Every authenticated role, including technician profile/sign-out; staff directory limited to director/admin |
| Collapse / Expand menu, version | Retained |
| Sign out | Authenticated users only; guests get Sign in |
| Quick Scan | Support search with focus; warehouse dispatch list for warehouse. Hidden for manager, technician and surveyor because those roles cannot use backend support search |
| Bell | Live role-specific queue counts and screen links; technician gets assigned open-ticket counts and today's assigned counts |
| Help | Panel of authorized screens and direct Office/Director child links |

## Checklist screen coverage

| Checklist screen | Route / sidebar entry |
| --- | --- |
| Public website enquiry | `/public`, public customer-facing URL; intentionally outside staff navigation |
| Public shared dashboard | `/share/:token`, created through Director → Shared links; token-specific links cannot be a static sidebar entry |
| Login/session | `/login`, guest Sign in; authenticated Sign out |
| Sales inbox/call sheet | `/office/enquiries`, Office Sales |
| Survey booking/tracking | `/office/surveys`, direct child link added |
| Quote/print | `/office/quotes`, direct child link added |
| Orders/payments | `/office/orders`, direct child link added |
| Invoices/print | `/office/invoices`, direct child link added |
| Repair intake/confirmation | `/office/repairs`, direct child link added |
| Subsidy tracker | `/office/subsidies`, direct child link added |
| Crew calendar/booking; repair assignment | `/manager/schedule`, Crew Schedule, both forms in existing component |
| My day/field survey | `/technician/today`, My Day → assigned `/technician/surveys/:id` |
| Installation phone form | My Day → assigned `/technician/jobs/:id` |
| My repair visits | My Day → assigned `/technician/tickets/:id` |
| Monthly pay | My Day → My monthly pay, existing component |
| Pick list/dispatch scanning | `/warehouse/dispatches`, Dispatches → `/warehouse/dispatches/:id` |
| Stock/receiving | `/inventory` and `/warehouse/receiving`, Inventory and Receiving |
| Customer/warranty search | `/support`, Support |
| Ticket lifecycle/replacements | Support search → customer's open tickets → `/support/tickets/:id` |
| Director survey review | `/director/surveys`, direct child link added |
| Profit dashboard/sharing | `/director/overview` and `/director/sharing`, Director and direct child link |
| Monthly technician pay runs | `/director/pay`, direct child link added |

All checklist components have reachable screens. Detail, print and token routes remain contextual to a selected record. Surveyors additionally lacked access to the existing field-survey form: added `/surveyor/surveys` and `/surveyor/surveys/:id`, using the existing API and survey form. Placeholder Technician/Warehouse pages are superseded by the implemented field screens; the empty OwnerPage file contains no screen to route.

Workspace landing URLs remain public entry points so signed-out/wrong-role visitors can be offered sign-in; role permissions control their sidebar visibility and their live data access.

## Validation

Part A: frontend production build passes; ruff is clean; pytest: 254 passed; full Playwright suite: 46 passed (4.6 minutes), using a normal demo reset. Tests honor the separate SEED_PASSWORD and DEMO_PASSWORD fixture credentials.

## Live workspace follow-up (revised Part B)

The user confirmed the 300-order dataset exists only in a teammate's database and removed dataset discovery, bulk import and the `-Bulk` switch from scope. Used the normal `scripts/demo_reset.ps1` seed (nine demo customers); no bulk records were imported.

| Workspace | Live sources |
| --- | --- |
| Owner | Month summary cards; `/dashboard/trend?months=12`; recent `/orders` with real order status as stage; submitted surveys, planned jobs and open repairs for the operational queues |
| Technician | `/me/today` for the current authenticated account, including links to assigned surveys, installations and repairs |
| Warehouse | Every `/stock` and `/dispatches` page, using backend low-stock flags and actual dispatch statuses |

Added `GET /api/v1/dashboard/trend?months=12` for director/admin. It uses independent SQL monthly aggregates, IST boundaries and Decimal strings; empty months are zero-filled. Bookings include GST and use confirmation dates; cash uses completed payment dates. Cancelled bookings and failed/pending/refunded payments are excluded from their respective series. Details are in `docs/api-changelog.md` and `docs/decisions.md`.

Preserved the workspace card/chart/project/queue styling. Removed invented people, weather, JSA, DISCOM, capacity/fleet targets, project progress percentages and toast-only workspace actions. Guests and wrong-role accounts get a role-specific sign-in prompt without fetching that workspace's protected data.

Final validation after a normal demo reset: ruff clean; pytest **258 passed**; frontend production build passed; full Playwright suite **51 passed** (4.7 minutes). Added tests compare every workspace KPI, project stage, approval count and chart month against the APIs, and cover role gating and failure/retry behavior. No schema migrations or db-requests changes were needed.
