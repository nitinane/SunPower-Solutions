# P3-2 dependency audit

Ran pinned pip-audit 2.9.0 against `backend/requirements.txt`; looked up severity from the official GitHub Advisory API for each GHSA identifier.

Initial result: 30 findings across PyJWT 2.10.1 (17), python-multipart 0.0.20 (6), and transitive Starlette 0.46.2 (7).

Applied the high/critical fixes:

| Package | Patched version | Reason |
| --- | --- | --- |
| PyJWT | 2.14.0 | High verification issues and critical GHSA-ffc3-869f-jxw9 |
| python-multipart | 0.0.30 | High GHSA-wp53-j4wj-2cfg, GHSA-pp6c-gr5w-3c5g, GHSA-5rvq-cxj2-64vf |
| Starlette | 1.3.1 | High GHSA-7f5h-v6xp-fcq8, GHSA-wqp7-x3pw-xc5r, GHSA-82w8-qh3p-5jfq |
| FastAPI | 0.162.0 | Compatibility with patched Starlette; dependency resolver and full tests pass |

Final result: 3 findings, no high or critical findings remaining:

- PyJWT PYSEC-2026-4141 / GHSA-42vr-xj54-vc7v: medium, fixed in 2.15.0.
- PyJWT PYSEC-2026-4183 / GHSA-x33g-cr3x-6449: medium, fixed in 2.15.0.
- python-multipart PYSEC-2026-3040 / GHSA-v9pg-7xvm-68hf: low, fixed in 0.0.31.

These remain under the task's high/critical-only upgrade scope. The audit exits 1 while these findings remain. No tracked secret `.env` files were found; `.env.example` contains development defaults only. Production requires independent generated secrets.

Reproduce inside the API container (the non-root account has no home cache directory):

```sh
docker compose exec -e XDG_CACHE_HOME=/tmp/audit-cache api python -m pip_audit -r requirements.txt
```
