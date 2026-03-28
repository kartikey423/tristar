# Risk Assessment: scout-layer

## Summary
- **Date**: 2026-03-28
- **Overall Risk Score**: 79
- **Recommendation**: ship_with_monitoring
- **Critical Risks**: 0
- **High Risks**: 1
- **Medium Risks**: 4
- **Low Risks**: 6

---

## Risk Catalog

### High Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation | Residual |
|----|------|-----------|--------|-------|------------|----------|
| R-001 | **CASL opt-out not checked in Scout match pipeline** — `ScoutMatchService._dispatch_outcome()` calls `can_deliver(member_id, amount=0.0, now=now)` without `member_notifications_enabled`. This parameter defaults to `True`, so the CASL opt-out block in `RedisDeliveryConstraintService.can_deliver()` is never triggered via `POST /api/scout/match`. | 3 | 5 | 15 | **Demo only:** all 5 mock profiles have no opt-out flag. No real member data in demo. Needs fix before production release. | Medium (pre-production fix required) |

---

### Medium Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation | Residual |
|----|------|-----------|--------|-------|------------|----------|
| R-002 | **Redis fail-open bypasses rate limits** — All Redis operations in `RedisDeliveryConstraintService` catch `redis.RedisError` and return `can_deliver=True`. During a Redis outage, ALL rate limiting (hourly, dedup, quiet hours) is bypassed. A member could receive unlimited notifications until Redis recovers. | 2 | 4 | 8 | Deliberate design choice (F-003: availability > correctness). Monitor Redis uptime; alert on RedisError warnings in logs. | Low (acceptable for demo; needs Redis HA in prod) |
| R-003 | **Context hash excludes GPS location** — `_context_hash()` uses `offer_id + purchase_category + 3h_bucket + weather`. Two members at very different locations (e.g., 0.1km vs 1.9km from a CTC store) with the same category/weather/hour receive the same cached Claude score, despite having different store proximity (the primary scoring signal). The member at 1.9km may be incorrectly activated with a score calibrated for the 0.1km member. | 3 | 3 | 9 | Cache TTL is 5 minutes. `_CANDIDATE_CAP=5` limits blast radius. In-process cache means different app instances won't share this stale score. P2 feature only. | Low |
| R-004 | **Hub API unavailability silently drops all activations** — `HubApiClient.get_active_offers()` catches exceptions and returns `[]` with a warning log. When Hub is unreachable, `ScoutMatchService.match()` returns `NoMatchResponse("No active offers available")`. There is no alert, no retry, and no circuit breaker. 100% of match requests silently fail when Hub is down. | 3 | 3 | 9 | Warning log at `hub_api:get_active_offers unreachable`. Add monitoring alert on this log pattern. | Medium (monitoring required) |
| R-005 | **Quiet hours enforced in UTC, not member local time** — `_is_quiet_hours()` uses `datetime.utcnow()`. For Canadian members (EST, UTC-5), quiet hours 22:00–08:00 UTC become 17:00–03:00 local. Evening activations (5pm–10pm local) are blocked when members may actively want them. The requirement says "server time" so this is by-design, but creates a poor member experience for western time zones. | 4 | 2 | 8 | Requirement explicitly states "server time" (CON requirement). Document this as a known limitation. Phase 2: add member timezone lookup. | Low |

---

### Low Risks

| ID | Risk | Likelihood | Impact | Score | Mitigation | Residual |
|----|------|-----------|--------|-------|------------|----------|
| R-006 | **In-memory cache is per-process, not shared** — `ClaudeContextScoringService._cache` is an instance dict. In a multi-worker deployment (e.g., `uvicorn --workers 4`), each process has its own cache. Identical requests routed to different workers re-invoke Claude API. Cache deduplication benefit is limited to same-process window. | 3 | 2 | 6 | `lru_cache(maxsize=1)` on DI provider ensures singleton per-process. Demo runs as single process. Production needs Redis-backed score cache for multi-worker benefit. | Low |
| R-007 | **No retry on Claude timeout — fallback notification_text is empty** — F-001 (design decision): single attempt with 3s timeout. When Claude times out or returns an error, `_deterministic_fallback()` returns `notification_text=""`. The `MatchResponse` will contain an empty notification text. The frontend must handle this gracefully (no crash), but the member would receive a blank notification. | 3 | 2 | 6 | Fallback is deliberate per CON-004 (<2s p95). Frontend `ContextDashboard` should display a default text when `notification_text` is empty. | Low |
| R-008 | **SQLite for audit log has limited concurrent write capacity** — `ScoutAuditService` uses `aiosqlite` (single-file SQLite). Under high concurrent activation load, write locks could cause audit log delays or failures. `ScoutAuditService.log_activation()` suppresses SQLite errors (logs but doesn't re-raise), meaning audit failures are silent. | 3 | 2 | 6 | Demo load is low (5 mock members). Production should use Azure SQL. Error suppression in `log_activation()` prevents audit failures from blocking activation, which is correct. | Low |
| R-009 | **Hacky `asyncio.Anthropic()` sync SDK in thread pool** — `anthropic.Anthropic()` (sync SDK) is wrapped in `asyncio.to_thread()`. Under high concurrent load (many simultaneous match requests), the default asyncio thread pool (CPU count × 5) could exhaust. Each in-flight Claude call holds a thread for up to 3 seconds. | 2 | 3 | 6 | `_CANDIDATE_CAP=5` limits calls per request. Demo has low concurrency. Use the `anthropic.AsyncAnthropic()` client in a production upgrade. | Low |
| R-010 | **member_id format not validated** — `MatchRequest.member_id: str = Field(..., min_length=1)`. Any non-empty string is accepted. An attacker could probe the API with arbitrary member IDs to enumerate valid profiles or trigger audit log entries for non-existent members. The impact is limited since unknown member IDs produce a `NoMatchResponse`. | 2 | 2 | 4 | `min_length=1` prevents empty strings. Mock profile store returns `None` for unknown IDs (graceful). No data leakage. | Low |
| R-011 | **f-string in `_parse_response` warning could log Claude response content** — `logger.warning(f"claude_response_parse_failed: {e!r}")` uses f-string formatting. If Claude's response is unexpectedly large or contains structured data that appears PII-like, this content appears verbatim in logs. | 1 | 2 | 2 | Claude prompt contains no member PII (only categories/behavioral data). Output from Claude is score/rationale/notification_text — none of which should contain member-identifying info. | Low |

---

## Risk Clusters

1. **CASL → Compliance cascade** (R-001): Missing `member_notifications_enabled` in Scout pipeline → CASL-opted-out member receives activation → Marketing regulations violated → Legal/brand risk. Single fix: pass `member_notifications_enabled` correctly.

2. **Redis outage → Spam cascade** (R-002 → domain R-RATE-001): Redis down → fail-open → all 3 rate limits bypassed (hourly, dedup, quiet hours) → member receives unlimited same-hour activations → CASL frequency abuse → complaint/churn. Mitigated by monitoring; Redis HA in production.

3. **Hub down → Silent failure cascade** (R-004): Hub unreachable → `offers=[]` → `NoMatchResponse` returned → all activations silently fail → members stop receiving offers → no alert → ops team unaware. Requires monitoring alert on `hub_api:get_active_offers unreachable`.

4. **Claude outage → UX degradation cascade** (R-007): Claude timeout → fallback scoring → `notification_text=""` → frontend displays blank notification → member confused → poor demo experience. Frontend needs empty-string handling.

---

## Ship Recommendation

**ship_with_monitoring**: The scout-layer has 0 Critical risks and 1 High risk that is unmitigated in code (CASL bypass) but mitigated by context (demo-only with mock data, no real opted-out members). The feature is functionally correct for the hackathon demo scenario.

**Before demo launch — must configure:**
- Monitor: Redis error rate (`hub_api:get_active_offers unreachable` and `scout.redis_error` log patterns)
- Monitor: Claude fallback rate (`scout.claude_timeout` and `scoring_method: "fallback"` in activation feed)
- Monitor: Activation volume per member per hour (alert if any member exceeds 2/hr which would indicate rate limiting failure)
- Alert: Any log entry containing `lat=` or `lon=` in Scout service output (PII check)

**Before production release — mandatory fixes:**

1. **Fix R-001 (CASL):** `ScoutMatchService._dispatch_outcome()` must pass `member_notifications_enabled` to `can_deliver()`. Requires fetching the member's CASL consent status from a real membership system (not mock profiles). This is a **hard blocker for production**.

   ```python
   # In _dispatch_outcome(): fetch opt-in status before calling can_deliver
   member_opted_in = await self._member_store.is_notifications_enabled(member_id)
   allowed, reason = self._constraints.can_deliver(
       member_id=member_id, amount=0.0, now=now,
       member_notifications_enabled=member_opted_in,
   )
   ```

2. **Fix R-006 (Cache):** Replace in-process dict cache with Redis-backed cache for multi-worker deployments.

3. **Fix R-007 (Notification text):** Handle `notification_text=""` in `ContextDashboard.tsx` — show a default template when fallback scoring is used.

4. **Fix R-004 (Hub monitoring):** Add structured alert on `hub_api:get_active_offers unreachable` log pattern via Azure Monitor.

### Rollback Trigger
If in production: any member reports receiving notifications after opting out, or if activation rate per member per hour exceeds 2 — disable via `SCOUT_MATCH_ENABLED=false` feature flag (returns HTTP 503).
