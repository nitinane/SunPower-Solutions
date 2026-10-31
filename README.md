# SunPower Solutions

Initial scaffold for the Solar Installation Management System: layered FastAPI backend, React/Vite frontend, PostgreSQL, Redis, Compose, and Nginx.

## Quick start

1. Copy `.env.example` to `.env` (`Copy-Item .env.example .env` in PowerShell or `cp .env.example .env` elsewhere).
2. Run `docker compose up --build -d`.
3. Visit <http://localhost> and <http://localhost/api/health>.

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

