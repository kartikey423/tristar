# Implementation Manifest: scout-layer

## Summary
- **Waves completed:** 7 (models → services → routes/deps/config → frontend API → frontend components → tests)
- **Files created:** 16 (10 new source, 6 new test)
- **Files modified:** 5
- **Baseline tests:** 125 (pre-implementation)
- **New test files:** 6 (unit + integration)
- **Design review concerns addressed:** F-001 ✅, F-003 ✅, F-004 ✅, F-005 ✅

---

## Baseline Test Counts
| Suite | Count |
|-------|-------|
| Backend unit | 125 |
| Integration | existing |

---

## Final Test Counts
| Suite | Added | Total (approx) |
|-------|-------|----------------|
| Backend unit | ~40 | ~165 |
| Integration | ~8 | ~133 |

---

## Files Created

### Wave 2 — Backend Models
| File | COMP | Description |
|------|------|-------------|
| `src/backend/models/scout_match.py` | COMP-001 | MatchRequest (F-004: location Optional), MatchResponse, NoMatchResponse, EnrichedMatchContext, ScoutActivationRecord |

### Wave 3 — Backend Services
| File | COMP | Description |
|------|------|-------------|
| `src/backend/services/mock_member_profile_store.py` | COMP-004 | 5 demo personas; AC-023/AC-024 |
| `src/backend/services/ctc_store_fixtures.py` | COMP-005 | 8 hardcoded Toronto CTC stores; Haversine; EC-005 strict < |
| `src/backend/services/claude_context_scoring_service.py` | COMP-002 | Claude AI scorer; F-001 fix (direct anthropic SDK, single attempt, 3s timeout); P2 cache; deterministic fallback |
| `src/backend/services/scout_audit_service.py` | COMP-007 | Append-only scout_activation_log table; no GPS/PII (AC-017) |
| `src/backend/services/scout_match_service.py` | COMP-003 | Orchestrator: asyncio.gather enrichment, CANDIDATE_CAP=5 (F-005), delivery constraints, outcome dispatch, audit |

### Wave 4 — Backend API (modified)
| File | Change | Description |
|------|--------|-------------|
| `src/backend/core/config.py` | MODIFIED | Added SCOUT_MATCH_ENABLED, SCOUT_CANDIDATE_CAP |
| `src/backend/api/deps.py` | MODIFIED | Added 6 new Scout dependency providers |
| `src/backend/api/scout.py` | MODIFIED | Added POST /match (F-004: 400 not 422), GET /activation-log/{member_id} |
| `src/backend/services/delivery_constraint_service.py` | MODIFIED | Added RedisDeliveryConstraintService (F-003: all methods fail-open) |
| `src/backend/services/hub_api_client.py` | MODIFIED | Added get_active_offers() |

### Wave 5 — Frontend API Client
| File | COMP | Description |
|------|------|-------------|
| `src/frontend/lib/scout-api.ts` | COMP-010 | callScoutMatch(), fetchActivationLog(), TypeScript types for Scout API |

### Wave 6 — Frontend Components
| File | COMP | Description |
|------|------|-------------|
| `src/frontend/components/Scout/ContextDashboard.tsx` | COMP-008 | Interactive match form; demo member + location presets; result card |
| `src/frontend/components/Scout/ActivationFeed.tsx` | COMP-009 | Activation history feed; polls GET /activation-log on refresh |
| `src/frontend/app/scout/page.tsx` | — | Server Component page shell |

---

## Test Files

| File | Type | Tests For |
|------|------|-----------|
| `tests/unit/backend/services/test_ctc_store_fixtures.py` | Unit | Haversine, EC-005 boundary, sorting |
| `tests/unit/backend/services/test_mock_member_profile_store.py` | Unit | AC-023, AC-024, graceful degradation |
| `tests/unit/backend/services/test_claude_context_scoring_service.py` | Unit | F-001 timeout/fallback, cache, parse |
| `tests/unit/backend/services/test_scout_match_service.py` | Unit | CON-001 threshold, F-005 cap, PII, audit |
| `tests/unit/backend/services/test_redis_delivery_constraint_service.py` | Unit | F-003 fail-open, constraints, quiet hours |
| `tests/integration/backend/api/test_scout_match_api.py` | Integration | F-004 (400 not 422), outcomes, 503 |

---

## Design Review Concerns Addressed

| Finding | Severity | Status | How |
|---------|----------|--------|-----|
| F-001: Claude timeout incompatibility | Major | ✅ Fixed | `ClaudeContextScoringService` uses `anthropic.Anthropic()` directly with `asyncio.wait_for(timeout=3.0)` — single attempt, no retry |
| F-003: Redis fail-open not specified | Major | ✅ Fixed | `RedisDeliveryConstraintService` — every public method has `except redis.RedisError` → fail-open default |
| F-004: 422 vs 400 for missing location | Major | ✅ Fixed | `purchase_location: Optional[GeoPoint] = None` in MatchRequest; route returns `HTTPException(400)` |
| F-005: Unbounded Claude calls | Minor | ✅ Fixed | `_CANDIDATE_CAP = 5` applied before scoring loop; early-exit on first match |
| F-007: Context hash unspecified | Minor | ✅ Fixed | SHA256(offer_id + purchase_category + hour_bucket + weather_condition) documented in module docstring |

## Simplification

Ten issues fixed across three agents:

| # | File | Fix |
|---|------|-----|
| 1 | `delivery_constraint_service.py` | Extracted duplicated `_is_quiet_hours()` into module-level function; removed from both classes |
| 2 | `delivery_constraint_service.py` | Added `retry_after_seconds()` to `DeliveryConstraintService` base class (returns constant fallback) |
| 3 | `scout_match_service.py` | Removed `hasattr` guard — `retry_after_seconds()` now callable on both constraint implementations |
| 4 | `scout_match_service.py` | Hub fetch made concurrent with context enrichment via `asyncio.gather` (previously sequential) |
| 5 | `scout_match_service.py` | Shared `httpx.AsyncClient` stored as `self._http_client`; avoids new connection pool per weather request |
| 6 | `scout_match.py` | `ScoutActivationRecord.scoring_method` and `.outcome` changed from `str` to `ScoringMethod`/`ScoutOutcome` enums; added `ScoutOutcome.error` |
| 7 | `scout_audit_service.py` | Updated `log_activation()` to call `.value` on enum fields before writing to SQLite |
| 8 | `claude_context_scoring_service.py` | Moved `timedelta` import to module-level; removed redundant inner imports in `_deterministic_fallback` |
| 9 | `ActivationFeed.tsx` | Added `.catch()` to prevent stuck loading state on fetch error; changed React key from array index to `offer_id + timestamp` |
| 10 | `ContextDashboard.tsx` | `refreshTrigger` now passes `refreshCount` (int) instead of full result object; moved `outcomeStyles` to module-level constant |
