# Problem Specification: hub-layer

## Meta
- **Feature:** hub-layer
- **Author:** SDLC Requirements Skill
- **Date:** 2026-03-28
- **Status:** Approved
- **Layers Affected:** Hub (Layer 2) backend, Hub (Layer 2) frontend, Designer (Layer 1) integration
- **Priority:** P0 (production upgrade — in-memory → Redis + SQL + UI)

---

## Problem Statement

The Hub layer currently uses an in-memory Python dict (`_store`) as its offer state store. This works for development and integration testing but has critical production gaps:

1. **No persistence** — offers are lost on process restart or deployment
2. **No horizontal scaling** — multiple backend instances have divergent state
3. **No audit trail** — there is no record of who changed what and when (compliance risk)
4. **No UI** — marketers have no visibility into offer state without calling the raw API
5. **No Designer integration** — generated offers are not automatically persisted to Hub

The hub-layer feature upgrades all four dimensions: persistence (Redis), compliance (SQL audit log), visibility (React OfferList frontend), and workflow automation (Designer→Hub auto-save).

---

## Requirements

### P0 — Must Have

| ID | Requirement |
|----|-------------|
| REQ-001 | The Hub store MUST use Redis as primary storage when `HUB_REDIS_ENABLED=true`. When false, it uses the existing in-memory dict (dev/test mode). |
| REQ-002 | When `HUB_REDIS_ENABLED=true` and Redis is unavailable, ALL Hub write and read endpoints MUST return 503 Service Unavailable (fail fast; no silent fallback). |
| REQ-003 | Hub MUST enforce strict status transitions: `draft→approved`, `approved→active`, `active→expired`. Any other transition MUST return 422 with `old_status` and attempted `new_status` in the error detail. |
| REQ-004 | Hub MUST append an audit log entry to SQL for each of: offer created, status transition, GET read (offer or list), and fraud-blocked attempt before Hub save. |
| REQ-005 | The Designer `POST /api/designer/generate` endpoint MUST auto-save the generated OfferBrief to Hub (via `POST /api/hub/offers`) immediately after fraud check passes. |
| REQ-006 | A `/hub` frontend page MUST display an OfferList rendered as a Next.js Server Component, listing all offers from `GET /api/hub/offers`. Each card shows: status badge, `offer_id`, objective, trigger_type label, risk flags severity badge, and (for draft offers) an Approve button. |
| REQ-007 | All Hub API endpoints MUST respond within p95 < 200ms under normal operating conditions. |
| REQ-008 | `GET /health` MUST include a `redis` field in its response body: `"ok"` when Redis is reachable, `"degraded"` when unreachable. |

### P1 — Should Have

| ID | Requirement |
|----|-------------|
| REQ-009 | `HUB_REDIS_ENABLED` MUST be a boolean env var in `Settings` (pydantic-settings). Default: `false` for development. |
| REQ-010 | On each `POST /api/hub/offers` and `PUT /api/hub/offers/{id}/status`, Hub MUST log offer counts by status (draft/approved/active/expired) as a structured INFO log. |
| REQ-011 | Hub MUST log a WARNING when any endpoint response time exceeds 200ms, including the endpoint name and duration_ms. |
| REQ-012 | The Approve button on the OfferList card MUST call `PUT /api/hub/offers/{id}/status?new_status=approved` and trigger a page refresh on success. |

### P2 — Nice to Have

| ID | Requirement |
|----|-------------|
| REQ-013 | OfferList SHOULD support status filter tabs (All / Draft / Approved / Active / Expired) as query params on the Server Component page. |
| REQ-014 | Clicking an offer card SHOULD expand or navigate to a detail view showing the full OfferBrief JSON. |

---

## Acceptance Criteria

### REQ-001: Redis Store

| ID | Given | When | Then |
|----|-------|------|------|
| AC-001 | `HUB_REDIS_ENABLED=true` and Redis is running | `POST /api/hub/offers` is called | Offer is persisted to Redis with key `offer:{offer_id}` and returned with 201 |
| AC-002 | `HUB_REDIS_ENABLED=true` and Redis is running | `GET /api/hub/offers/{id}` is called | Offer is retrieved from Redis and returned with 200 |
| AC-003 | `HUB_REDIS_ENABLED=false` | Any Hub endpoint is called | In-memory dict is used; behaviour identical to current implementation |
| AC-004 | `HUB_REDIS_ENABLED=true` | Backend process restarts | Offers previously saved to Redis are still retrievable after restart |

### REQ-002: Redis Fail-Fast

| ID | Given | When | Then |
|----|-------|------|------|
| AC-005 | `HUB_REDIS_ENABLED=true` and Redis is unreachable | `POST /api/hub/offers` is called | Response is 503 with `{"detail": "Hub storage unavailable — Redis unreachable"}` |
| AC-006 | `HUB_REDIS_ENABLED=true` and Redis is unreachable | `GET /api/hub/offers` is called | Response is 503 (no silent fallback to in-memory) |

### REQ-003: Strict Status Transitions

| ID | Given | When | Then |
|----|-------|------|------|
| AC-007 | Offer exists with `status=draft` | `PUT /status?new_status=approved` | Response 200, offer now has `status=approved` |
| AC-008 | Offer exists with `status=approved` | `PUT /status?new_status=active` | Response 200, offer now has `status=active` |
| AC-009 | Offer exists with `status=active` | `PUT /status?new_status=expired` | Response 200, offer now has `status=expired` |
| AC-010 | Offer exists with `status=draft` | `PUT /status?new_status=active` | Response 422 with `old_status=draft` and `new_status=active` in detail |
| AC-011 | Offer exists with `status=expired` | `PUT /status?new_status=draft` | Response 422 (no rollback allowed) |
| AC-012 | Offer exists with `status=active` | `PUT /status?new_status=draft` | Response 422 |

### REQ-004: SQL Audit Log

| ID | Given | When | Then |
|----|-------|------|------|
| AC-013 | Any Hub endpoint | `POST /api/hub/offers` succeeds | Audit row inserted: `event=offer_created`, `offer_id`, `actor_id`, `timestamp` |
| AC-014 | Any Hub endpoint | `PUT /status` succeeds | Audit row inserted: `event=status_transition`, `old_status`, `new_status`, `actor_id`, `timestamp` |
| AC-015 | Any Hub endpoint | `GET /api/hub/offers` or `GET /api/hub/offers/{id}` | Audit row inserted: `event=offer_read`, `offer_id` (or null for list), `actor_id`, `timestamp` |
| AC-016 | Designer blocks offer for fraud | Before Hub save | Audit row inserted: `event=fraud_blocked`, `offer_id`, `fraud_severity`, `actor_id`, `timestamp` |
| AC-017 | SQL write fails during audit | After main operation completes | WARNING is logged; HTTP response is NOT affected (audit failure is non-blocking) |

### REQ-005: Designer→Hub Auto-Save

| ID | Given | When | Then |
|----|-------|------|------|
| AC-018 | Fraud check passes (severity != critical) | `POST /api/designer/generate` | OfferBrief is automatically saved to Hub with `status=draft` |
| AC-019 | Fraud check returns critical | `POST /api/designer/generate` | Offer is NOT saved to Hub; 422 returned to caller (existing behaviour) |
| AC-020 | Hub returns 409 (duplicate offer_id) | During auto-save | Designer catches the error, logs WARNING, and returns 201 with the offer data (idempotent) |
| AC-021 | Hub returns 503 (Redis down) | During auto-save | Designer returns 503 with detail explaining Hub unavailability |

### REQ-006: Hub Frontend OfferList

| ID | Given | When | Then |
|----|-------|------|------|
| AC-022 | User navigates to `/hub` | Page loads | OfferList renders as Server Component with all offers from `GET /api/hub/offers` |
| AC-023 | Offer has `status=draft` | Displayed on list | Grey status badge; Approve button visible |
| AC-024 | Offer has `status=approved` | Displayed on list | Blue status badge; no Approve button |
| AC-025 | Offer has `status=active` | Displayed on list | Green status badge |
| AC-026 | Offer has `status=expired` | Displayed on list | Red/grey status badge with reduced opacity |
| AC-027 | Offer has `trigger_type=purchase_triggered` | Displayed on list | "Purchase" label shown on card |
| AC-028 | Offer has `fraud_check.severity=critical` | Displayed on list | Red risk severity badge shown (would not normally be in Hub, but defensive render) |
| AC-029 | User clicks Approve button | `PUT /status?new_status=approved` called | Page refreshes; offer card now shows approved badge |
| AC-030 | Hub API returns empty list | Page loads | "No offers yet" empty-state message shown |

### REQ-007: Performance

| ID | Given | When | Then |
|----|-------|------|------|
| AC-031 | Redis is healthy | Any Hub endpoint is called | p95 response time < 200ms |
| AC-032 | Response takes > 200ms | Any Hub endpoint | WARNING log emitted with `endpoint` and `duration_ms` |

### REQ-008: Health Endpoint

| ID | Given | When | Then |
|----|-------|------|------|
| AC-033 | Redis is reachable | `GET /health` | Response includes `"redis": "ok"` |
| AC-034 | Redis is unreachable | `GET /health` | Response includes `"redis": "degraded"` (does not return 503 — health is observability, not a gate) |

---

## Constraints

| ID | Constraint |
|----|------------|
| C-001 | Redis key schema: `offer:{offer_id}` (string key, JSON value). TTL: none (offers persist until explicitly expired). |
| C-002 | Redis maxmemory policy MUST be `noeviction`. Eviction is treated as data loss and must be detected at startup. |
| C-003 | SQL audit table schema: `id` (autoincrement), `offer_id` (varchar), `event` (varchar), `old_status` (nullable), `new_status` (nullable), `actor_id` (varchar), `fraud_severity` (nullable), `timestamp` (datetime). |
| C-004 | All existing Hub API contracts (URL paths, request/response schemas, status codes) MUST remain unchanged. |
| C-005 | Auth model unchanged: `POST /api/hub/offers` and `PUT /status` require `role=system`; GET endpoints require any valid JWT. |
| C-006 | PII rule: Only `actor_id` (=user_id from JWT sub) logged in audit; no names, emails, or addresses. |
| C-007 | Frontend: Next.js 15 App Router Server Component at `src/frontend/app/hub/page.tsx`. No `use client` on the list itself; only the Approve button action uses a Client Component. |
| C-008 | Designer auto-save is fire-and-store (synchronous within the generate request). No background tasks or queues. |

---

## Non-Goals

1. **WebSocket or real-time push** — SSR page refresh on navigation is sufficient; no event streaming in this feature.
2. **Redis Pub/Sub** — Scout will pull from Hub via HTTP; no pub/sub architecture.
3. **API versioning (`/v2`)** — in-place storage upgrade only; same API contracts.
4. **New RBAC roles** — no new roles (system/marketing/analyst remain unchanged).
5. **Search or full-text filtering** — OfferList filters only by `status` and `trigger_type` query params.
6. **Offer auto-expiry** — no cron job or TTL-based expiry; `expired` status is set explicitly by Scout or system callers.
7. **Redis Cluster or Sentinel** — single Redis node (Azure Redis Cache Basic/Standard tier). HA is an infrastructure concern outside this feature.
8. **Read-through cache** — Redis is the primary store, not a cache in front of SQL.

---

## Assumptions

| ID | Assumption | Risk If Wrong |
|----|------------|---------------|
| A-001 | SQLite is used for the SQL audit log in development; migration to PostgreSQL in production is an infra concern outside this feature. | Low — audit log is append-only; schema is simple |
| A-002 | Redis is available as Azure Redis Cache in staging/prod. Local development uses a Docker Redis container. | High — if Redis is unavailable in staging, HUB_REDIS_ENABLED must stay false |
| A-003 | `member_id` is not stored on `OfferBrief`; the Hub audit log records `actor_id` (JWT sub) but not the offer's target member segment. | Low — no member-level Hub filtering required |
| A-004 | The Approve button is accessible to any authenticated user (no new role restriction). Marketing users can approve. | Medium — if role restriction needed, add `require_marketing_role` to PUT /status |
| A-005 | Redis `noeviction` policy is configured by the infrastructure team; Hub startup validates this at boot and logs a CRITICAL if misconfigured. | Medium — silent eviction would cause unexpected 404s |
| A-006 | Designer auto-save uses a direct in-process call to Hub service (not an HTTP call to itself) to avoid network overhead and circular dependency. | Medium — if Hub is extracted to a separate service, this changes |
| A-007 | The frontend Approve button uses a Next.js Server Action (not client-side fetch) for progressive enhancement. | Low — UX is identical either way |

---

## Edge Cases

| ID | Scenario | Expected Behaviour |
|----|----------|--------------------|
| EC-001 | Redis connection lost mid-request | Catch `RedisError`; return 503 with `{"detail": "Hub storage unavailable — Redis unreachable"}` |
| EC-002 | `POST /api/hub/offers` with duplicate `offer_id` | Return 409 Conflict with `offer_id` in detail (existing behaviour, preserved with Redis) |
| EC-003 | `PUT /status` with invalid transition (e.g., `draft→active`) | Return 422 with body `{"detail": "Invalid transition: draft → active. Allowed: draft → approved"}` |
| EC-004 | SQL audit INSERT fails (DB locked, schema mismatch) | Log `WARNING audit_write_failed`; HTTP response unaffected |
| EC-005 | Offer stuck in `approved` indefinitely (Scout hasn't activated) | No auto-expiry; acceptable for MVP — Hub is passive |
| EC-006 | Redis eviction detected at startup (`maxmemory-policy != noeviction`) | Log `CRITICAL redis_eviction_policy_misconfigured`; proceed (warn, don't crash) |
| EC-007 | Designer auto-save returns 409 (offer already in Hub) | Designer logs WARNING, treats as idempotent success, returns 201 to caller |
| EC-008 | Hub returns 503 during Designer auto-save | Designer returns 503 to caller with `{"detail": "Hub unavailable — offer not saved"}` |
| EC-009 | OfferList page loads with Hub returning 503 | Next.js error boundary shows "Hub temporarily unavailable" message; no unhandled exception |
| EC-010 | `GET /api/hub/offers` with `since` filter and naive datetime string | Hub treats naive datetime as UTC (existing fix — preserved) |
| EC-011 | Approve button clicked on offer already approved (race condition) | PUT /status returns 422 (invalid transition approved→approved); UI shows "Already approved" toast |

---

## Backward Compatibility

| Area | Impact | Migration |
|------|--------|-----------|
| Hub API endpoints | **None** — same URLs, same schemas, same status codes | No migration needed |
| `_store` in-memory dict | **Replaced** when `HUB_REDIS_ENABLED=true`; still used when false | Existing tests use in-memory; no change required |
| `OfferBrief` Pydantic model | **No change** — no new fields added | No migration |
| Designer API | `POST /api/designer/generate` response adds auto-save side effect | Callers receive same 201 response; Hub save is transparent |
| Existing integration tests | All 20 hub integration tests MUST remain green after Redis storage layer added | Tests use in-memory (HUB_REDIS_ENABLED=false default); no change required |
| `GET /health` | **Extended** — adds `redis` field | Existing callers unaffected; new field is additive |

---

## Glossary

| Term | Definition |
|------|------------|
| Hub | Layer 2 of TriStar; the shared offer state store. Single source of truth for all OfferBrief lifecycle state. |
| OfferBrief | Core domain object: offer_id, objective, segment, construct, channels, kpis, risk_flags, status, trigger_type, created_at, valid_until. |
| Status machine | The valid offer lifecycle: `draft → approved → active → expired`. No other transitions permitted. |
| HUB_REDIS_ENABLED | Boolean env var. false = in-memory (dev/test). true = Redis (staging/prod). |
| Audit log | Append-only SQL table recording every offer event for compliance and debugging. |
| Fail-fast | Pattern where a failing dependency (Redis) causes immediate error response (503) rather than silent degradation. |
| Actor | The authenticated entity performing an action; identified by JWT `sub` claim (`actor_id`). |
| Purchase-triggered | An offer generated automatically by Scout in response to a purchase event. May be saved to Hub with `status=active` directly (F-003). |
| Marketer-initiated | An offer generated by a marketer via the Designer UI. Must follow `draft → approved → active` flow. |
| SSR | Server-Side Rendering. Next.js Server Component pattern: data fetched on the server, HTML sent to client. No client-side JS for the list render. |
