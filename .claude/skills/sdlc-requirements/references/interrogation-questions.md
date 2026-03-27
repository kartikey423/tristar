# Interrogation Question Bank

Full question bank organized by category. Each category includes generic engineering questions enhanced with TriStar domain context.

---

## 1. Scope & Layers

**TriStar Context:** The system has 3 layers - Designer (marketer copilot via Claude API), Hub (shared state store), Scout (real-time activation engine). All communication flows through Hub.

- Which TriStar layers does this feature touch?
  a) Designer only (Layer 1)
  b) Hub only (Layer 2)
  c) Scout only (Layer 3)
  d) Designer + Hub
  e) Hub + Scout
  f) All three layers

- Within the affected layers, which specific capabilities are involved?
  - Designer: offer generation, objective parsing, risk flag analysis, fraud pre-check
  - Hub: state management, offer lifecycle, approval workflow, audit logging
  - Scout: context signal ingestion, semantic matching, activation triggers, notification delivery

- Does this feature introduce a new flow between layers, or modify an existing one?
  a) New flow (describe)
  b) Modifies existing Designer->Hub flow
  c) Modifies existing Hub->Scout flow
  d) Modifies end-to-end Designer->Hub->Scout flow
  e) No inter-layer changes

- Is there any scenario where this feature requires direct Designer->Scout communication (bypassing Hub)?
  a) No, all communication goes through Hub (correct pattern)
  b) Yes (describe why - this violates architecture and needs justification)

---

## 2. Data Model

**TriStar Context:** OfferBrief is the core schema (offer_id, objective, segment, construct, channels, kpis, risk_flags). Types defined in src/shared/types/ (Zod + TypeScript), mirrored in src/backend/models/ (Pydantic v2).

- Does this feature require changes to the OfferBrief schema?
  a) No changes to OfferBrief
  b) New fields added to OfferBrief
  c) Existing fields modified
  d) New nested model added (e.g., new segment type, new channel)

- Which OfferBrief fields does this feature read or write?
  - offer_id, objective, segment, construct, channels, kpis, risk_flags, status, created_at

- Does this feature introduce new Hub state transitions?
  a) No new states or transitions
  b) New intermediate state (describe)
  c) New terminal state (describe)
  d) Modified transition rules for existing states

- What is the valid state flow for offers affected by this feature?
  - Current: draft -> approved -> active -> expired
  - Proposed changes (if any)?

- Are new Pydantic v2 models needed on the backend?
  a) No new models
  b) New request model
  c) New response model
  d) New internal domain model

- Are new Zod schemas needed on the frontend?
  a) No new schemas
  b) New form validation schema
  c) New API response schema
  d) Modified existing schema

- Does this feature require new segment definitions or criteria?
  a) Uses existing segments (high_value, lapsed, new_member, active)
  b) New segment criteria needed (describe)

---

## 3. Error States

**TriStar Context:** Multiple external dependencies (Claude API, Weather API) and internal systems (Hub state store, fraud detection) can fail. Retry strategy: 3 attempts with exponential backoff for Claude API.

- What happens when the Claude API fails during this feature's execution?
  a) Retry with exponential backoff (3 attempts)
  b) Return cached response (5 min TTL)
  c) Graceful degradation with fallback
  d) Hard failure with user notification
  e) Not applicable (feature doesn't use Claude API)

- What happens when the Weather API is unavailable?
  a) Skip weather context signal (reduce activation score)
  b) Use cached weather data (stale ok)
  c) Block activation until weather available
  d) Not applicable (feature doesn't use weather data)

- What happens when context signals are unavailable or stale?
  - GPS unavailable: skip proximity scoring? block activation?
  - Behavior data >7 days old: use anyway? discount score? exclude?
  - Time signal: can this ever be unavailable?

- What happens when fraud detection flags a critical risk?
  a) Block the operation entirely
  b) Allow with warning to user
  c) Queue for manual review
  d) Not applicable

- What happens when Hub state transition conflicts occur (race condition)?
  a) First-write-wins
  b) Last-write-wins
  c) Reject with conflict error
  d) Queue for retry

- What happens when Redis is unavailable (production Hub store)?
  a) Fall back to in-memory store
  b) Return 503 Service Unavailable
  c) Queue operations for replay
  d) Not applicable (dev uses in-memory)

---

## 4. Security & PII

**TriStar Context:** Only member_id may appear in logs. No names, emails, addresses, phone numbers. Claude API key must never be exposed. JWT tokens expire in 1h.

- Does this feature handle any member data?
  a) No member data involved
  b) member_id only (compliant)
  c) Additional member data (requires PII review - what data?)

- Does this feature introduce new log statements?
  a) No new logging
  b) Yes - all use member_id only (compliant)
  c) Yes - need to verify PII exclusion

- Does this feature require authentication?
  a) Public endpoint (no auth)
  b) JWT-authenticated endpoint
  c) Role-based access (which roles?)

- Does this feature involve input from external sources that needs validation?
  a) User input (validate with Zod frontend + Pydantic backend)
  b) External API response (validate with Pydantic)
  c) Context signals (validate format and range)
  d) No external input

- Are there SQL injection, XSS, or command injection vectors?
  a) No user input reaches database queries
  b) All queries use parameterized statements / ORM
  c) Needs review (describe input path)

- Does this feature interact with the Claude API key?
  a) No
  b) Yes - key accessed via environment variable / Key Vault only
  c) Yes - needs review for exposure risk

---

## 5. Performance

**TriStar Context:** API p95 <200ms, Scout activation <500ms, frontend FCP <2s. Redis caching with 5 min TTL for Claude API responses.

- What is the acceptable latency for this feature's primary operation?
  a) <200ms (standard API call)
  b) <500ms (activation/scoring)
  c) <2s (page load / complex generation)
  d) >2s acceptable (background processing)

- Does this feature introduce new database queries?
  a) No new queries
  b) Simple lookup (indexed)
  c) Complex query (joins, aggregations)
  d) Bulk operation (batch processing)

- Is caching appropriate for this feature?
  a) No caching needed (data changes frequently)
  b) Redis cache with TTL (what TTL?)
  c) In-memory cache (request-scoped)
  d) CDN caching (static assets)

- What is the expected request volume?
  a) Low (<10 req/min)
  b) Medium (10-100 req/min)
  c) High (>100 req/min, needs rate limiting)

- Does this feature affect frontend bundle size?
  a) No new client-side code
  b) Small addition (<10KB)
  c) Significant addition (needs code splitting / lazy loading)

- Does this feature require concurrent operations?
  a) Sequential processing is fine
  b) Needs asyncio.gather for parallel API calls
  c) Needs background task processing

---

## 6. Feature Flags & Rollout

**TriStar Context:** Environment-based configuration (dev/staging/prod). A/B testing capability for offer targeting.

- Should this feature be behind a feature flag?
  a) No - always enabled
  b) Yes - environment-based (dev only initially)
  c) Yes - percentage rollout (start at 10%)
  d) Yes - A/B test with control group

- What is the rollout strategy?
  a) Deploy to all environments simultaneously
  b) Dev -> Staging -> Prod (standard)
  c) Canary deployment (subset of users first)

- What is the rollback plan if this feature causes issues?
  a) Feature flag off (instant)
  b) Code revert required
  c) Data migration rollback needed

- Does this feature affect offer targeting or activation logic?
  a) No
  b) Yes - needs A/B testing to measure impact on redemption rates

---

## 7. Integration Points

**TriStar Context:** Designer uses Claude API (claude-sonnet-4-6). Scout uses Weather API. Hub uses Redis (prod) or in-memory dict (dev). All layers communicate through Hub.

- Which external APIs does this feature interact with?
  a) Claude API (claude-sonnet-4-6) - offer generation
  b) Weather API - context signals
  c) Both
  d) Neither

- Does this feature modify the Designer->Hub communication?
  a) No changes
  b) New data passed from Designer to Hub
  c) New validation added at Hub ingestion
  d) New response data from Hub to Designer

- Does this feature modify the Hub->Scout communication?
  a) No changes
  b) New data passed from Hub to Scout
  c) New activation criteria
  d) New notification triggers

- Does the feature need to work differently in dev (in-memory) vs prod (Redis)?
  a) No - same behavior regardless of store
  b) Yes - describe differences

---

## 8. Loading & Async States

**TriStar Context:** React 19 with Suspense, Server Components, useOptimistic. FastAPI with async/await.

- Does this feature have visible loading states?
  a) No UI changes
  b) Suspense boundary with fallback
  c) Skeleton loader
  d) Progress indicator (for long operations like Claude API generation)

- Should any operations use optimistic updates (useOptimistic)?
  a) No - wait for server confirmation
  b) Yes - offer approval (likely to succeed)
  c) Yes - status change (likely to succeed)
  d) Other (describe)

- Does this feature involve streaming responses?
  a) No
  b) Yes - Claude API streaming for offer generation
  c) Yes - real-time context signal updates

- Are there background tasks that need status tracking?
  a) No background tasks
  b) Yes - notification delivery
  c) Yes - batch processing
  d) Yes - other (describe)

---

## 9. Observability

**TriStar Context:** Structured logging with loguru. JSON output. Audit trail for Hub state changes.

- What should be logged for this feature?
  a) Standard request/response logging only
  b) Business events (offer created, approved, activated)
  c) Error conditions with context
  d) Performance metrics (latency, throughput)

- Does this feature need audit trail entries?
  a) No audit needed
  b) Yes - Hub state changes must be audited
  c) Yes - user actions must be audited
  d) Yes - external API calls must be audited

- What metrics should be tracked?
  a) No new metrics
  b) Success/failure rates
  c) Latency percentiles
  d) Business metrics (offer activation rate, redemption rate)

- What alerts should fire?
  a) No new alerts
  b) Error rate threshold
  c) Latency threshold
  d) Business metric anomaly

---

## 10. Accessibility

**TriStar Context:** Tailwind CSS, semantic HTML, ARIA labels required for interactive elements.

- Does this feature add new interactive UI elements?
  a) No UI changes
  b) New form inputs
  c) New buttons/actions
  d) New navigation elements
  e) New data display (tables, charts)

- Are ARIA labels needed for new elements?
  a) No new interactive elements
  b) Yes - describe elements

- Is keyboard navigation supported for new interactions?
  a) No new interactions
  b) Yes - standard form navigation
  c) Yes - custom keyboard shortcuts needed

---

## 11. Testing Strategy

**TriStar Context:** Jest + RTL (frontend), pytest + httpx (backend), Playwright (E2E). Coverage >80%.

- What test types are needed?
  a) Unit tests only
  b) Unit + integration tests
  c) Unit + integration + E2E tests
  d) All test types

- What should be mocked in tests?
  a) Claude API responses
  b) Weather API responses
  c) Redis/Hub state store
  d) Time (freezegun for quiet hours, expiry)
  e) Multiple (specify)

- Are there specific edge cases that need test coverage?
  a) Boundary values (score exactly 60, discount exactly 30%)
  b) Race conditions (concurrent Hub state changes)
  c) Clock-dependent behavior (quiet hours, expiry)
  d) Network failures (API timeouts)

---

## 12. Backward Compatibility

**TriStar Context:** Existing offers in Hub must not be corrupted. API versioning strategy.

- Does this feature change any existing API contracts?
  a) No API changes
  b) Additive changes only (new fields, backward compatible)
  c) Breaking changes (requires API versioning)

- Does this feature affect existing offers in Hub?
  a) No impact on existing offers
  b) Existing offers need migration (describe)
  c) Existing offers may behave differently (describe)

- Is data migration required?
  a) No migration needed
  b) Schema migration (add columns/fields)
  c) Data transformation (existing data must be updated)
  d) State migration (existing Hub states must transition)

---

## 13. Loyalty Domain

**TriStar Context:** Loyalty offer system with fraud detection, rate limiting, and channel-based delivery.

- Does this feature affect offer lifecycle rules?
  a) No lifecycle changes
  b) New approval criteria
  c) New activation rules
  d) New expiry conditions

- Does this feature involve discount calculations?
  a) No discounts
  b) Yes - must enforce <30% threshold (over-discounting flag)
  c) Yes - new discount type (describe)

- What channels does this feature use for delivery?
  a) No notification delivery
  b) Push notification
  c) SMS
  d) Email
  e) Multiple (priority order: Push > SMS > Email)

- Does this feature affect rate limiting?
  a) No rate limiting impact
  b) Must respect 1 notification/member/hour
  c) Must respect 24h dedup for same offer
  d) Must respect quiet hours (10pm-8am)
  e) Multiple constraints apply

- Does this feature interact with fraud detection?
  a) No fraud detection impact
  b) Triggers over-discounting check (>30%)
  c) Triggers cannibalization check
  d) Triggers frequency abuse check (>3 offers/day)
  e) Triggers offer stacking check (>2 concurrent)
  f) Multiple checks apply

- Does this feature introduce new segment targeting criteria?
  a) Uses existing segments
  b) New behavioral segment
  c) New demographic segment
  d) New contextual segment (location, time, weather)

- What context signals does this feature depend on?
  a) No context signals
  b) GPS proximity (<2km)
  c) Time/day patterns
  d) Weather conditions
  e) Member purchase behavior
  f) Multiple signals (describe weighting)
