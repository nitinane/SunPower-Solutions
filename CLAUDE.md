# SunPower backend — rules for Claude Code

## Project
FastAPI + PostgreSQL 16 + SQLAlchemy 2 (sync) + Alembic + Redis, Docker Compose, Nginx.
Solar installation ERP for "SunPower Solutions". Hackathon: finish fast, no extras.

## How to work
- Build plan: BUILD_PLAN.md. "Next task" = first unchecked box in its PROGRESS list.
- The task prompt is the full spec. Execute it step by step. Don't redesign. Don't ask questions.
- If something is unclear, pick the simplest option that satisfies the rule, add one line to
  docs/decisions.md ("<feature>: <choice> because <reason>"), and continue.
- Read only the files the prompt lists, plus what you need to copy an existing pattern.
- Don't refactor existing code. Don't add endpoints, features or libraries the prompt doesn't ask for.
- After each step: run ruff and that step's tests. Fix before moving on.

## Ownership
- NEVER edit app/models/* or alembic/versions/* — the DB teammate owns them.
- If a table/column/constraint/index you need is missing: append it to db-requests.md
  (table, column, type, constraint, why), print the list, and STOP.

## Layers (same as Features 1–3)
Router -> Service -> Repository -> DB. Schemas = Pydantic, models = SQLAlchemy.
- Routers: parse input, call one service function, return a schema. No DB queries.
- Services: all business rules. No FastAPI imports. Raise errors from app/exceptions.py.
- Repositories: queries only. No commits, no rules. Bound parameters only.
- Copy patterns from: app/services/enquiries.py, app/services/quotes.py,
  app/repositories/enquiries.py, app/api/routes/quotes.py, app/schemas/quotes.py, existing tests.

## Rules for every write
- Lock the main row first (SELECT ... FOR UPDATE, like get_by_id_for_update).
- Check the current status is allowed, else 409 with a clear message.
- One transaction per action; commit where Features 1–3 commit.
- Audit entry for every state change (copy the _audit helper pattern).
- Statuses: only values from app/core/enums.py (DB names win). Map by meaning, never rename.

## Money and time
- Money: Decimal only, never float. quantize(Decimal("0.01"), ROUND_HALF_UP). JSON sends strings.
- Timestamps stored in UTC. Business dates ("today", warranty start) use Asia/Kolkata.

## API
- Prefix /api/v1, snake_case JSON, list endpoints return Page[T] (?page, ?page_size).
- Errors: {"error": {"code", "message", "fields"}}. 401 / 403 / 404 / 409 business rule / 422 validation.
  409 codes are SCREAMING_SNAKE_CASE, e.g. SERIAL_ALREADY_SHIPPED.
- Roles via require_role(...) from app/core/deps.py, using the UserRole values in enums.py.

## Commands
- Lint: ruff check app tests
- Tests: docker compose exec api python -m pytest -q (real Postgres)

## Finish every task with
1. ruff clean, all tests pass (old + new).
2. git commit (don't push) with the message given in the prompt.
3. A short report: files changed, endpoints (method, path, roles), tests added,
   anything written to db-requests.md or docs/decisions.md.
