# Implementation Plan: scout-layer

## Overview
- **Total files:** 24 (20 new, 4 modified)
- **Waves:** 6 (no Wave 1 — OfferBrief schema unchanged per CON-006)
- **Estimated complexity:** High
- **Test target:** ≥80% coverage for all new Scout files

---

## Pre-Implementation Baseline

Run before writing any code to capture baseline test count:
```bash
pytest tests/ --co -q 2>/dev/null | tail -1
```
Record the number. Target: baseline + ≥30 new tests.

---

## Wave 2: Backend Models
*(Wave 1 skipped — no shared type changes per CON-006)*

| # | File | Action | COMP | Description |
|---|------|--------|------|-------------|
| 1 | `src/backend/models/scout_match.py` | NEW | COMP-008 | MatchRequest, MatchResponse, NoMatchResponse, EnrichedMatchContext Pydantic v2 models |

**Wave 2 Verification:**
- [ ] `from src.backend.models.scout_match import MatchRequest, MatchResponse` imports without error
- [ ] `MatchRequest(member_id="x", purchase_location=None)` passes (Optional field, F-004 fix)
- [ ] `MatchResponse(score=85.0, rationale="...", notification_text="...", offer_id="...", outcome="activated", scoring_method="claude")` validates correctly

**Implementation notes for Wave 2:**
- `purchase_location: Optional[GeoPoint] = None` — NOT a required field. Route-level validation returns HTTP 400 per AC-007 / review F-004.
- `EnrichedMatchContext` must have NO lat/lon fields — only `store_id`, `store_name`, `distance_km` (CON-002 / AC-017).
- `ScoutActivationRecord` fields: `member_id`, `offer_id`, `score`, `rationale`, `scoring_method`, `outcome`, `timestamp` — NO GPS coordinates.

---

## Wave 3: Backend Services

| # | File | Action | COMP | Description |
|---|------|--------|------|-------------|
| 2 | `src/backend/services/mock_member_profile_store.py` | NEW | COMP-003 | 5 hardcoded demo MemberProfile objects, get() returns None for unknown IDs |
| 3 | `src/backend/services/ctc_store_fixtures.py` | NEW | COMP-004 | 8 hardcoded CTC store GeoPoints, Haversine distance, get_nearby(location, radius_km) |
| 4 | `src/backend/services/claude_context_scoring_service.py` | NEW | COMP-005 | Claude AI scorer (single-attempt, 3s timeout) + ContextScoringService fallback |
| 5 | `src/backend/services/delivery_constraint_service.py` | MODIFY | COMP-006 | Add RedisDeliveryConstraintService class alongside existing in-memory class |
| 6 | `src/backend/services/hub_api_client.py` | MODIFY | COMP-009 | Add get_active_offers() method using existing persistent httpx client |
| 7 | `src/backend/services/scout_audit_service.py` | NEW | COMP-007 | ScoutAuditService — scout_activation_log SQLite table, log_match() |
| 8 | `src/backend/services/scout_match_service.py` | NEW | COMP-002 | ScoutMatchService orchestrator — full match flow |

**Wave 3 Verification (run after each file):**
- [ ] After file 2: `MockMemberProfileStore().get("demo-001")` returns profile with loyalty_tier="gold"
- [ ] After file 2: `MockMemberProfileStore().get("unknown-id")` returns `None`
- [ ] After file 3: Stores within 2km returned sorted by distance; store exactly 2.0km excluded (EC-005)
- [ ] After file 4: Claude call path uses `asyncio.wait_for()` not httpx; fallback fires on TimeoutError
- [ ] After file 5: `RedisDeliveryConstraintService.check_hourly_limit()` returns `(True, 0)` on `RedisError` (fail-open)
- [ ] After file 6: `HubApiClient.get_active_offers()` uses existing `self._client` (no new AsyncClient created)
- [ ] After file 7: `scout_activation_log` table created on `ScoutAuditService.__init__()`; rationale truncated at 2000 chars
- [ ] After file 8: `ScoutMatchService.match()` with mock dependencies returns `MatchResponse` for all paths

**Implementation notes for Wave 3:**

**File 4 — `claude_context_scoring_service.py` (addresses review F-001):**
```python
import anthropic
import asyncio
from anthropic import Anthropic

class ClaudeContextScoringService:
    def __init__(self) -> None:
        # Direct anthropic client — NOT ClaudeApiService (no retry loop)
        self._client = Anthropic(api_key=settings.CLAUDE_API_KEY)

    async def score(self, context: EnrichedMatchContext, offer: OfferBrief) -> ClaudeScoreResult:
        prompt = self._build_prompt(context, offer)
        try:
            # Single attempt, 3-second hard timeout. asyncio.to_thread wraps sync SDK.
            response_text = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.messages.create,
                    model=settings.CLAUDE_MODEL,
                    max_tokens=800,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=3.0,
            )
            return self._parse_response(response_text.content[0].text)
        except (asyncio.TimeoutError, Exception):
            # Fallback to deterministic scorer
            return self._deterministic_fallback(context, offer)
```

- `_build_prompt()`: Include absent signals explicitly in prompt body (REQ-004 / AC-012, AC-013)
- `_parse_response()`: Must handle malformed JSON gracefully — try/except around `json.loads()`, fallback on parse error
- Context hash for P2 cache: `hashlib.sha256(f"{offer.offer_id}:{context.request.purchase_category}:{hour_bucket}:{context.weather.condition if context.weather else 'none'}".encode()).hexdigest()` — document in method docstring

**File 5 — `delivery_constraint_service.py` (addresses review F-003):**
- `RedisDeliveryConstraintService` all public methods wrap Redis calls in `try/except redis.RedisError`
- On `RedisError`: log warning, return fail-open defaults: `check_hourly_limit → (True, 0)`, `check_dedup → False`, `record_activation → silently skip`
- Redis key TTL precision: use `PEXPIRE` (milliseconds) for accurate `retry_after_seconds` calculation

**File 6 — `hub_api_client.py`:**
```python
async def get_active_offers(self) -> list[OfferBrief]:
    """GET /api/hub/offers?status=active — Scout reads active offers (read-only)."""
    try:
        response = await self._client.get(  # reuse existing persistent client
            f"{self._base_url}/offers",
            params={"status": "active"},
            headers=scout_auth.bearer_header(),
        )
        response.raise_for_status()
        data = response.json()
        return [OfferBrief(**o) for o in data.get("offers", [])]
    except httpx.HTTPStatusError as e:
        logger.warning(f"Hub active offers fetch failed: {e.response.status_code}")
        return []
    except httpx.RequestError as e:
        logger.warning(f"Hub unreachable for active offers: {e}")
        return []
```

**File 8 — `scout_match_service.py` (addresses review F-005/F-006):**
- Cap candidate offers at **N=5** before scoring loop
- **Stop on first score > 60** — do not score remaining candidates
- Enrich (asyncio.gather) and Hub fetch should run concurrently where possible:
  ```python
  enrichment_task = asyncio.create_task(_enrich(request))
  offers = await hub_client.get_active_offers()  # while enrichment runs
  context = await enrichment_task
  ```
- Quiet hours check BEFORE Claude API call to avoid wasted API cost

---

## Wave 4: Backend API Routes

| # | File | Action | COMP | Description |
|---|------|--------|------|-------------|
| 9 | `src/backend/api/scout.py` | MODIFY | COMP-001 | Add POST /api/scout/match route (keep existing webhook unchanged) |
| 10 | `src/backend/api/deps.py` | MODIFY | COMP-009 | Add lru_cache DI for ScoutMatchService, RedisDeliveryConstraintService, ScoutAuditService, ClaudeContextScoringService |
| 11 | `src/backend/core/config.py` | MODIFY | COMP-010 | Add SCOUT_ENABLED: bool = True feature flag |

**Wave 4 Verification:**
- [ ] `POST /api/scout/match` with missing `purchase_location` → HTTP 400 (not 422) with `"detail": "location signal required for activation"` (AC-007 / F-004)
- [ ] `POST /api/scout/match` with valid body and empty Hub → 200 `{"matches": [], "message": "No active offers available"}` (EC-001)
- [ ] Existing `POST /api/scout/purchase-event` tests still pass (backward compat)
- [ ] `SCOUT_ENABLED=false` in config → route returns 503 or 404

**Implementation notes for Wave 4:**

**File 9 — `scout.py` (addresses review F-004):**
```python
@router.post("/match", response_model=MatchResponse, status_code=200)
async def match_offers(
    request: MatchRequest,
    service: ScoutMatchService = Depends(get_scout_match_service),
) -> MatchResponse | NoMatchResponse:
    # F-004 fix: validate purchase_location at route level → HTTP 400
    if request.purchase_location is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="location signal required for activation",
        )
    if not settings.SCOUT_ENABLED:
        raise HTTPException(status_code=503, detail="Scout match service is disabled")
    return await service.match(request)
```

**File 10 — `deps.py`:**
- Follow existing `@lru_cache(maxsize=1)` pattern for all new DI factories
- `get_redis_delivery_service()` → returns `RedisDeliveryConstraintService` when `HUB_REDIS_ENABLED=True`, else existing `DeliveryConstraintService`
- `get_scout_match_service()` → assembles `ScoutMatchService` with all dependencies injected

---

## Wave 5: Frontend Services

| # | File | Action | COMP | Description |
|---|------|--------|------|-------------|
| 12 | `src/frontend/lib/scout-api.ts` | NEW | — | TypeScript API client for POST /api/scout/match, typed request/response |

**Wave 5 Verification:**
- [ ] TypeScript compiles: `tsc --noEmit` passes
- [ ] `postScoutMatch(request: MatchRequest)` returns typed `MatchResponse | NoMatchResponse`

**Implementation notes for Wave 5:**
- Follow existing `src/frontend/lib/` pattern (check for existing config.ts or api helpers to reuse)
- Use `fetch` API with `Content-Type: application/json`
- Type definitions: Mirror Python `MatchRequest` / `MatchResponse` as TypeScript interfaces in same file or `src/frontend/types/scout.ts`

---

## Wave 6: Frontend Components

| # | File | Action | COMP | Description |
|---|------|--------|------|-------------|
| 13 | `src/frontend/app/scout/page.tsx` | NEW | COMP-011 | Scout page shell — Server Component, exports metadata, renders ContextDashboard in Suspense |
| 14 | `src/frontend/components/Scout/ContextDashboard.tsx` | NEW | COMP-012 | `'use client'` — member selector, store preset, weather preset, Simulate Purchase button |
| 15 | `src/frontend/components/Scout/ActivationFeed.tsx` | NEW | COMP-013 | `'use client'` — list of activation results with score badge, outcome badge, notification preview |

**Wave 6 Verification:**
- [ ] `npm run build` passes (Next.js static analysis)
- [ ] `/scout` page renders without errors in browser
- [ ] Simulate Purchase button calls `POST /api/scout/match` (check Network tab)
- [ ] All 5 member profiles available in dropdown (AC-022)
- [ ] Outcome badge shows correct color: activated=green, queued=yellow, rate_limited=red

**Implementation notes for Wave 6:**

**File 13 — `page.tsx`:**
```tsx
// Server Component (no 'use client') — metadata only
import { Metadata } from 'next';
import { Suspense } from 'react';
import { ContextDashboard } from '@/components/Scout/ContextDashboard';

export const metadata: Metadata = { title: 'Scout — TriStar' };

export default function ScoutPage() {
  return (
    <main className="container mx-auto py-8">
      <h1 className="text-2xl font-bold mb-6">Scout — Real-Time Activation Engine</h1>
      <Suspense fallback={<div>Loading...</div>}>
        <ContextDashboard />
      </Suspense>
    </main>
  );
}
```

**File 14 — `ContextDashboard.tsx`:**
- Cap `feedItems` state at 20 entries (F-009 fix): `setFeedItems(prev => [newItem, ...prev].slice(0, 20))`
- Member profiles hardcoded as constants (same as backend mock store for demo consistency)
- Store presets: array of `{ label: string, location: { lat: float, lon: float } }` for 8 CTC stores
- Weather presets: "clear", "rain", "snow", "cold"

**File 15 — `ActivationFeed.tsx`:**
- Display per activation item: offer_id (truncated), score as colored badge (>75=green, 60-75=yellow, ≤60=red), outcome badge, rationale (max 2 lines with expand), notification_text in styled callout
- scoring_method chip: "claude"=purple, "fallback"=orange, "cached"=blue

---

## Wave 7: Tests

| # | File | Action | Tests For | Key Scenarios |
|---|------|--------|-----------|---------------|
| 16 | `tests/unit/backend/services/test_mock_member_profile_store.py` | NEW | COMP-003 | All 5 profiles return correct data, unknown returns None, demo-001 has loyalty_tier=gold |
| 17 | `tests/unit/backend/services/test_ctc_store_fixtures.py` | NEW | COMP-004 | Stores within 2km returned; exactly 2.0km excluded (EC-005); sorted by distance; empty list if none nearby |
| 18 | `tests/unit/backend/services/test_claude_context_scoring_service.py` | NEW | COMP-005 | Claude happy path, TimeoutError→fallback, malformed JSON→fallback, absent weather in prompt, absent behavioral profile in prompt |
| 19 | `tests/unit/backend/services/test_redis_delivery_constraint_service.py` | NEW | COMP-006 | Hourly limit blocks after 1 activation, dedup blocks same offer, quiet hours at 22:00, activation at 08:00 proceeds, RedisError→fail-open, retry_after_seconds accuracy |
| 20 | `tests/unit/backend/services/test_scout_match_service.py` | NEW | COMP-002 | Full flow: activated, queued (score≤60), rate_limited, quiet hours queued, no offers→NoMatchResponse, missing location handled, all signals absent, EC-003 (score=60→queued) |
| 21 | `tests/unit/backend/services/test_scout_audit_service.py` | NEW | COMP-007 | Table created on init, log_match writes all required fields, no lat/lon in record, rationale truncated at 2000 chars |
| 22 | `tests/integration/backend/api/test_scout_match_api.py` | NEW | COMP-001 | POST /match 200, 400 (missing location), 429 (rate limit), no offers 200, existing webhook still 202 |
| 23 | `tests/unit/frontend/components/Scout/ContextDashboard.test.tsx` | NEW | COMP-012 | 5 member profiles in dropdown, submit calls API, loading state, error displayed |
| 24 | `tests/unit/frontend/components/Scout/ActivationFeed.test.tsx` | NEW | COMP-013 | Activated/queued/rate_limited badges render correctly, notification_text visible, score badge color |

**Wave 7 Verification:**
- [ ] `pytest tests/unit/backend/services/test_mock_member_profile_store.py -v` — all pass
- [ ] `pytest tests/unit/backend/services/test_ctc_store_fixtures.py -v` — all pass, EC-005 verified
- [ ] `pytest tests/unit/backend/services/test_claude_context_scoring_service.py -v` — fallback tests pass
- [ ] `pytest tests/unit/backend/services/test_redis_delivery_constraint_service.py -v` — quiet hours tests use freeze_time
- [ ] `pytest tests/unit/backend/services/test_scout_match_service.py -v` — EC-003 (score=60→queued), EC-007 (22:00→queued), EC-008 (08:00→activated)
- [ ] `pytest tests/integration/backend/api/test_scout_match_api.py -v` — 400 returns HTTP 400 (not 422)
- [ ] `pytest tests/ --cov=src/backend/services/scout_match_service --cov-report=term-missing` — ≥80%
- [ ] `npm test -- --testPathPattern=Scout` — all frontend tests pass

---

## Acceptance Criteria Mapping

| AC ID | Description (abbreviated) | Files | Wave |
|-------|---------------------------|-------|------|
| AC-001 | POST /match → Claude invoked → {score, rationale, notification_text, offer_id} | scout.py, scout_match_service.py, claude_context_scoring_service.py | 3,4 |
| AC-002 | score > 60 → outcome=activated in audit | scout_match_service.py, scout_audit_service.py | 3 |
| AC-003 | score ≤ 60 → outcome=queued | scout_match_service.py, scout_audit_service.py | 3 |
| AC-004 | Claude timeout → fallback, scoring_method=fallback | claude_context_scoring_service.py | 3 |
| AC-005 | Prompt references purchase event | claude_context_scoring_service.py (prompt template) | 3 |
| AC-006 | Only offers within 2km considered | scout_match_service.py, ctc_store_fixtures.py | 3 |
| AC-007 | No purchase_location → HTTP 400 | scout.py (route-level validation) | 4 |
| AC-008 | Member activated in last 60 min → HTTP 429 + retry_after_seconds | scout.py, delivery_constraint_service.py | 3,4 |
| AC-009 | Same offer+member in 24h → skip, try next (no 429) | scout_match_service.py, delivery_constraint_service.py | 3 |
| AC-010 | Quiet hours → queued + delivery_time | scout_match_service.py, delivery_constraint_service.py | 3 |
| AC-011 | Rate limits survive restart | delivery_constraint_service.py (Redis keys) | 3 |
| AC-012 | Weather absent → Claude prompt notes reduced confidence | claude_context_scoring_service.py | 3 |
| AC-013 | No behavioral history → Claude notes it | claude_context_scoring_service.py | 3 |
| AC-014 | Only location+time, score > 60 → activation proceeds | scout_match_service.py | 3 |
| AC-015 | Activated audit event: all required fields, no GPS | scout_audit_service.py | 3 |
| AC-016 | Queued/rate-limited audit event: same fields | scout_audit_service.py | 3 |
| AC-017 | GPS NEVER in audit or logs | scout_audit_service.py, scout_match.py (no lat/lon) | 2,3 |
| AC-018 | notification_text: rewards hook + offer + store + savings | claude_context_scoring_service.py (prompt) | 3 |
| AC-019 | notification_text format matches spec | claude_context_scoring_service.py, ActivationFeed.tsx | 3,6 |
| AC-020 | /scout page with all controls | app/scout/page.tsx, ContextDashboard.tsx | 6 |
| AC-021 | Activation feed shows all required fields | ActivationFeed.tsx | 6 |
| AC-022 | 5 profiles → visibly different outcomes | mock_member_profile_store.py, ContextDashboard.tsx | 3,6 |
| AC-023 | demo-001 → score ≥ 75 for outdoor gear | mock_member_profile_store.py (demo-001 profile) | 3 |
| AC-024 | demo-005 → score ≤ 45 for outdoor gear | mock_member_profile_store.py (demo-005 profile) | 3 |
| AC-025 | Any demo profile → context auto-enriched | scout_match_service.py, mock_member_profile_store.py | 3 |

---

## Design Review Concerns → Implementation Actions

| Finding | Severity | File | Action |
|---------|----------|------|--------|
| F-001: httpx vs anthropic SDK + no-retry | Major | `claude_context_scoring_service.py` | Use `anthropic.Anthropic()` directly + `asyncio.wait_for(asyncio.to_thread(...), timeout=3.0)` — single attempt only |
| F-003: Redis fail-open not in interface | Major | `delivery_constraint_service.py` | All `RedisDeliveryConstraintService` public methods catch `redis.RedisError` and return allow-defaults |
| F-004: HTTP 400 vs Pydantic 422 for missing location | Major | `scout.py` | `purchase_location: Optional[GeoPoint] = None` in model; explicit `HTTPException(status_code=400)` in route |
| F-005: No candidate offer cap | Minor | `scout_match_service.py` | Cap candidates at N=5 before scoring loop; stop scoring on first score > 60 |
| F-006: O(n) sequential Claude calls | Minor | `scout_match_service.py` | N=5 cap + early-stop on score > 60 reduces worst case from O(n) to O(5) |
| F-007: Context hash unspecified | Minor | `claude_context_scoring_service.py` | Hash = SHA256(offer_id + purchase_category + hour_bucket + weather_condition); document in docstring |
| F-008: rationale max-length | Minor | `scout_audit_service.py` | `rationale[:2000]` before writing to DB |

---

## Risk Register

| Risk | Impact | Wave | Mitigation |
|------|--------|------|------------|
| R-001: Claude p95 latency exceeds 3s timeout | High | 3 | asyncio.wait_for enforces hard timeout; fallback fires immediately |
| R-002: Redis unavailable in dev (HUB_REDIS_ENABLED=False) | Medium | 3 | DI selects InMemory service when Redis disabled; tests run with InMemory |
| R-003: Hub returns empty offers list at demo time | High | 3 | EC-001 returns clean 200 + message; pre-load ≥1 offer before demo (ASM-003) |
| R-004: Claude returns malformed JSON | Medium | 3 | `_parse_response()` try/except → deterministic fallback on parse failure |
| R-005: asyncio.to_thread timeout leaves orphan thread | Low | 3 | Acceptable for hackathon; thread completes in background without affecting response |
| R-006: Pydantic v2 vs v1 validator syntax | Medium | 2 | Use `@field_validator` and `@model_validator(mode='before')` — NOT `@validator` (v1) |

---

## Implementation Order Summary

1. **Wave 2** — `scout_match.py` (Pydantic models — foundation for all other files)
2. **Wave 3** — Services in order:
   - `mock_member_profile_store.py` (pure data, no I/O)
   - `ctc_store_fixtures.py` (pure data + math)
   - `claude_context_scoring_service.py` (depends on models + anthropic)
   - `delivery_constraint_service.py` (add RedisDeliveryConstraintService)
   - `hub_api_client.py` (add get_active_offers method)
   - `scout_audit_service.py` (depends on models)
   - `scout_match_service.py` (depends on ALL above services)
3. **Wave 4** — API routes and config:
   - `config.py` (SCOUT_ENABLED flag)
   - `deps.py` (DI for new services)
   - `scout.py` (new /match endpoint)
4. **Wave 5** — `scout-api.ts` (TypeScript API client)
5. **Wave 6** — Frontend components (page → ContextDashboard → ActivationFeed)
6. **Wave 7** — Tests (one file per service, then integration test)

---

## Pipeline Continuation

Next phase: **Implementation (Phase 5)** — implement files in wave order.

After each wave, run verification checklist before proceeding to next wave.

Incremental test protocol:
- After each backend service file: run its corresponding test file
- After Wave 4: run `pytest tests/integration/backend/api/test_scout_match_api.py`
- After Wave 6: run `npm test -- --testPathPattern=Scout`
- Final: `pytest tests/ --cov=src/backend --cov-report=term-missing`
