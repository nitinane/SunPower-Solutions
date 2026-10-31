.PHONY: dev up down logs migrate makemigration test lint seed seed-demo demo-reset
dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
up:
	docker compose up --build -d
down:
	docker compose down
logs:
	docker compose logs -f
migrate:
	docker compose exec api alembic upgrade head
makemigration:
	@test -n "$(message)" || (echo "Usage: make makemigration message='description'" && exit 1)
	docker compose exec api alembic revision --autogenerate -m "$(message)"
test:
	docker compose exec api pytest
lint:
	docker compose exec api ruff check .
seed:
	docker compose exec api python scripts/seed.py
seed-demo:
	docker compose exec api python -m scripts.seed_demo
# Wipes the database. Server: make demo-reset COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
COMPOSE ?= docker compose -f docker-compose.yml -f docker-compose.dev.yml
demo-reset:
	$(COMPOSE) down -v
	$(COMPOSE) up -d --build --wait
	$(COMPOSE) exec -T api alembic upgrade head
	$(COMPOSE) exec -T api python -m scripts.seed
	$(COMPOSE) exec -T api python -m scripts.seed_demo
