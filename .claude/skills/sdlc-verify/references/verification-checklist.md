# TriStar Verification Checklist

Domain-specific verification items for the TriStar loyalty offer system.

---

## 1. OfferBrief Schema Validation

### Zod (Frontend)
- [ ] OfferBrief Zod schema exists in `src/shared/types/offer-brief.ts`
- [ ] All required fields validated: offer_id, objective, segment, construct, channels, kpis, risk_flags
- [ ] objective: min 10 chars, max 500 chars
- [ ] segment_criteria: min 1 item, max 10 items
- [ ] Zod parse rejects invalid data with clear error messages
- [ ] Schema exported for use by components and API clients

### Pydantic (Backend)
- [ ] OfferBrief Pydantic model exists in `src/backend/models/offer_brief.py`
- [ ] Field names match Zod schema exactly
- [ ] Field types match Zod schema (string -> str, number -> float/int, etc.)
- [ ] Field validators present for constraints (min_length, max_length, min_items)
- [ ] `from_attributes = True` set in Config (for ORM compatibility)
- [ ] Model used as response_model in API routes

### Cross-Stack Sync
- [ ] Number of fields matches between Zod and Pydantic
- [ ] Field names are identical (snake_case in both)
- [ ] Validation constraints are equivalent
- [ ] Optional/required status matches
- [ ] Nested model structure matches (Segment, Construct, Channel, KPIs, RiskFlags)

---

## 2. Hub State Transition Integrity

### State Machine Implementation
- [ ] All valid states defined: draft, approved, active, expired
- [ ] Transition function exists that validates from->to pairs
- [ ] Valid transitions implemented:
  - [ ] draft -> approved (with fraud check guard)
  - [ ] approved -> active (with score > 60 guard)
  - [ ] active -> expired (with time/redemption guard)
  - [ ] draft -> expired (cancellation/timeout)
  - [ ] approved -> expired (cancellation/window)
- [ ] Invalid transitions rejected with clear error:
  - [ ] approved -> draft (blocked)
  - [ ] active -> approved (blocked)
  - [ ] active -> draft (blocked)
  - [ ] expired -> any (blocked, terminal state)

### Concurrency Safety
- [ ] State transitions are atomic (no partial updates)
- [ ] Race condition handling present (Redis WATCH/MULTI or in-memory lock)
- [ ] Concurrent transitions to same offer handled correctly
- [ ] Transition audit trail recorded (who, when, from_state, to_state)

### Dev vs Prod Parity
- [ ] In-memory store (dev) supports same operations as Redis (prod)
- [ ] State transition logic is identical regardless of store backend
- [ ] Store abstraction layer exists (interface/protocol)

---

## 3. Rate Limiting Enforcement

### Per-Member Frequency
- [ ] 1 notification per member per hour limit implemented
- [ ] Rate limit check happens before notification delivery (not after)
- [ ] Rate-limited notifications are queued (not discarded)
- [ ] Queue drains when rate limit window opens
- [ ] Rate limit counter resets correctly after 1 hour

### Deduplication
- [ ] Same offer not sent to same member within 24 hours
- [ ] Dedup check uses (member_id, offer_id) composite key
- [ ] Dedup window is exactly 24 hours (not longer)
- [ ] Different offers to same member are allowed (within frequency limit)

### Quiet Hours
- [ ] No notifications sent between 10pm and 8am
- [ ] Timezone used is member's local timezone (not server timezone)
- [ ] Notifications during quiet hours are queued for 8am next day
- [ ] Boundary behavior at exactly 10pm and 8am is correct
- [ ] Quiet hours settings are configurable (not hardcoded)

---

## 4. Fraud Detection Integration

### Risk Flag Calculations
- [ ] Over-discounting: flagged when discount > 30% of item value
  - [ ] Warning severity at 20-30%
  - [ ] Critical severity at >30%
- [ ] Cannibalization: flagged when new offer overlaps existing active offer segment
  - [ ] Warning for partial segment overlap
  - [ ] Critical for full segment overlap
- [ ] Frequency abuse: flagged when member receives > 3 offers/day
  - [ ] Warning at 3/day
  - [ ] Critical at >5/day
- [ ] Offer stacking: flagged when member has > 2 concurrent active offers
  - [ ] Warning at 2 active
  - [ ] Critical at >3 active

### Blocking Behavior
- [ ] Critical severity blocks draft -> approved transition
- [ ] Blocking returns clear error with risk flag details
- [ ] Warning severity allows transition but flags for review
- [ ] Risk flags are stored on the OfferBrief object
- [ ] Fraud detection runs BEFORE approval (not after)

### Integration Point
- [ ] Fraud detection called from correct location (hub service or designer service)
- [ ] Fraud detection results logged (structured, no PII)
- [ ] loyalty-fraud-detection skill produces consistent results

---

## 5. Context Signal Scoring Accuracy

### GPS Proximity
- [ ] Distance calculation is correct (haversine or equivalent)
- [ ] Scoring ranges match specification:
  - [ ] < 500m: score 100
  - [ ] 500m - 1km: score 80
  - [ ] 1km - 2km: score 50
  - [ ] 2km - 5km: score 20
  - [ ] > 5km: score 0
- [ ] GPS unavailability handled (signal excluded from average)

### Time/Day Scoring
- [ ] Peak hours for segment correctly identified
- [ ] Time scoring range is 0-100
- [ ] Day of week factored in
- [ ] Timezone handling is correct

### Weather Scoring
- [ ] Weather conditions mapped to offer relevance (0-100)
- [ ] Weather API failure handled gracefully
- [ ] Stale weather data handling (cache TTL, fallback)

### Behavior Scoring
- [ ] Member purchase history incorporated
- [ ] Recency weighting applied (recent activity scores higher)
- [ ] Missing behavior data handled (new member, no history)
- [ ] Stale data threshold defined (>7 days)

### Composite Score
- [ ] Weights sum to 100% (GPS 30%, Time 25%, Weather 20%, Behavior 25%)
- [ ] Weighted average calculation is correct
- [ ] Missing signals excluded and weights redistributed
- [ ] Activation threshold is 60 (not 50, not 70)
- [ ] Score boundary at exactly 60 is tested (should activate)

---

## 6. PII Absence in Logs

### Log Statement Audit
- [ ] Grep all log statements in Python code (logger.info, logger.error, logger.warning, logger.debug)
- [ ] Grep all log statements in TypeScript code (console.log, console.error, console.warn)
- [ ] No member names appear in any log statement
- [ ] No member emails appear in any log statement
- [ ] No member addresses appear in any log statement
- [ ] No member phone numbers appear in any log statement
- [ ] Only member_id appears as member identifier

### GPS Data in Logs
- [ ] Raw GPS coordinates (lat/lon) not logged
- [ ] If distance is logged, it is the calculated distance (not coordinates)
- [ ] GPS data in context signals is used for scoring only (not persisted in logs)

### Claude API Prompts
- [ ] Prompts sent to Claude API do not contain member PII
- [ ] If member data is needed, only anonymized identifiers are sent
- [ ] Claude API responses are not logged in full (may contain generated PII)

### Error Messages
- [ ] Error responses to clients do not leak internal member data
- [ ] Stack traces in error logs do not contain PII
- [ ] Validation error messages do not echo back PII from input

---

## 7. Additional TriStar Checks

### Channel Priority
- [ ] Push > SMS > Email priority order implemented
- [ ] Fallback to next channel if preferred channel fails
- [ ] Channel preference stored per offer (not hardcoded)

### OfferBrief Lifecycle
- [ ] Created offers get unique UUIDs
- [ ] Created_at timestamp set at creation time
- [ ] Status starts as 'draft'
- [ ] Status transitions follow the state machine
- [ ] Expired offers cannot be reactivated

### Claude API Integration
- [ ] Model set to claude-sonnet-4-6
- [ ] Retry logic: 3 attempts with exponential backoff
- [ ] Cache: 5 min TTL for identical objectives
- [ ] API key loaded from environment variable (not hardcoded)
- [ ] Timeout configured (prevent indefinite hanging)
