// Load test: 30 s ramp to 50 virtual users, then 60 s steady, on three read endpoints.
// Run (no install), from the repo root:
//   docker run --rm -v ${PWD}/loadtest:/scripts -e BASE_URL=http://host.docker.internal:8000 \
//     -e DIRECTOR_EMAIL=director@sunpower.in -e DIRECTOR_PASSWORD=... grafana/k6:0.54.0 run /scripts/k6.js
// SERIAL defaults to the demo seed's expired inverter (Ravi Kumar (demo)).
import http from "k6/http";
import { check, fail } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://host.docker.internal:8000";
const SERIAL = __ENV.SERIAL || "INV-3K-0001";
const ENDPOINTS = {
  enquiries: "/api/v1/enquiries",
  support_search: `/api/v1/support/search?q=${encodeURIComponent(SERIAL)}`,
  dashboard: "/api/v1/dashboard/summary?period=month",
};

const thresholds = {};
for (const name of Object.keys(ENDPOINTS)) {
  // Thresholds also make k6 print per-endpoint numbers in the summary.
  thresholds[`http_req_duration{endpoint:${name}}`] = ["p(95)<1000"];
  thresholds[`http_req_failed{endpoint:${name}}`] = ["rate<0.01"];
  thresholds[`http_reqs{endpoint:${name}}`] = ["count>0"];
}

export const options = {
  stages: [
    { duration: "30s", target: 50 },
    { duration: "60s", target: 50 },
  ],
  thresholds,
};

// Log in once; every virtual user reuses the session cookie (avoids the login rate limit).
export function setup() {
  const res = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({
      email: __ENV.DIRECTOR_EMAIL || "director@sunpower.in",
      password: __ENV.DIRECTOR_PASSWORD,
    }),
    { headers: { "Content-Type": "application/json" }, tags: { endpoint: "login" } },
  );
  const cookie = res.cookies.sp_session && res.cookies.sp_session[0];
  if (res.status !== 200 || !cookie) fail(`login failed: HTTP ${res.status}`);
  return { cookie: `sp_session=${cookie.value}` };
}

export default function (data) {
  const params = (name) => ({ headers: { Cookie: data.cookie }, tags: { endpoint: name } });
  for (const [name, path] of Object.entries(ENDPOINTS)) {
    const res = http.get(`${BASE_URL}${path}`, params(name));
    check(res, { [`${name} 200`]: (r) => r.status === 200 });
  }
}
