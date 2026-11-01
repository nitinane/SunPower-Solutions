#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --wait
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
