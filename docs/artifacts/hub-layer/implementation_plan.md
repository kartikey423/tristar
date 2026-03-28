# Implementation Plan: hub-layer

## Overview
- **Total files:** 21 (13 new, 8 modified)
- **Waves:** 7
- **Estimated complexity:** Medium-High
- **Pre-existing tests that must remain green:** 94 (all current pytest suite)

---

## Pre-Implementation Baseline

Before writing any code, record:
```bash
pytest tests/ -q --tb=no   # Must show: 94 passed
```

Run after each wave — if count drops, stop and fix before proceeding.

---

## Wave Plan

### Wave 1: Dependencies

No shared type changes (OfferBrief schema unchanged). Add new Python package dependencies.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 1 | `pyproject.toml` | MODIFY | — | Add `redis>=5.0.0`, `aiosqlite>=0.21.0`, `sqlalchemy[asyncio]>=2.0` to `[project.dependencies]` |

**Wave 1 Verification:**
- [ ] `pip install -e ".[dev]"` succeeds without errors
- [ ] `python -c "import redis.asyncio; import aiosqlite; import sqlalchemy"` succeeds

---

### Wave 2: Backend Config

All services depend on config. Config must be updated before any new service reads it.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 2 | `src/backend/core/config.py` | MODIFY | COMP-004 | Add `HUB_REDIS_ENABLED: bool = False` and `REDIS_URL: str = "redis://localhost:6379"` to Settings class |

**Wave 2 Verification:**
- [ ] `python -c "from src.backend.core.config import settings; print(settings.HUB_REDIS_ENABLED)"` prints `False`
- [ ] `pytest tests/ -q --tb=no` still shows 94 passed

---

### Wave 3: Backend Services

Hub storage abstraction and audit service — pure business logic, no route dependencies.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 3 | `src/backend/services/hub_store.py` | NEW | COMP-001 | `HubStore` Protocol + `InMemoryHubStore` + `RedisHubStore`. Redis key: `offer:{offer_id}`. `RedisUnavailableError` raised on connection failure. `ping()` and `validate_redis_config()` methods on `RedisHubStore`. |
| 4 | `src/backend/services/hub_audit_service.py` | NEW | COMP-003 | `HubAuditEvent` Pydantic model + `HubAuditService`. `__init__` runs `CREATE TABLE IF NOT EXISTS hub_audit_log (...)`. `log_event()` is async, catches all exceptions (logs WARNING, never raises). |

**Wave 3 Verification:**
- [ ] `python -c "from src.backend.services.hub_store import InMemoryHubStore"` succeeds
- [ ] `python -c "from src.backend.services.hub_audit_service import HubAuditService"` succeeds
- [ ] `pytest tests/ -q --tb=no` still shows 94 passed

---

### Wave 4: Backend API Routes

All routes depend on Wave 3 services and Wave 2 config. Implement DI registry first, then routes.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 5 | `src/backend/api/deps.py` | MODIFY | COMP-005 | Add `get_hub_store()` factory (returns `RedisHubStore` if `HUB_REDIS_ENABLED` else `InMemoryHubStore`) and `get_hub_audit_service()` factory. Both decorated with `@lru_cache(maxsize=1)`. |
| 6 | `src/backend/api/hub.py` | MODIFY | COMP-002 | Replace `_store` dict with `Depends(get_hub_store)`. Add `VALID_TRANSITIONS` map + `_validate_transition()`. Inject `HubAuditService`. Add latency timing (WARNING if >200ms). Catch `RedisUnavailableError` → 503. Fire-and-forget audit via `asyncio.create_task()`. |
| 7 | `src/backend/api/designer.py` | MODIFY | COMP-006 | In `POST /generate`: inject `HubStore`, auto-save offer as draft after fraud check passes. In `POST /approve/{offer_id}`: change from `hub_client.save_offer()` to `hub_store.update()` + `_validate_transition(draft, approved)` [F-001 fix]. |
| 8 | `src/backend/main.py` | MODIFY | COMP-007 | Extend `GET /health` to include `"redis": "ok" \| "degraded"` via `hub_store.ping()`. Update `_expire_offers_task` to use `hub_store.list()` + `hub_store.update()` instead of direct `_store` dict access. |

**Wave 4 Verification:**
- [ ] `uvicorn src.backend.main:app --port 8000` starts without errors
- [ ] `GET /health` returns `{"status": "healthy", ..., "redis": "degraded"}` (Redis not running)
- [ ] `pytest tests/integration/backend/api/test_hub_api.py -v` → all 20 pass
- [ ] `pytest tests/ -q --tb=no` ≥ 94 passed (no regressions)

---

### Wave 5: Frontend Services

Frontend services depend on API contracts being defined (Wave 4). No component dependencies yet.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 9 | `src/frontend/lib/config.ts` | MODIFY | — | Add `getAuthHeaders()` function returning `{Authorization: "Bearer ${MARKETER_JWT}"}` [F-002 fix] |
| 10 | `src/frontend/services/hub-api.ts` | NEW | COMP-014 | `fetchOffers(params)` using `SERVER_API_BASE` + `MARKETER_JWT` (not `HUB_SERVICE_TOKEN`) [F-003 fix]. `next: { revalidate: 0 }` for fresh SSR data. |
| 11 | `src/frontend/app/hub/actions.ts` | NEW | COMP-013 | `'use server'`. `approveOffer(offerId)` calls `PUT /api/hub/offers/{id}/status?new_status=approved` using `getAuthHeaders()`. |

**Wave 5 Verification:**
- [ ] TypeScript compilation: `npx tsc --noEmit` on wave 5 files passes
- [ ] `getAuthHeaders()` returns `{}` when `MARKETER_JWT` is undefined (no crash)

---

### Wave 6: Frontend Components

All Hub components depend on Wave 5 services and each other in order.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 12 | `src/frontend/components/Hub/StatusBadge.tsx` | NEW | COMP-012 | Server Component. Color map: draft=grey, approved=blue, active=green, expired=red/opacity. No `'use client'`. |
| 13 | `src/frontend/components/Hub/ApproveButton.tsx` | NEW | COMP-011 | `'use client'`. Uses `useTransition` + `useRouter`. Calls `approveOffer` Server Action. Disables on pending. |
| 14 | `src/frontend/components/Hub/OfferCard.tsx` | NEW | COMP-010 | Server Component. Renders status badge, offer_id (truncated), objective, trigger_type label, risk severity, and conditionally `<ApproveButton>` for draft offers. Import types from `@/../../shared/types/offer-brief` [F-005 fix]. |
| 15 | `src/frontend/components/Hub/OfferList.tsx` | NEW | COMP-009 | Server Component. Maps offers to `<OfferCard>`. Shows "No offers yet." empty state. |
| 16 | `src/frontend/app/hub/page.tsx` | NEW | COMP-008 | Server Component. Calls `fetchOffers()`. Passes to `<OfferList>`. Inline try/catch for Hub 503 → error message. Reads `searchParams.status` for optional status filter. |

**Wave 6 Verification:**
- [ ] TypeScript compilation: `npx tsc --noEmit` on all wave 6 files passes
- [ ] `npm run build` succeeds (Next.js static analysis)
- [ ] No `'use client'` on OfferList, OfferCard, StatusBadge, page.tsx

---

### Wave 7: Tests

Tests depend on all implementation waves.

| # | File | Action | Tests For | Key Scenarios |
|---|------|--------|-----------|---------------|
| 17 | `tests/unit/backend/services/test_hub_store.py` | NEW | COMP-001 | `InMemoryHubStore`: save/get/list/update/exists/ping. `list()` with status filter, trigger_type filter, since filter. `exists()` returns False for unknown id. |
| 18 | `tests/unit/backend/services/test_hub_audit_service.py` | NEW | COMP-003 | `log_event()` writes to hub_audit_log table. DB error → WARNING logged, no exception raised. `HubAuditEvent` Pydantic validation. |
| 19 | `tests/integration/backend/api/test_hub_api.py` | MODIFY | COMP-002 | Add: `test_invalid_transition_returns_422` (draft→active). Add: `test_redis_unavailable_returns_503` (mock store raises `RedisUnavailableError`). |
| 20 | `tests/integration/backend/api/test_designer_hub_integration.py` | NEW | COMP-006 | `test_generate_auto_saves_to_hub`: POST /generate → verify offer in GET /hub/offers. `test_generate_fraud_blocked_not_saved`: POST /generate with critical fraud → GET /hub/offers returns empty. `test_approve_transitions_not_rejects_duplicate`: POST /generate then POST /approve/{id} → 200 (not 409). |
| 21 | `tests/unit/frontend/components/Hub/OfferCard.test.tsx` | NEW | COMP-010 | Draft offer renders Approve button. Non-draft offer hides Approve button. Renders objective, truncated offer_id, trigger_type label. |
| 22 | `tests/unit/frontend/components/Hub/StatusBadge.test.tsx` | NEW | COMP-012 | Each status renders correct CSS class. Unknown status renders fallback. |

**Wave 7 Verification:**
- [ ] `pytest tests/ -q --tb=no` ≥ 110 passed (94 baseline + ~16 new)
- [ ] `pytest tests/integration/ -m integration -v` all pass
- [ ] `npm test` (frontend unit tests) all pass
- [ ] No test touches `HUB_REDIS_ENABLED=true` — all integration tests use in-memory store

---

## Acceptance Criteria Mapping

| AC ID | Description | Primary Files | Test File | Wave |
|-------|-------------|--------------|-----------|------|
| AC-001 | Redis store: POST saves to Redis | hub_store.py, hub.py, config.py | test_hub_store.py | 3,4 |
| AC-002 | Redis store: GET retrieves from Redis | hub_store.py, hub.py | test_hub_store.py | 3,4 |
| AC-003 | In-memory when HUB_REDIS_ENABLED=false | hub_store.py, deps.py | test_hub_store.py | 3,5 |
| AC-004 | Offers survive restart (Redis) | hub_store.py (RedisHubStore) | manual/staging | 3 |
| AC-005 | Redis unreachable → 503 on POST | hub_store.py, hub.py | test_hub_api.py (add) | 3,4 |
| AC-006 | Redis unreachable → 503 on GET | hub_store.py, hub.py | test_hub_api.py (add) | 3,4 |
| AC-007 | draft → approved allowed | hub.py (VALID_TRANSITIONS) | test_hub_api.py (existing) | 4 |
| AC-008 | approved → active allowed | hub.py (VALID_TRANSITIONS) | test_hub_api.py (existing) | 4 |
| AC-009 | active → expired allowed | hub.py (VALID_TRANSITIONS) | test_hub_api.py (existing) | 4 |
| AC-010 | draft → active rejected (422) | hub.py (_validate_transition) | test_hub_api.py (add) | 4 |
| AC-011 | expired → draft rejected (422) | hub.py (_validate_transition) | test_hub_api.py (add) | 4 |
| AC-012 | active → draft rejected (422) | hub.py (_validate_transition) | test_hub_api.py (add) | 4 |
| AC-013 | Audit: offer created | hub_audit_service.py, hub.py | test_hub_audit_service.py | 3,4 |
| AC-014 | Audit: status transition | hub_audit_service.py, hub.py | test_hub_audit_service.py | 3,4 |
| AC-015 | Audit: GET read | hub_audit_service.py, hub.py | test_hub_audit_service.py | 3,4 |
| AC-016 | Audit: fraud blocked | hub_audit_service.py, designer.py | test_hub_audit_service.py | 3,4 |
| AC-017 | Audit write fail → non-blocking | hub_audit_service.py | test_hub_audit_service.py | 3 |
| AC-018 | Designer generate → Hub draft | designer.py, hub_store.py | test_designer_hub_integration.py | 4 |
| AC-019 | Designer generate critical → not saved | designer.py | test_designer_hub_integration.py | 4 |
| AC-020 | Designer auto-save 409 → idempotent | designer.py | test_designer_hub_integration.py | 4 |
| AC-021 | Designer auto-save 503 → Designer 503 | designer.py | test_designer_hub_integration.py | 4 |
| AC-022 | /hub page renders OfferList | page.tsx, OfferList.tsx | manual | 6 |
| AC-023–026 | Status badges per status | StatusBadge.tsx, OfferCard.tsx | StatusBadge.test.tsx | 6 |
| AC-027 | trigger_type label shown | OfferCard.tsx | OfferCard.test.tsx | 6 |
| AC-028 | Risk severity badge | OfferCard.tsx | OfferCard.test.tsx | 6 |
| AC-029 | Approve button triggers refresh | ApproveButton.tsx, actions.ts | OfferCard.test.tsx | 6 |
| AC-030 | Empty state message | OfferList.tsx | OfferCard.test.tsx | 6 |
| AC-031 | p95 < 200ms | hub.py (Redis backend) | performance (manual) | 4 |
| AC-032 | WARNING if >200ms | hub.py (latency timer) | test_hub_api.py | 4 |
| AC-033 | /health redis=ok | main.py | test_health (add) | 4 |
| AC-034 | /health redis=degraded | main.py | test_health (add) | 4 |

---

## Risk Register

| Risk | Impact | Mitigation | Wave |
|------|--------|------------|------|
| R-001: F-001 approve endpoint 409 conflict | HIGH | Change `POST /approve` to call `hub_store.update()` not `save()`. Test in test_designer_hub_integration.py | 4 |
| R-002: asyncio.create_task in tests | MEDIUM | Tests must use `await asyncio.sleep(0)` or `pytest-anyio` to flush pending tasks before asserting audit rows | 7 |
| R-003: SQL table not created on fresh install | HIGH | `HubAuditService.__init__()` runs sync `CREATE TABLE IF NOT EXISTS`. Verify in test_hub_audit_service.py | 3 |
| R-004: lru_cache singleton in tests | MEDIUM | Use `app.dependency_overrides[get_hub_store]` in all integration tests that need mock store | 7 |
| R-005: MARKETER_JWT not set in CI | LOW | `getAuthHeaders()` returns `{}` gracefully; Hub GET endpoints work with any valid JWT; set in .env.test | 5 |
| R-006: _expire_offers_task accesses old _store | HIGH | Update main.py in Wave 4 — task must call `hub_store.list()` not `_store.values()` | 4 |

---

## Design Review Concerns — Resolution Map

| Finding | Severity | Resolution | Wave |
|---------|----------|------------|------|
| F-001: Approve endpoint 409 conflict | CRITICAL | `POST /approve` calls `hub_store.update(approved_offer)` + `_validate_transition(draft, approved)` | 4 (file #7) |
| F-002: `getAuthHeaders()` missing | MAJOR | Add to `src/frontend/lib/config.ts` using `MARKETER_JWT` | 5 (file #9) |
| F-003: `HUB_SERVICE_TOKEN` wrong pattern | MAJOR | Use `MARKETER_JWT` in `hub-api.ts` (matches designer/page.tsx pattern) | 5 (file #10) |
| F-004: SQL table never initialized | MAJOR | `HubAuditService.__init__()` runs `CREATE TABLE IF NOT EXISTS` synchronously | 3 (file #4) |
| F-005: Wrong import path `@/types/offer-brief` | MINOR | Use `@/../../shared/types/offer-brief` in all Hub components | 6 (files #12–16) |
| F-006: O(n) expire task scan | MINOR | Add TODO comment in `_expire_offers_task` noting Redis sorted-set optimization for prod | 4 (file #8) |

---

## Implementation Order Summary

1. **Wave 1** — Add Python package dependencies to `pyproject.toml`
2. **Wave 2** — Add `HUB_REDIS_ENABLED` + `REDIS_URL` to `config.py`
3. **Wave 3** — `hub_store.py` (Protocol + both implementations) + `hub_audit_service.py` (SQL, non-blocking)
4. **Wave 4** — `deps.py` (new factories) → `hub.py` (inject store, transitions, audit, latency) → `designer.py` (auto-save + F-001 approve fix) → `main.py` (health + expire task)
5. **Wave 5** — `lib/config.ts` (getAuthHeaders) → `hub-api.ts` → `actions.ts`
6. **Wave 6** — `StatusBadge` → `ApproveButton` → `OfferCard` → `OfferList` → `page.tsx`
7. **Wave 7** — Unit + integration + frontend tests; baseline must grow from 94 → ≥110 passing

---

## Pipeline Continuation

- **Current stage:** impl-planning complete
- **Next stage:** implementation (Phase 5 — inline, no skill invocation)
- **Branch:** `feature/implementation` (current)
- **Commit strategy:** one commit per wave (`feat: hub-layer wave N — <description>`)
