# Deploy SunPower

1. Create an Ubuntu 24.04 VM with 2 vCPU and 4 GB RAM. Allow inbound TCP ports 22, 80 and 443 only.
2. Install Docker: `curl -fsSL https://get.docker.com | sh`. Use Docker Compose 2.24.4 or newer (the production override uses `!override`).
3. Clone your repository: `git clone <YOUR_REPOSITORY_URL> SunPower-Solutions`, then `cd SunPower-Solutions`.
4. Run `cp .env.production.example .env`. Generate separate database, JWT and seed secrets with `openssl rand -hex 32`. Replace every `CHANGE_ME` value; use the same database password in POSTGRES_PASSWORD and DATABASE_URL. Keep `.env` private (`chmod 600 .env`).
5. Set DOMAIN to your domain pointing at the VM, or `<VM-IP-with-dashes>.sslip.io`, for example `203-0-113-10.sslip.io`. Caddy obtains HTTPS certificates automatically.
6. Run `sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --wait`. The entrypoint applies migrations before starting the API. PostgreSQL and Redis have no public ports; Caddy is the public entrypoint.
7. Seed users, catalog and stock: `sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api python -m scripts.seed`. Users in `backend/scripts/seed.py` log in with SEED_PASSWORD. Use a unique production password and share it privately.
8. Open `https://YOUR_DOMAIN`, log in, and check `https://YOUR_DOMAIN/api/health/ready`.

## Updates and logs

Run `sudo sh deploy/deploy.sh` from your checkout. It pulls, rebuilds, waits for health and shows status. View logs with `sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api`.

## Backups

Create `/var/backups/sunpower` owned by root with mode 700. Add this nightly cron entry to root's crontab, replacing `/opt/SunPower-Solutions` with your checkout path:

```cron
0 2 * * * cd /opt/SunPower-Solutions && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > /var/backups/sunpower/db-$(date +\%F).sql.gz
```

Copy backups off the VM and back up the `uploaded_files` volume as well. Test restoring a dump into a separate database before relying on backups.
