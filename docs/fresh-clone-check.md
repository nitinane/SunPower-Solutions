# P3-3 fresh-clone verification

Run date: 2026-11-01. Host: Windows / PowerShell / Docker Desktop. Source commit: `cb0ad03` (P3-1), cloned from the local Git repository with no hardlinks, so only committed files were available initially; the source `.env`, storage and installed dependencies were not copied. This checks a clean checkout, not whether all local commits have already reached GitHub. The final Nginx fix was copied from the source workspace into this disposable clone and rebuilt before rechecking the failed behavior.

The dev stack had only `api`, `db`, and `redis` running. Its original Compose configuration included the dev file and an external override that removes the conflicting host DB port. `stop`/`start` preserved those containers and their existing configuration. The independent `sunpower_fresh` project used base Compose only, so it did not publish database port 5432 or disturb the other project's database.

## Commands and results

Commands are in execution order. `ROOT` below is `C:/hackathon/SunPower-Solutions`; after step 3 the working directory for fresh Compose commands is `ROOT/.fresh-check`. Python inspection/rehearsal commands used stdin (`@'... '@ | docker compose ... exec -T api python -` in PowerShell); their operations and results are recorded below rather than printing credentials, cookies or share tokens.

| Step | Command | Result |
| --- | --- | --- |
| 1 | `docker compose stop api db redis` | Exit 0; original dev services stopped, volumes retained. |
| 2 | `git clone --no-hardlinks C:/hackathon/SunPower-Solutions C:/hackathon/SunPower-Solutions/.fresh-check` | Exit 0; independent clean checkout at cb0ad03. |
| 3 | `Copy-Item -LiteralPath .fresh-check/.env.example -Destination .fresh-check/.env` | Success; only checked-in example values used. Bash equivalent: `cp .env.example .env` inside the clone. |
| 4 | `docker compose -p sunpower_fresh up -d --build --wait` | Exit 0; API and frontend images built, all four services ready. Entrypoint applied the full migration chain to the empty database. |
| 5 | `docker compose -p sunpower_fresh exec -T api alembic upgrade head` | Exit 0; already at head after entrypoint migration. |
| 6 | `docker compose -p sunpower_fresh exec -T api python -m scripts.seed` | Exit 0; 8 users, 18 products, 15 packages; stock seeded. |
| 7 | `docker compose -p sunpower_fresh exec -T api python -m scripts.seed_demo` | Exit 0; 9 demo customers, 8 demo role logins (including 3 technicians); password read from DEMO_PASSWORD, not printed. |
| 8 | `docker compose -p sunpower_fresh exec -T api python -c <SQLAlchemy record inspection>` | Exit 0; verified seeded customer, survey, quote, ticket, user and package IDs used to prepare the demo. New unqualified enquiries need not yet have customer rows. |
| 9 | `docker compose -p sunpower_fresh exec -T api python -m pytest -q tests/test_e2e_chain.py` | Exit 0; **1 passed**, two dependency deprecation warnings. Tests created/migrated the separate sunpower_test database. |
| 10 | `docker compose -p sunpower_fresh exec -T api ruff check app tests` | Exit 0; all checks passed. |
| 11 | `docker compose -p sunpower_fresh exec -T api python -c <urllib readiness/web inspection>` | Exit 0; direct `/health/ready` and Nginx `/api/health/ready` both 200 with DB/Redis ok; frontend `/` and Swagger HTML `/api/docs` both 200. Inspection found Swagger external/inline scripts blocked by the inherited CSP. |
| 12 | `docker compose -p sunpower_fresh exec -T api python -m pytest --cov=app/services --cov-report=term -q` | Exit 0; **230 passed**, **90%** service statement coverage, 1,823 statements / 188 missed, two dependency deprecation warnings. |
| 13 | `Copy-Item -LiteralPath frontend/nginx.conf -Destination .fresh-check/frontend/nginx.conf` (from ROOT) | Success; applied the source fix to the disposable checkout. |
| 14 | `docker compose -p sunpower_fresh up -d --build --wait web` | Exit 0; rebuilt with the new Nginx config and all dependencies healthy. |
| 15 | `docker compose -p sunpower_fresh exec -T web nginx -t` | Exit 0; syntax and config successful. |
| 16 | `docker compose -p sunpower_fresh exec -T api python -c <urllib CSP/readiness assertions>` | Exit 0; docs policy now permits jsDelivr and inline initializer, root policy unchanged, proxied readiness still 200. This verifies headers and HTML, not an automated browser render. |
| 17 | `@'<HTTP rehearsal script>'@ \| docker compose -p sunpower_fresh exec -T api python -` | First half reached delivery successfully, then the assertion for invoice search by order number failed. The docs example was corrected to search by customer name; no backend change was needed. |
| 18 | `@'<remaining HTTP rehearsal script>'@ \| docker compose -p sunpower_fresh exec -T api python -` | Exit 0; corrected invoice lookup and all remaining demo steps passed; see exact endpoint results below. |
| 19 | `docker compose -p sunpower_fresh down -v` | Exit 0; all four disposable containers, fresh network and sunpower_fresh_postgres_data removed. No dev volumes removed. |
| 20 | `Resolve-Path` / `Get-Item` / `Remove-Item -LiteralPath <verified clone> -Recurse -Force` | Success; resolved path compared against the exact expected ROOT/.fresh-check and rejected links before deleting it. |
| 21 | `docker compose start db redis api` (from ROOT) | Exit 0; original dev containers restarted without recreation. |
| 22 | `docker compose ps` and direct API readiness check | Original three services restored; final health status and readiness confirmed after startup. |

## What the rehearsal verified

All login calls used DEMO_PASSWORD inside the container and independent cookie jars. They called the running API over HTTP, not service functions, with no secret values in the transcript.

| Moment | Requests and observed result |
| --- | --- |
| Approval gate | Office looks up Fatima's submitted survey and 2 kW package; POST `/api/v1/quotes` → 409 SURVEY_NOT_APPROVED. |
| Automatic work queues | Accept Venkatesh's quote → 200; first cash payment 1000.00 → 201, with both pick list and installation job in the order response. |
| Wrong serial | Scan BAT-150AH-0004 → 409 SERIAL_WRONG_PRODUCT; INV-4K-0001 and CC-MPPT-40-0006 → 200 each. |
| Delivery | Send → 200; deliver → 200 and nonzero warranties_created. Invoice lookup by order number returned no matching items; corrected `search=Venkatesh` → 200 with one invoice, then invoice detail → 200. |
| Expired repair | Search INV-3K-0001 → 200 with Ravi's expired coverage. Assigned tech2 resolves the inverter ticket with one hour and no parts → 200, status resolved, total 590.00. |
| Customer confirmation | Support opens Kavitha's resolved warranty ticket, records confirmed=true → 200, status closed, total 0.00. |
| Profit and share | Director month summary sorted profit_asc → 200; create 24-hour share → 201; anonymous public summary → 200; revoke → 204; anonymous read afterward → 404. |

The API demo was rehearsed across the two scripts after correcting the invoice-search example. It was not a UI end-to-end test: role pages are placeholders, `/share/<token>` is not implemented, and public sharing was checked through `/api/v1/public/dashboard/<token>`.

## Fixes and limits

- Fixed the Swagger CSP in `frontend/nginx.conf` with an exact `/api/docs` location. It repeats security headers, permits jsDelivr script/style assets and the inline Swagger initializer, and keeps the normal application's self-only script policy. Docs require CDN connectivity; this is not a fully offline Swagger bundle.
- Corrected the demo invoice lookup to match the implemented search fields (invoice number, customer name, phone digits).
- No missing environment variables, migrations, seeds, build files or service dependencies blocked the clean base-Compose startup. No schema changes were needed.
- No live VM/domain was supplied; production TLS and the actual GitHub Actions run were not exercised by this local check.
