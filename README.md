# SunPower Solutions

Initial scaffold for the Solar Installation Management System: layered FastAPI backend, React/Vite frontend, PostgreSQL, Redis, Compose, and Nginx.

## Quick start

1. Copy `.env.example` to `.env` (`Copy-Item .env.example .env` in PowerShell or `cp .env.example .env` elsewhere).
2. Run `docker compose up --build -d`.
3. Visit <http://localhost> and <http://localhost/api/health>.

## Demo database and staff sign-in

The application uses PostgreSQL as its source of truth. Set `POSTGRES_DB` and
`DATABASE_URL` in `.env` to `sunpower_demo` before starting the API. The 300
customer / 300 order seed refuses to run against any other database. Keep an
existing `sunpower` database intact; use the dedicated `sunpower_demo` database
for this dataset.

The deterministic seed creates 300 customers, their sites, 300 orders, and
related operational records. Run it from the `backend` directory after applying
the migrations:

```powershell
docker compose exec api alembic upgrade head
docker compose exec api python scripts/seed.py
```

The seed is idempotent for the same dataset. It will not replace unmarked data;
do not add `--reset` when using a database that contains data you need to keep.
The director dashboard reads customer/order counts and financial totals from
PostgreSQL, while Customers, Installations, Inventory, and Reports screens use
the API. Empty/error states are shown when the database cannot provide records;
those screens do not substitute mock customer or order data.

All staff sign in before entering a dashboard. The server issues an HttpOnly
session cookie, and each role sees only its permitted routes and records. The
demo seed uses the following email accounts; the password comes from
`DEMO_PASSWORD` in `.env` (the local example value is shown here for convenience):

**Demo password:** `SunPower@2026`

| Role | Email |
| --- | --- |
| Director | `director@sunpower.in` |
| Office | `office@sunpower.in` |
| Warehouse | `warehouse@sunpower.in` |
| Technician | `tech1@sunpower.in` through `tech8@sunpower.in` |
| Support | `support@sunpower.in` |
| Admin | `admin@sunpower.in` |

Technicians only receive installation jobs assigned to their own user account.
Warehouse staff are routed to inventory and dispatch data. Directors can access
all operational pages and financial reports.

Development with backend and frontend hot reload: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build` or `make dev` where Make is installed.

## URLs and commands

- Web app: <http://localhost>; liveness: <http://localhost/api/health>; readiness: <http://localhost/api/health/ready>
- Dev frontend: <http://localhost:5173>; dev API: <http://localhost:8000>; dev PostgreSQL: `localhost:5432`
- Make targets: `dev`, `up`, `down`, `logs`, `migrate`, `makemigration`, `test`, `lint`, `seed`.

Create and apply migrations after adding models:

```sh
docker compose exec api alembic revision --autogenerate -m "description"
docker compose exec api alembic upgrade head
```

The initial `alembic/versions/` directory is intentionally empty.

## Ownership

- DB teammate: `backend/app/models`, `backend/alembic`, `backend/scripts/seed.py`
- Backend developer: services, repositories, API, and frontend
- Shared: schemas

## Problem statement checklist

| Requirement | Screen | API | Status |
|---|---|---|---|

