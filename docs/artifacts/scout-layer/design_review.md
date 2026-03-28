# Design Review: scout-layer

## Review Summary
- **Date:** 2026-03-28
- **Review Mode:** Initial
- **Score:** 66/100
- **Decision:** APPROVE_WITH_CONCERNS

---

## Findings

### Dimension A: Codebase Validation

- **[MAJOR] F-001 — Claude timeout mechanism conflicts with existing ClaudeApiService**

  The design states `ClaudeContextScoringService` should use `httpx.AsyncClient(timeout=3.0)` for Claude calls and lists `ClaudeApiService (existing)` as a dependency. Both references are problematic:

  1. Claude uses the `anthropic` Python SDK (sync, via `asyncio.to_thread()`), not httpx. There is no `httpx` client for Claude in this codebase.
  2. `ClaudeApiService._call_with_retry()` retries 3× with 1s + 2s + 4s delays (7s total). If `ClaudeContextScoringService` delegates to it, `asyncio.wait_for(timeout=3.0)` wrapping the entire chain would cancel mid-retry, but the background thread spawned by `asyncio.to_thread()` is not cancellable — it continues running silently.

  **Required fix during implementation:** `ClaudeContextScoringService` must call the `anthropic` SDK directly (not via `ClaudeApiService`) using a single attempt wrapped in `asyncio.wait_for(asyncio.to_thread(client.messages.create, ...), timeout=3.0)`. No retry loop — on `TimeoutError` or `Exception`, fall back to `ContextScoringService` immediately.

- **[MINOR] F-002 — Hub GET /offers auth level not confirmed in design**

  `hub.py:list_offers` uses `Depends(get_current_user)` (any authenticated user) while `save_offer` uses `Depends(require_system_role)`. The design's new `HubApiClient.get_active_offers()` uses `scout_auth.bearer_header()` (service JWT with system role). This works — `get_current_user` accepts service JWTs — but the design should explicitly confirm the token type to avoid implementors using a user JWT accidentally.

---

### Dimension B: Architectural Review

- **[MAJOR] F-003 — Redis fail-open behavior not defined in component interface**

  The ADR for Redis-backed rate limiting (ADR-003) states "fail-open: allow activation if Redis is down, log warning". However, the `RedisDeliveryConstraintService` interface methods (`check_hourly_limit`, `check_dedup`, `record_activation`) show no error type or return contract for Redis connection failures. If `redis.asyncio` raises `ConnectionError`, `ScoutMatchService` will receive an unhandled exception rather than a graceful fallback.

  **Required fix:** `check_hourly_limit()` and `check_dedup()` must internally catch `redis.RedisError` and return `(True, 0)` (allow, no retry) on failure, logging a warning. `record_activation()` must catch `redis.RedisError` and log a warning without raising.

---

### Dimension C: Assumption Challenges

- **[MAJOR] F-004 — Pydantic 422 vs required HTTP 400 for missing location (AC-007)**

  AC-007 specifies: "Given no `purchase_location` is provided, return HTTP 400 with `"detail": "location signal required for activation"`".

  `MatchRequest.purchase_location: GeoPoint` is a required Pydantic v2 field with no `Optional`. When the field is missing, FastAPI returns HTTP 422 (`RequestValidationError`), not 400. This is a spec compliance gap.

  **Required fix during implementation:** Either:
  - (a) Add a `model_validator(mode='before')` on `MatchRequest` that raises `ValueError("location signal required for activation")` when `purchase_location` is absent, and register a custom `RequestValidationError` handler that returns 400 for this specific message; OR
  - (b) Make `purchase_location: Optional[GeoPoint] = None` and validate manually in the route handler with `raise HTTPException(status_code=400, detail="location signal required for activation")`.

  Option (b) is simpler and matches existing patterns in `scout.py` (amount/refund validation at route level).

- **[MINOR] F-005 — p95 latency budget is tight with Claude at 3s timeout**

  ASM-001 assumes Claude p95 = 1.5s. CON-004 requires match endpoint p95 < 2s. With enrichment (`asyncio.gather` — up to 200-400ms) + Claude call (p95 = 1.5s) + Redis checks (~10ms) + Hub fetch (~50ms), the realistic p95 budget is ~1.8-2.0s — barely within CON-004. The design doesn't address this budget explicitly. If Claude degrades to 2.0s p95, the endpoint will violate CON-004 with no mitigation.

  The design should note: concurrent enrichment (`asyncio.gather`) and Hub fetch should overlap where possible. If Hub fetch can start before enrichment completes, this saves ~50ms.

---

### Dimension D: Complexity Concerns

- **[MINOR] F-006 — Sequential offer scoring is O(n) with blocking Claude calls**

  The data flow description scores candidate offers one-at-a-time ("for each candidate offer"). For the hackathon with a small offer catalog (3–10 active offers), this is acceptable. However, the design doesn't cap the number of offers evaluated per request or address what happens with a large Hub catalog. If 20 offers are active and all pass the proximity filter, this could invoke Claude up to 20 times serially (each with a 3s timeout = 60s worst case).

  **Mitigation note (should be in design):** Cap candidate offers at N=5 before scoring. Stop on first score > 60 rather than scoring all candidates.

---

### Dimension E: Alternative Approaches

No findings. All three ADRs present genuine alternatives with honestly documented trade-offs. ADR-001 in particular correctly identifies that Alt C (hybrid re-ranking) would weaken the hackathon AI narrative. The chosen approaches are appropriate for the system's constraints.

---

### Dimension F: Missing Considerations

- **[MINOR] F-007 — P2 context hash algorithm unspecified (REQ-009 / AC-026)**

  The design mentions `scout:cache:{context_hash}` for the P2 scoring cache but doesn't specify which fields are included in the hash or the hash function. A hash over `(offer_id, member_id, purchase_category, hour_bucket, weather_condition)` would be reasonable — but omitting `member_id` would cause member A's cache to be served to member B.

  **Required during implementation:** Specify the hash input fields explicitly. Include `offer_id` + `purchase_category` + `hour_bucket` (not raw timestamp) + `weather_condition`. Exclude `member_id` from hash but include `member behavioral profile hash` if behavioral data affects scoring.

- **[MINOR] F-008 — No max-length guard on `rationale TEXT` column**

  Claude rationales could theoretically be very long. The schema has no `VARCHAR(n)` constraint on `rationale`. SQLite has no practical row size limit but the audit log should protect against unusually large responses. Truncate to 2000 characters before writing.

---

## Score Breakdown

| Category | Count | Points |
|----------|-------|--------|
| Critical | 0 | 0 |
| Major | 3 (F-001, F-003, F-004) | −24 |
| Minor | 5 (F-002, F-005, F-006, F-007, F-008) | −15 |
| Clean Dimensions (E) | 1 | +5 |
| **Total** | | **66/100** |

---

## Gate Decision

**APPROVE_WITH_CONCERNS** — Score 66/100.

The overall architecture is sound. The 3-layer separation is correctly maintained, ADRs demonstrate genuine decision-making, the Redis rate limiting strategy is appropriate, and the Claude-primary scoring design is well-motivated. The existing codebase assumptions are largely accurate.

Three concerns must be tracked as implementation constraints — they are not design flaws requiring re-architecture, but they will cause bugs if implementation follows the design spec literally:

1. **F-001 (Claude timeout):** `ClaudeContextScoringService` must call the anthropic SDK directly with `asyncio.wait_for(timeout=3.0)` — do NOT delegate to `ClaudeApiService._call_with_retry()`.
2. **F-003 (Redis fail-open):** The fail-open contract must be implemented inside the Redis service methods, not assumed to bubble up as an exception.
3. **F-004 (HTTP 400):** Missing location must return 400 (not Pydantic's default 422). Use route-level validation for this field.

---

## Recommendations

1. **Add `_call_once_with_timeout()` method** to `ClaudeApiService` (or implement Claude call directly in `ClaudeContextScoringService`) — single attempt, `asyncio.wait_for(timeout=3.0)`, no retry. Tag this as solving AC-004.

2. **Implement fail-open as defensive defaults** in all `RedisDeliveryConstraintService` public methods. The Redis dependency must never propagate as an unhandled exception to `ScoutMatchService`.

3. **Make `purchase_location` an Optional field** in `MatchRequest`, validate explicitly at route level to return HTTP 400 per AC-007. Add a test case verifying the exact status code and error message.

4. **Cap candidate offers at N=5** in `ScoutMatchService.match()`. Stop scoring as soon as first score > 60 is found. Document this as an implementation optimization note.

5. **Specify context hash inputs** for the P2 cache key before implementing REQ-009. Add to the `ClaudeContextScoringService` docstring.
