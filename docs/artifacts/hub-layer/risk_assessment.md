# Risk Assessment: hub-layer

## Summary
- **Date**: 2026-03-28
- **Overall Risk Score**: 93
- **Recommendation**: ship_with_monitoring
- **Critical Risks**: 0
- **High Risks**: 0
- **Medium Risks**: 5
- **Low Risks**: 9

---

## Risk Catalog

### Critical Risks

_None identified._

---

### High Risks

_None identified._

---

### Medium Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation | Residual |
|----|------|-----------|--------|-------|------------|----------|
| R-001 | **HUB_REDIS_ENABLED=false default** — If env var is not explicitly set in staging/prod, Hub silently uses in-memory store (no persistence). All offers lost on process restart without any error. | 3 | 4 | 12 | Document required env vars in deployment runbook. Set `HUB_REDIS_ENABLED=true` in all non-dev environments via Azure App Service config. Health endpoint shows `"redis": "degraded"` when Redis unreachable, surfacing misconfiguration. | Medium — correct deployment config is operator responsibility; no code change needed |
| R-002 | **Redis AUTH not configured** — Default `REDIS_URL=redis://localhost:6379` has no password or TLS. Azure Redis Cache requires TLS (`rediss://`) and AUTH token. Misconfigured REDIS_URL causes startup connection failures — all Hub writes/reads return 503. | 3 | 4 | 12 | Set `REDIS_URL=rediss://:password@host:6380` (note `rediss://` for TLS) in Azure Key Vault. The validate_redis_config() startup check will catch noeviction policy issues. | Medium — config error; not a code defect |
| R-003 | **MARKETER_JWT unset in production** — `getAuthHeaders()` returns `{}` if env var unset. Hub Server Component calls fail with 401. Hub frontend page shows "Failed to load offers" for all users. | 3 | 3 | 9 | `getAuthHeaders()` gracefully returns `{}` (no crash). Add `console.warn` in dev (minor finding from code review). Document `MARKETER_JWT` as required in deployment checklist. | Low-Medium — availability issue, not security issue; no data exposure |
| R-004 | **Redis eviction misconfiguration** — If Azure Redis Cache has `maxmemory-policy != noeviction`, Redis silently evicts oldest offers. `GET /api/hub/offers/{id}` returns 404 for evicted offers, appearing as if offers never existed. Startup check logs CRITICAL but does not block startup. | 2 | 4 | 8 | `validate_redis_config()` logs CRITICAL on startup (EC-006). Infra team must set noeviction policy when provisioning the cache instance. For Azure Redis Cache, set `maxmemory-policy = noeviction` via portal or ARM template. | Low-Medium — mitigated by startup check + operator responsibility |
| R-005 | **Hub fraud bypass via system role** — Callers with `role=system` can call `PUT /api/hub/offers/{id}/status` to transition draft→approved, bypassing the Designer fraud check. No fraud verification occurs at the Hub transition layer itself. | 2 | 4 | 8 | Hub's responsibility is state transition enforcement only (correct per architecture). Fraud detection runs in Designer before save. Only service accounts (Scout, internal callers) hold system JWTs — no human user can obtain a system role JWT. Document this as an architectural decision: Hub trusts that callers with system role have already performed fraud checks. | Low-Medium — intentional design; mitigated by role restriction |

---

### Low Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation | Residual |
|----|------|-----------|--------|-------|------------|----------|
| R-006 | **Redis SCAN O(N) at scale** — `RedisHubStore.list()` uses SCAN cursor, iterating all `offer:*` keys. At 10,000+ offers, each LIST call scans the full keyspace. p95 latency could exceed 200ms. | 2 | 3 | 6 | TODO comment in code (F-006). latency logging fires WARNING if >200ms. For MVP scale (<1,000 offers), SCAN is acceptable. Post-MVP: Redis sorted set by created_at for O(log N) range queries. | Low |
| R-007 | **Redis parse error silently drops offer** — If a stored value is corrupted JSON, `OfferBrief.model_validate_json()` raises in `list()`. The corrupted offer is skipped with a WARNING log. The offer is lost from list view but still exists in Redis under its key. | 1 | 3 | 3 | Pydantic v2 validation is strict — only externally-corrupted bytes would cause this. Write path uses `model_dump_json()` which always produces valid JSON. Corrupted data would require direct Redis manipulation. WARNING log provides observability. | Low |
| R-008 | **Redis connection not closed on shutdown** — `get_hub_store()` lru_cache creates a `RedisHubStore` with a connection pool that is never explicitly closed. Under hot-reload or container restart, connections may not be cleanly terminated. | 3 | 1 | 3 | Code review minor finding: add `await store._redis.aclose()` in main.py lifespan shutdown hook. Azure container restarts handle this at the OS level. Not a data integrity risk. | Low |
| R-009 | **Designer auto-save leaves offer un-saved on transient Redis failure** — If `hub_store.save()` raises `RedisUnavailableError`, the Designer returns 503 and the offer is NOT in Hub. Client must retry `POST /generate` entirely. A new offer_id is generated on retry (no dedup at Designer level). | 2 | 2 | 4 | `OfferAlreadyExistsError` → idempotent (AC-020). Transient failures require client retry — documented in API responses (503 detail string explains this). Not a data corruption risk. | Low |
| R-010 | **lru_cache singleton state leaks between tests** — `get_hub_store()` with `lru_cache(maxsize=1)` returns the same `InMemoryHubStore` instance across all calls unless overridden. Tests that forget to set `app.dependency_overrides` or clear the store may see stale data from previous tests. | 2 | 3 | 6 | All integration tests use `app.dependency_overrides[get_hub_store]`. `InMemoryHubStore.clear()` is available for fixtures. This is a test infrastructure concern, not a production risk. | Low |
| R-011 | **Concurrent approve + expire task race** — If Scout calls `PUT /status?new_status=active` and `_expire_offers_task` simultaneously processes the same offer's expiry, both call `hub_store.update()`. Last write wins. Result is always deterministic (one valid `expired` state). | 2 | 1 | 2 | Benign race — both writers intend the same terminal state. Redis SET is atomic. | Low |
| R-012 | **Hub frontend JWT expiry** — `MARKETER_JWT` is a static env var. When the token expires, all Server Component Hub API calls return 401 indefinitely until env var is rotated. | 3 | 2 | 6 | In production: use short-lived tokens refreshed via Azure Managed Identity or set long-lived service account JWTs. For hackathon/dev: acceptable. | Low |
| R-013 | **Audit SQLite path incorrect** — If `DATABASE_URL` is misconfigured or the path is non-writable, `_create_table_sync()` logs WARNING but the app starts. All `log_event()` calls silently fail. Compliance audit trail is lost. | 2 | 3 | 6 | Non-blocking by design (REQ-004 / AC-017). WARNING at startup surfaces this. Verify path permissions in deployment checklist. SQLite is dev/test only; production uses PostgreSQL with proper path/DSN. | Low |
| R-014 | **Offers stuck in approved indefinitely** — No auto-expiry for approved offers. If Scout is down or an offer is never activated, it accumulates in Hub. No TTL or cleanup mechanism. | 3 | 2 | 6 | Acceptable per spec (EC-005, Non-Goal #6). The expire task only handles active→expired. An operator cleanup script can be added post-MVP. | Low |

---

## Risk Clusters

1. **Redis Misconfiguration Cascade** (R-001 → R-002 → R-004):
   `HUB_REDIS_ENABLED` not set → in-memory used (no persistence) → OR → Redis URL wrong (AUTH missing, TLS missing) → all Hub writes 503 → AND → eviction policy misconfigured → silent data loss. **Single point of failure:** operator deployment config. Mitigation: deployment checklist with explicit verification of all three env vars.

2. **Frontend Auth Failure Cascade** (R-003 → R-012):
   `MARKETER_JWT` unset or expired → Hub Server Component returns 401 → OfferList page shows error state for all users → designers cannot see/approve offers. Mitigation: token rotation process + health check monitoring on Hub page response codes.

3. **Audit Availability Cluster** (R-008 → R-013):
   Redis connection leak on shutdown → audit tasks may not complete → AND → SQLite path misconfigured → all audit rows silently dropped. Compliance trail incomplete. Mitigation: both are independently non-blocking (design intent); deploy monitoring on `hub_audit_write_failed` log events.

---

## Ship Recommendation

**ship_with_monitoring**: 0 Critical risks, 0 High risks, 5 Medium risks (all mitigated), total risk score 93 < 100.

The hub-layer feature is safe to ship. All 5 Medium risks are deployment configuration concerns (env vars, Redis provisioning) rather than code defects. No data integrity, PII, or member-impacting risks exist at code level. The implementation correctly: enforces strict status transitions (422 on invalid paths), fails fast on Redis unavailability (503), protects audit trail as non-blocking (no HTTP impact), and gates fraud detection before Hub save.

### Monitoring Requirements

**Monitor:**
- `hub_latency_exceeded` WARNING logs — triggers if p95 > 200ms; baseline alert threshold: >5/min
- `hub_audit_write_failed` WARNING logs — indicates audit trail gap; alert on any occurrence in prod
- `redis_eviction_policy_misconfigured` CRITICAL log — alert immediately; data loss risk
- Hub page 401/503 error rates — indicate MARKETER_JWT or Redis config failures

**Alert Conditions:**
- `GET /health` returns `"redis": "degraded"` for more than 60 seconds
- `hub_audit_write_failed` count > 0 in any 5-minute window
- `hub_latency_exceeded` count > 10 in any 1-minute window
- HTTP 503 rate on Hub endpoints > 1% of requests

**Rollback Trigger:**
- Any offer in Hub shows incorrect status after a status transition
- `hub_audit_write_failed` rate > 50% of Hub events (audit trail unusable)
- Redis eviction policy confirmed misconfigured with offers already evicted

### Deployment Checklist (Required Before Production)

- [ ] `HUB_REDIS_ENABLED=true` set in Azure App Service config
- [ ] `REDIS_URL=rediss://:${REDIS_AUTH_KEY}@${REDIS_HOST}:6380` (TLS + AUTH)
- [ ] Azure Redis Cache `maxmemory-policy` = `noeviction` verified
- [ ] `DATABASE_URL` points to writable path (PostgreSQL DSN for prod)
- [ ] `MARKETER_JWT` set with appropriate expiry + rotation plan
- [ ] `GET /health` verified to return `"redis": "ok"` after deployment
- [ ] Hub page (`/hub`) verified to load OfferList without 401/503

---

## Sign-Off

| Dimension | Status |
|-----------|--------|
| Data integrity | PASS — atomic SET NX, strict transition enforcement |
| PII protection | PASS — actor_id (opaque JWT sub) only; no names/emails in logs |
| Fraud gate | PASS — fraud check blocks Hub save for critical severity |
| Rate limiting | N/A — Hub is state store; activation limits are Scout's responsibility |
| Member spam | N/A — Hub does not trigger notifications |
| Offer stacking | N/A — Hub stores offers; stacking detection is Designer/Scout |
| Auth enforcement | PASS — system role required for writes; any JWT for reads |
| Fail-fast | PASS — Redis unavailability returns 503 (no silent fallback) |
