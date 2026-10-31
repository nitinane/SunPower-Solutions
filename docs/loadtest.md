# Load test

Script: `loadtest/k6.js`. It logs in once as the director in `setup()`, and all virtual users share that session cookie, so the login rate limit is never hit. Load: 30 s ramp up to 50 virtual users, then 60 s steady. Each iteration calls three read endpoints one after another, with no think time.

```
docker run --rm -v ${PWD}/loadtest:/scripts -e BASE_URL=http://host.docker.internal:8000 \
  -e DIRECTOR_PASSWORD=<demo password> grafana/k6:0.54.0 run /scripts/k6.js
```

## Result (2026-10-31, local dev stack, after `seed` + `seed_demo`)

| Endpoint | Requests | Req/s | p95 latency | Avg | Error rate |
|---|---|---|---|---|---|
| GET /api/v1/enquiries | 3,642 | 39.8 | 554 ms | 294 ms | 0.00 % |
| GET /api/v1/support/search?q=INV-3K-0001 | 3,642 | 39.8 | 625 ms | 354 ms | 0.00 % |
| GET /api/v1/dashboard/summary?period=month | 3,642 | 39.8 | 658 ms | 391 ms | 0.00 % |
| **Total** | 10,927 | **119.5** | 619 ms | 347 ms | **0.00 %** |

Every k6 check passed (10,926 / 10,926), and every endpoint met its p95 < 1 s threshold.

**Machine:** a laptop with an Intel Core 5 210H and 16 GB RAM, running Windows 11 and Docker Desktop 29.6.2 (WSL2 VM: 12 vCPU, 7.6 GB). The API ran the **dev** configuration: uvicorn `--reload` with 2 workers, sharing Postgres 16 with the dev database. That database holds about 1,400 enquiries and 1,000+ orders left over from earlier test runs. k6 ran on the same machine, so it competed with the API for CPU. Treat these numbers as a floor, not a production figure.

## What to scale first
The API is stateless (the session is a signed cookie), so the first step is more workers: raise `WEB_CONCURRENCY` or run `docker compose up --scale api=3` behind Nginx. That alone should multiply throughput, because here the latency comes from 50 concurrent users sharing only 2 Python workers. After that, Postgres is the real bottleneck. Put PgBouncer in front of it so many workers can share a few connections, and send the dashboard's aggregate queries to a read replica (or cache them for 30-60 s in Redis), because the dashboard is the heaviest endpoint. 10,000 registered users are not 10,000 concurrent requests. At ~120 req/s on a laptop running a dev server, one production VM with 4-8 workers covers SunPower's office and field staff with plenty of headroom.
