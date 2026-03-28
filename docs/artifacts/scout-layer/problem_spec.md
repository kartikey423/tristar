# Problem Specification: scout-layer

## Meta
- **Feature:** scout-layer
- **Date:** 2026-03-28
- **Status:** Approved
- **Author:** TriStar SDLC Pipeline (sdlc-requirements)
- **Artifact Path:** `docs/artifacts/scout-layer/problem_spec.md`

---

## Problem Statement

Triangle loyalty today is reactive: members earn points, then manually decide when to redeem them. TriStar Scout transforms this into a proactive, predictive experience. When a member makes a purchase at any Triangle partner (e.g., Tim Hortons), Scout detects the transaction context — store location, purchase category, rewards earned, weather at that location, time of day, and day-of-week — and uses Claude AI to predict where the member is likely heading next and what CTC offer would be most relevant to them right now.

If the AI-assessed contextual fit score exceeds 60/100, Scout activates the best matching offer and generates a personalized notification:

> *"You earned 120 Triangle points at Tim Hortons. The Canadian Tire 400m from you has 20% off Outdoor gear — that's 15% cheaper than Amazon. Use your rewards now."*

This makes TriStar's AI presence visible at the moment that matters most: the activation moment, not just the design moment.

**Actors:**
- **Triangle Member** — receives the personalized push notification
- **Scout Engine** — the system receiving context signals and making activation decisions
- **Hub** — source of approved active offers; destination for activation audit events
- **Claude AI** — the intelligence layer scoring contextual fit and generating notification copy

---

## Requirements

### P0 — Must Have

**REQ-001: Claude AI context scoring**
Scout must use Claude API (claude-sonnet-4-6) as the primary scoring engine. All available context signals and the candidate offer's details are submitted to Claude. Claude returns a contextual fit score (0–100) and a natural-language rationale explaining why this offer is or is not a good match for the member right now.

Acceptance Criteria:
- AC-001: Given an active offer exists in Hub and a full context signal is provided, When `POST /api/scout/match` is called, Then Claude is invoked with a prompt containing all context signals + offer details, and the response contains `{ score: number, rationale: string, notification_text: string, offer_id: string }`
- AC-002: Given Claude returns a score > 60, When the match endpoint processes the result, Then the offer is marked as activated in the audit log with `outcome: "activated"`
- AC-003: Given Claude returns a score ≤ 60, When the match endpoint processes the result, Then no activation occurs and the result is logged with `outcome: "queued"`
- AC-004: Given Claude API times out (>3 seconds), When this occurs during scoring, Then Scout falls back to the deterministic scoring formula (location 40pts + time 30pts + weather 20pts + behavior 10pts) and logs `scoring_method: "fallback"` in the audit event

**REQ-002: Purchase-context trigger and predictive intent**
The context signal must include the member's most recent Triangle purchase event: the store location (lat/lon), purchase category, rewards points earned, and the inferred day context (weekday, weekend, long weekend). Claude uses this purchase event to predict the member's likely next destination and need.

Acceptance Criteria:
- AC-005: Given a context signal containing `purchase_location`, `purchase_category`, `rewards_earned`, and `day_context`, When Claude evaluates the match, Then Claude's rationale references the purchase event (e.g., "Member bought coffee near Dundas Square — likely heading to office")
- AC-006: Given the predicted destination, When Scout fetches candidate offers, Then only offers at CTC stores within 2km of the predicted destination are considered for scoring
- AC-007: Given no `purchase_location` is provided in the context signal, When `POST /api/scout/match` is called, Then return HTTP 400 with `"detail": "location signal required for activation"`

**REQ-003: Redis-backed rate limiting with three hard limits**
Scout must enforce three independent activation limits that survive process restarts:
1. One activation per member per hour
2. No duplicate activation of the same offer for the same member within 24 hours
3. No activations during quiet hours (22:00–08:00 server time)

Acceptance Criteria:
- AC-008: Given a member has already had an offer activated in the last 60 minutes, When a new `POST /api/scout/match` is called for that member, Then return HTTP 429 with `{ "detail": "rate_limited", "retry_after_seconds": N }`
- AC-009: Given the same offer was activated for the same member in the last 24 hours, When that offer appears as a candidate, Then Scout skips that offer and evaluates the next best candidate (no 429 — dedup is per-offer, not per-member)
- AC-010: Given the current server time is between 22:00 and 08:00, When `POST /api/scout/match` is called, Then no activation occurs; the best candidate is queued and the response contains `{ "queued": true, "delivery_time": "HH:MM next day" }`
- AC-011: Given rate limits are implemented, When the service restarts, Then all rate limit state is preserved (no member can bypass limits via restart)

**REQ-004: Graceful degradation on missing signals**
If any context signal is unavailable (weather API down, behavioral data absent), Scout must continue scoring with available signals. Claude is explicitly prompted about which signals are absent and adjusts confidence accordingly. GPS (purchase location) is the only required signal.

Acceptance Criteria:
- AC-012: Given the weather API is unavailable when a match request arrives, When Claude is invoked, Then the weather signal is omitted from the prompt and Claude's response notes reduced confidence; activation can still occur if score > 60
- AC-013: Given no behavioral history exists for the member, When Claude scores the match, Then the scoring prompt indicates no behavioral data; Claude scores purely on location, time, and weather context
- AC-014: Given all optional signals are absent (only location + time available), When Claude scores and returns > 60, Then activation proceeds normally

**REQ-005: Activation audit log**
Every match request outcome — whether activated, queued, rate-limited, or errored — must be written to the Hub audit trail.

Acceptance Criteria:
- AC-015: Given a successful activation, When the audit event is written, Then it contains `member_id`, `offer_id`, `score` (number), `rationale` (string from Claude), `scoring_method` ("claude" or "fallback"), `outcome` ("activated"), and `timestamp`
- AC-016: Given a queued or rate-limited outcome, When the audit event is written, Then it contains the same fields with `outcome: "queued"` or `outcome: "rate_limited"` respectively
- AC-017: Given any audit event is written, Then raw GPS coordinates (lat/lon) MUST NOT appear anywhere in the audit record or any log statement; only `member_id` is permitted to identify the member

---

### P1 — Should Have

**REQ-006: Personalized notification text generation**
Claude must generate the exact notification copy for each activation, referencing: the trigger purchase and rewards earned, the specific offer value, the CTC store name, the distance to the store, and the savings vs marketplace pricing.

Acceptance Criteria:
- AC-018: Given activation score > 60, When Claude generates notification text, Then `notification_text` contains all four elements: rewards hook (e.g., "You earned 120 points at Tim Hortons"), offer description, store name + distance, and savings claim
- AC-019: Given notification text is generated, When it appears in the Scout ContextDashboard activation feed, Then the text matches the format: `"[Rewards hook] — [Offer] at [Store], [Distance]. [Savings claim]."`

**REQ-007: ContextDashboard frontend**
An interactive Scout demo UI that allows a demo operator to simulate member purchase events and observe live activation results.

Acceptance Criteria:
- AC-020: Given the Scout page at `/scout`, When a user selects a member profile, a CTC store location, and a weather preset, Then clicking "Simulate Purchase" calls `POST /api/scout/match` with that context
- AC-021: Given a match response is returned, When it appears in the activation feed panel, Then it displays: offer title, Claude score (0–100), Claude rationale, notification preview text, and outcome badge (activated / queued / rate_limited)
- AC-022: Given five demo member profiles exist, When the user selects different profiles, Then the activation feed shows visibly different outcomes (different offers, different scores, different rationale)

**REQ-008: Mock member behavioral profiles**
Five hardcoded demo member profiles providing varied purchase histories for reliable demo outcomes.

Acceptance Criteria:
- AC-023: Given member `demo-001` (frequent outdoor/sporting goods buyer near CTC stores), When matched against an active outdoor gear offer at Canadian Tire, Then Claude score should be ≥ 75
- AC-024: Given member `demo-005` (auto parts buyer, suburban location), When matched against an outdoor gear offer, Then Claude score should be ≤ 45
- AC-025: Given any of the five profiles, When `POST /api/scout/match` is called with `member_id` from a mock profile, Then the context signal is automatically enriched with that profile's behavioral data

---

### P2 — Nice to Have

**REQ-009: Claude scoring result cache**
Cache Claude's scoring result for identical (offer, context) combinations to reduce API cost and latency for repeated identical signals within a short window.

Acceptance Criteria:
- AC-026: Given the same `(offer_id, context_hash)` is submitted twice within 5 minutes, When the second request arrives, Then Claude API is not called; the cached score and rationale are returned directly
- AC-027: Given a cached response is used, When the audit event is written, Then `scoring_method: "cached"` appears in the audit record

---

## Constraints

| ID | Constraint | Source |
|----|-----------|--------|
| CON-001 | Activation threshold is strictly > 60 (score of exactly 60 does NOT activate) | Architecture |
| CON-002 | GPS coordinates must never appear in logs or audit trail | Security rule |
| CON-003 | Claude model must be `claude-sonnet-4-6` | Tech stack |
| CON-004 | Match endpoint p95 latency target: < 2 seconds (Claude AI call included) | Performance |
| CON-005 | Rate limiting state must survive service restarts | Reliability |
| CON-006 | No changes to Hub API contracts or OfferBrief schema permitted | Backward compat |
| CON-007 | Weather API: OpenWeatherMap; graceful degradation if key absent | Integration |
| CON-008 | Scout reads Hub offers via existing `GET /api/hub/offers?status=active` | Hub integration |

---

## Non-Goals

| ID | What We Are NOT Building | Rationale |
|----|-------------------------|-----------|
| NG-001 | Real FCM/APNs push notification delivery | Requires mobile app, device token registration, and Firebase/Apple developer accounts — out of scope for hackathon. Notifications simulated in dashboard. |
| NG-002 | Real Triangle member database integration | Real Triangle rewards ledger requires authenticated enterprise API access. Mock profiles provide demo credibility without production dependencies. |
| NG-003 | Activating multiple offers per match call | Scout activates at most 1 offer per call (the highest Claude-scored candidate). Multi-offer activation raises member spam risk and is deferred. |
| NG-004 | SMS and email delivery channels | Channel model supports these types, but only push is simulated. Multi-channel delivery is a post-hackathon enhancement. |
| NG-005 | Offer redemption tracking | Scout's scope ends at activation (notification sent). Redemption events (member taps notification, buys product) are a separate flow not built in this layer. |

---

## Assumptions

| ID | Assumption | Risk If Wrong |
|----|-----------|--------------|
| ASM-001 | Claude API (claude-sonnet-4-6) responds within 1.5s p95 for Scout scoring prompts; context + offer details fit within a single prompt without hitting token limits | medium — if response exceeds 3s budget, deterministic fallback activates automatically (AC-004) |
| ASM-002 | OpenWeatherMap API key will be available in `.env` for hackathon demo | low — graceful degradation (REQ-004) means Scout continues without weather signal |
| ASM-003 | Hub contains at least one active offer at demo time | high — Scout returns `{ matches: [] }` if Hub is empty; always pre-load at least one offer before demo |
| ASM-004 | Five mock member profiles provide sufficient behavioral diversity to demonstrate varied AI outcomes | low — profiles are fully controlled; can be adjusted at any time |
| ASM-005 | Server timezone (UTC) is acceptable for quiet hours enforcement in hackathon context | low — production would use member's local timezone; documented as a known simplification |
| ASM-006 | CTC store coordinates (for mock nearby-store lookup) can be hardcoded as demo fixtures | low — real store directory integration is NG-002 |

---

## Edge Cases

| ID | Scenario | Expected Behavior |
|----|----------|------------------|
| EC-001 | No active offers in Hub at match time | Return `{ matches: [], message: "No active offers available" }` — no Claude call made, HTTP 200 |
| EC-002 | All active offers are already rate-limited (24h dedup) for this member | Return `{ activated: null, queued: 0, rate_limited: N }` — no activation, HTTP 200 |
| EC-003 | Claude returns score exactly 60 | Does NOT activate (threshold is strictly `> 60`); logged as `outcome: "queued"` |
| EC-004 | Claude API times out (>3s) | Fall back to deterministic formula; log `scoring_method: "fallback"`; activation still possible if fallback score > 60 |
| EC-005 | Member location exactly 2km from store | Location score = 0pts in fallback formula (range is strictly `< 2km`); Claude informed of boundary in prompt |
| EC-006 | Multiple offers score > 60 | Claude ranks all qualifying candidates; only the highest-scoring offer activates per call |
| EC-007 | Request arrives at exactly 22:00 (start of quiet hours) | Offer queued, not activated; `delivery_time` set to `08:00` next morning |
| EC-008 | Request arrives at exactly 08:00 (end of quiet hours) | Activation proceeds normally (quiet hours end at 08:00, exclusive) |
| EC-009 | Member exhausted hourly limit and requests again 59 minutes later | HTTP 429 with accurate `retry_after_seconds` (≤ 60 seconds remaining) |
| EC-010 | Same offer submitted twice within 5-minute cache window (P2) | Second call returns cached score; no Claude API call; audit records `scoring_method: "cached"` |

---

## Backward Compatibility

**Verdict: Fully compatible.**

- Scout is a new layer. It adds new API endpoints (`/api/scout/*`) with no modifications to existing endpoints.
- Hub API is consumed read-only by Scout (`GET /api/hub/offers?status=active`). No Hub endpoint changes.
- Activation audit events use the existing `HubAuditEvent` model with existing event types (`offer_activated`). No schema migration.
- OfferBrief schema: no new fields, no removed fields, no type changes.
- Existing Designer and Hub layers continue operating unchanged.

---

## Feature Flags & Rollout

| Environment | Scout Enabled | Notes |
|-------------|--------------|-------|
| Development | Yes | Full feature, mock profiles, weather API optional |
| Staging | Yes | Real weather API, mock member profiles |
| Production | Via `SCOUT_ENABLED` env var | Default: `true`. Set to `false` to disable without code change. |

**Rollout strategy:** Standard dev → staging → prod. No canary or A/B rollout required for initial launch. Scout is additive — it only reads Hub and logs events; disabling it has zero impact on Designer and Hub.

**Rollback:** Set `SCOUT_ENABLED=false` — instant disable. No data migration required.

---

## Glossary

| Term | Definition |
|------|-----------|
| Context signal | The bundle of real-time data used to score an offer: purchase location, purchase category, rewards earned, weather, time, day-of-week, member behavioral profile |
| Activation | The event where Scout determines an offer should be delivered to a member (score > 60) |
| Quiet hours | The window 22:00–08:00 server time during which no activations are delivered |
| Deterministic fallback | The fixed scoring formula used when Claude API is unavailable: Location (40pts) + Time (30pts) + Weather (20pts) + Behavior (10pts) |
| Rate limiting | Three independent guards: 1/hr/member, 24h dedup per offer+member, quiet hours |
| Notification text | The human-readable message Claude generates for the activation, referencing the trigger purchase and savings |
| Mock member profile | One of five hardcoded demo personas with pre-defined behavioral history used in the ContextDashboard |
| Predictive intent | Claude's inference about where a member is heading and what they need next, based on their most recent purchase context |

---

## Quality Gate Results

| Gate | Status | Notes |
|------|--------|-------|
| Gate 1: Mandatory category coverage | ✅ PASS | All 6 categories covered: scope, error states, security, performance, rollout, backward compat |
| Gate 2: P0 requirements defined | ✅ PASS | 5 P0 requirements (REQ-001 through REQ-005), each with measurable ACs |
| Gate 3: Non-goals defined | ✅ PASS | 5 non-goals with rationale (NG-001 through NG-005) |
| Gate 4: Edge cases defined | ✅ PASS | 10 edge cases covering error handling, boundary values, rate limits, clock boundaries |
| Gate 5: ACs for P0 requirements | ✅ PASS | All 5 P0 requirements have Given/When/Then ACs (AC-001 through AC-017) |
| Gate 6: Backward compatibility | ✅ PASS | Explicit verdict: Fully compatible. No Hub/OfferBrief changes. |
| Gate 7: No implementation details | ✅ PASS | Requirements describe behavior; technology choices deferred to design spec |
| Gate 8: Assumptions have risk levels | ✅ PASS | All 6 assumptions have risk_if_wrong levels with mitigations for medium/high |
