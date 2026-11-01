# Demo reset: wipes the database (and named volumes), then migrates and loads demo data.
# Local:  .\scripts\demo_reset.ps1          (dev compose files)
# Server: .\scripts\demo_reset.ps1 -Prod    (prod compose files)
# Needs DEMO_PASSWORD in .env for the demo logins (dev falls back to the seed default).
param([switch]$Prod)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$files = if ($Prod) { @("-f", "docker-compose.yml", "-f", "docker-compose.prod.yml") }
         else { @("-f", "docker-compose.yml", "-f", "docker-compose.dev.yml") }

function Compose { docker compose @files @args; if ($LASTEXITCODE -ne 0) { throw "docker compose $args failed" } }

Compose down -v
Compose up -d --build --wait
Compose exec -T api alembic upgrade head
Compose exec -T api python -m scripts.seed
Compose exec -T api python -m scripts.seed_demo
Write-Host "Demo reset done."
