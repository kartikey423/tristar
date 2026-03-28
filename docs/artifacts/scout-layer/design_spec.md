# Design Specification: scout-layer

## Meta
- **Feature:** scout-layer
- **Date:** 2026-03-28
- **Status:** Draft
- **Author:** TriStar SDLC Pipeline (sdlc-architecture)
- **Problem Spec Reference:** `docs/artifacts/scout-layer/problem_spec.md`
- **Artifact Path:** `docs/artifacts/scout-layer/design_spec.md`

---

## Problem Spec Reference

Builds on the approved problem specification. Key constraints driving design:
- **CON-001** Activation threshold strictly > 60 (not ≥)
- **CON-003** Claude model must be `claude-sonnet-4-6`
- **CON-004** Match endpoint p95 < 2 seconds (Claude call included)
- **CON-005** Rate limit state must survive service restarts (→ Redis required)
- **CON-006** No changes to Hub API contracts or OfferBrief schema
- **CON-008** Scout reads Hub via existing `GET /api/hub/offers?status=active`

---

## Current Architecture

### Existing Scout Infrastructure

The Scout layer already contains significant infrastructure from the purchase-event webhook feature:

| File | Description | Status |
|------|-------------|--------|
| `src/backend/api/scout.py` | `POST /api/scout/purchase-event` webhook | EXISTS — keep, extend |
| `src/backend/services/context_scoring_service.py` | 7-factor deterministic scorer, threshold 70 | EXISTS — becomes fallback |
| `src/backend/services/delivery_constraint_service.py` | In-memory rate limiting (6h limit) | EXISTS — upgrade to Redis |
| `src/backend/services/purchase_event_handler.py` | Concurrent enrichment via asyncio.gather | EXISTS — reuse enrichment pattern |
| `src/backend/services/notification_service.py` | Push with email fallback, 3 retries | EXISTS — keep as-is |
| `src/backend/services/audit_log_service.py` | PII-safe structured logging | EXISTS — extend |
| `src/backend/services/hub_api_client.py` | Hub HTTP client (save/get offers) | EXISTS — extend for active offer fetch |
| `src/backend/models/purchase_event.py` | GeoPoint, PurchaseEventPayload, EnrichedContext | EXISTS — reuse |

### Architectural Divergence From Requirements

The existing flow calls Designer to **generate new offers** on purchase events. The new requirements specify that Scout should **match existing Hub-approved offers** against context signals. These are two distinct patterns:

| Pattern | Existing | New (scout-layer) |
|---------|---------|-------------------|
| Offer source | Designer generates per purchase event | Hub's active offers (marketer-designed) |
| Endpoint | `POST /api/scout/purchase-event` (webhook) | `POST /api/scout/match` (interactive) |
| Scoring | Deterministic 7-factor (threshold 70) | Claude AI (threshold strictly > 60) |
| Rate limiting | In-memory (6h window) | Redis-backed (1h window, survives restart) |
| Context enrichment | asyncio.gather (member history, nearby stores, weather) | Same pattern, extended |

**Resolution:** Add `POST /api/scout/match` as the new primary endpoint. Keep the existing `POST /api/scout/purchase-event` webhook unchanged (backward compatibility). The two flows share the enrichment pattern and will share the upgraded Redis rate limiter.

---

## Architecture

### Component Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (React 19 / Next.js 15)                                        │
│                                                                           │
│  /scout (page.tsx — Server)                                               │
│    ├── ContextDashboard.tsx ('use client') ─── POST /api/scout/match     │
│    └── ActivationFeed.tsx ('use client') ←── activation results          │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP
┌─────────────────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI)                                                        │
│                                                                           │
│  scout.py router                                                          │
│    ├── POST /api/scout/match  ────────────────── [NEW]                   │
│    │     ├── ScoutMatchService (orchestrator)                             │
│    │     │   ├── MockMemberProfileStore         [NEW]                    │
│    │     │   ├── CTCStoreFixtures               [NEW]                    │
│    │     │   ├── WeatherAPI (existing pattern)                            │
│    │     │   ├── HubApiClient.get_active_offers [NEW method]             │
│    │     │   ├── ClaudeContextScoringService    [NEW]                    │
│    │     │   │     └── ContextScoringService (fallback, existing)        │
│    │     │   ├── RedisDeliveryConstraintService [NEW]                    │
│    │     │   └── ScoutAuditService              [NEW]                    │
│    │     │         └── scout_activation_log (SQLite table)               │
│    └── POST /api/scout/purchase-event ──────────── [EXISTING, unchanged] │
└─────────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────────┐
              ▼                                   ▼
┌─────────────────────┐               ┌─────────────────────┐
│  Hub Layer           │               │  Redis               │
│  GET /api/hub/offers │               │  scout:rl:hourly:*   │
│  ?status=active      │               │  scout:rl:dedup:*:*  │
│  HubAuditService     │               │  scout:cache:*       │
└─────────────────────┘               └─────────────────────┘
              │
              ▼
┌─────────────────────┐
│  Claude API          │
│  claude-sonnet-4-6   │
│  3s timeout          │
└─────────────────────┘
```

### Data Flow: `POST /api/scout/match`

```
Client
  │ POST /api/scout/match { member_id, purchase_location, purchase_category,
  │                          rewards_earned, day_context, [weather_condition] }
  ▼
scout.py — match_offers()
  │
  ├─[1] Validate: purchase_location required → 400 if absent
  │
  ├─[2] Check hourly rate limit (Redis key: scout:rl:hourly:{member_id})
  │     └─ HIT → return 429 { "detail": "rate_limited", "retry_after_seconds": N }
  │
  ├─[3] Check quiet hours (22:00–08:00 UTC)
  │     └─ YES → queue and return { "queued": true, "delivery_time": "HH:MM" }
  │
  ├─[4] Concurrent enrichment (asyncio.gather, return_exceptions=True)
  │     ├─ MockMemberProfileStore.get(member_id) → MemberProfile | None
  │     ├─ CTCStoreFixtures.get_nearby(purchase_location, radius_km=2.0) → [NearbyStore]
  │     └─ WeatherAPI.get(purchase_location) → WeatherConditions | None (graceful)
  │
  ├─[5] Fetch active offers: HubApiClient.get_active_offers()
  │     └─ EMPTY → return { "matches": [], "message": "No active offers available" }
  │
  ├─[6] Filter offers by proximity to predicted destination (within 2km)
  │
  ├─[7] For each candidate offer (sorted, highest potential first):
  │     ├─[7a] Check 24h dedup Redis key: scout:rl:dedup:{member_id}:{offer_id}
  │     │      └─ EXISTS → skip this offer, try next
  │     ├─[7b] Check P2 cache: scout:cache:{context_hash}
  │     │      └─ HIT → use cached score, scoring_method = "cached"
  │     ├─[7c] ClaudeContextScoringService.score(context, offer) → {score, rationale, notification_text}
  │     │      └─ TIMEOUT (>3s) → ContextScoringService.score(context) fallback, scoring_method = "fallback"
  │     └─ record best candidate
  │
  ├─[8] Best candidate score > 60?
  │     ├─ YES → activate:
  │     │         Redis SET scout:rl:hourly:{member_id} TTL=3600
  │     │         Redis SET scout:rl:dedup:{member_id}:{offer_id} TTL=86400
  │     │         ScoutAuditService.log_match(outcome="activated", ...)
  │     │         return MatchResponse { outcome: "activated", ... }
  │     └─ NO  → queue:
  │              ScoutAuditService.log_match(outcome="queued", ...)
  │              return MatchResponse { outcome: "queued", ... }
  │
  └─[ALWAYS] ScoutAuditService.log_match() called for every outcome
```

---

## Components

### COMP-001: scout.py route — match endpoint
- **Path:** `src/backend/api/scout.py`
- **Layer:** Scout
- **Action:** MODIFY — add `POST /api/scout/match` route alongside existing `POST /api/scout/purchase-event`
- **Responsibility:** HTTP boundary for interactive Scout match requests. Validate input, delegate to ScoutMatchService, return typed response.
- **Dependencies:** ScoutMatchService (COMP-002 orchestrator), MatchRequest/MatchResponse models (COMP-009)
- **Interface:**
  ```python
  @router.post("/match", response_model=MatchResponse, status_code=200)
  async def match_offers(
      request: MatchRequest,
      service: ScoutMatchService = Depends(get_scout_match_service),
  ) -> MatchResponse: ...
  ```

---

### COMP-002: ScoutMatchService — orchestrator
- **Path:** `src/backend/services/scout_match_service.py`
- **Layer:** Scout
- **Action:** NEW
- **Responsibility:** Orchestrates the full match flow: enrichment → Hub fetch → Claude scoring → rate limit checks → audit. Single entry point for the match use case.
- **Dependencies:** MockMemberProfileStore (COMP-003), CTCStoreFixtures (COMP-004), HubApiClient (existing), ClaudeContextScoringService (COMP-005), RedisDeliveryConstraintService (COMP-006), ScoutAuditService (COMP-007)
- **Interface:**
  ```python
  class ScoutMatchService:
      async def match(self, request: MatchRequest) -> MatchResponse: ...
  ```

---

### COMP-003: MockMemberProfileStore — demo profiles
- **Path:** `src/backend/services/mock_member_profile_store.py`
- **Layer:** Scout
- **Action:** NEW
- **Responsibility:** Returns hardcoded behavioral profiles for the 5 demo members. For unknown member IDs, returns `None` (graceful degradation per REQ-004).
- **Dependencies:** None (pure data, no I/O)
- **Interface:**
  ```python
  class MockMemberProfileStore:
      def get(self, member_id: str) -> Optional[MemberProfile]: ...
  ```
- **Mock profiles:**

  | member_id | Profile | Behavior |
  |-----------|---------|----------|
  | demo-001 | Frequent outdoor/sporting goods buyer near CTC stores | purchase_count_90_days=12, preferred_categories=["outdoor","sporting_goods"], last_ctc_purchase_days_ago=3, loyalty_tier="gold" |
  | demo-002 | Urban commuter, Tim Hortons daily, moderate CTC shopper | purchase_count_90_days=6, preferred_categories=["food_beverage","apparel"], last_ctc_purchase_days_ago=14, loyalty_tier="silver" |
  | demo-003 | Seasonal buyer, hardware and home garden focus | purchase_count_90_days=3, preferred_categories=["hardware","home_garden"], last_ctc_purchase_days_ago=30, loyalty_tier="standard" |
  | demo-004 | Family shopper, broad categories, high spend | purchase_count_90_days=8, preferred_categories=["outdoor","electronics","apparel"], last_ctc_purchase_days_ago=7, loyalty_tier="platinum" |
  | demo-005 | Auto parts buyer, suburban location, low CTC engagement | purchase_count_90_days=2, preferred_categories=["automotive"], last_ctc_purchase_days_ago=45, loyalty_tier="standard" |

---

### COMP-004: CTCStoreFixtures — nearby store lookup
- **Path:** `src/backend/services/ctc_store_fixtures.py`
- **Layer:** Scout
- **Action:** NEW
- **Responsibility:** Provides hardcoded CTC store coordinates for nearby-store lookup using Haversine distance calculation. Returns stores within the requested radius, sorted by distance.
- **Dependencies:** None (pure data + math)
- **Interface:**
  ```python
  class CTCStoreFixtures:
      def get_nearby(self, location: GeoPoint, radius_km: float = 2.0) -> list[NearbyStore]: ...
  ```
- **Store fixtures (8 demo locations):** Canadian Tire Queen St W, Canadian Tire Yonge & Eglinton, Sport Chek Eaton Centre, Sport Chek Yorkdale, Canadian Tire Mississauga, Marks on King St, Canadian Tire Scarborough, Sport Chek Square One

---

### COMP-005: ClaudeContextScoringService — AI scorer
- **Path:** `src/backend/services/claude_context_scoring_service.py`
- **Layer:** Scout
- **Action:** NEW
- **Responsibility:** Primary scoring engine. Builds a structured prompt containing all available context signals + offer details. Submits to `claude-sonnet-4-6`. Parses JSON response: `{score, rationale, notification_text}`. Falls back to existing `ContextScoringService` if Claude times out (> 3s) or returns invalid JSON.
- **Dependencies:** ClaudeApiService (existing), ContextScoringService (existing — fallback), MatchRequest models
- **Interface:**
  ```python
  @dataclass
  class ClaudeScoreResult:
      score: float                    # 0-100
      rationale: str                  # natural language
      notification_text: str          # push notification copy
      scoring_method: ScoringMethod   # "claude" | "fallback" | "cached"

  class ClaudeContextScoringService:
      async def score(
          self,
          context: EnrichedMatchContext,
          offer: OfferBrief,
      ) -> ClaudeScoreResult: ...

      def _build_prompt(
          self,
          context: EnrichedMatchContext,
          offer: OfferBrief,
      ) -> str: ...

      def _parse_response(self, response_text: str) -> ClaudeScoreResult: ...
  ```

**Claude prompt structure:**
```
You are the TriStar Scout activation engine. Score how well this CTC offer matches
the member's current context. Return ONLY valid JSON with exactly these fields:
{"score": <0-100>, "rationale": "<2-3 sentences>", "notification_text": "<push notification copy>"}

## Context Signals
- Purchase just made: {category} at {store_name} (+{rewards_earned} Triangle points)
- Predicted intent: Member likely heading to {predicted_destination_area}
- Day context: {day_context}
- Time: {hour}:00 {timezone}
- Nearest CTC store: {store_name} ({distance_km}km away)
- Weather: {condition} ({temperature_c}°C)
- Member behavioral profile: {preferred_categories}, {purchase_count_90_days} CTC purchases in 90 days
  [OMIT member profile section if not available — note: no behavioral data]
  [OMIT weather section if not available — note: weather signal absent, reduced confidence]

## Candidate Offer
- Offer ID: {offer_id}
- Description: {offer_description}
- Value: {construct_type} — {construct_value}
- Target segment: {segment_name}
- Store: {store_name} ({distance_to_offer_store_km}km from member)

## Scoring Criteria
Score 0-100 based on: relevance to predicted next destination, contextual fit with purchase just made,
member behavioral alignment, timing appropriateness.
Score exactly 60 or below = NOT activated. Score 61+ = activated.

## Notification Text Format
"[Rewards hook] — [Offer] at [Store], [Distance]. [Savings claim]."
Example: "You earned 120 Triangle points at Tim Hortons — 20% off Outdoor gear at Canadian Tire 400m away. Save 15% vs Amazon."
```

**Fallback trigger conditions:**
- Claude API timeout (> 3 seconds)
- Claude returns non-JSON or JSON missing required fields
- `CLAUDE_API_KEY` is empty (dev/test without key)

---

### COMP-006: RedisDeliveryConstraintService — Redis rate limiter
- **Path:** `src/backend/services/delivery_constraint_service.py`
- **Layer:** Scout
- **Action:** MODIFY — add `RedisDeliveryConstraintService` class. Keep existing `DeliveryConstraintService` (in-memory) for tests and `HUB_REDIS_ENABLED=False` fallback.
- **Responsibility:** Enforces the three rate limits using Redis atomic operations with TTL-managed keys. Survives process restarts (CON-005).
- **Dependencies:** redis.asyncio (already in requirements for Hub)
- **Interface:**
  ```python
  class RedisDeliveryConstraintService:
      def __init__(self, redis_url: str) -> None: ...

      async def check_hourly_limit(self, member_id: str) -> tuple[bool, int]:
          """Returns (can_proceed, retry_after_seconds)."""

      async def check_dedup(self, member_id: str, offer_id: str) -> bool:
          """Returns True if offer was already activated within 24h."""

      async def check_quiet_hours(self) -> tuple[bool, str]:
          """Returns (is_quiet, delivery_time_hhmm)."""

      async def record_activation(self, member_id: str, offer_id: str) -> None:
          """Atomically set hourly + dedup keys after activation."""
  ```
- **Redis key design:**

  | Key | TTL | Purpose |
  |-----|-----|---------|
  | `scout:rl:hourly:{member_id}` | 3600s (1 hour) | Hourly rate limit per member |
  | `scout:rl:dedup:{member_id}:{offer_id}` | 86400s (24 hours) | 24h offer dedup per member |
  | `scout:cache:{context_hash}` | 300s (5 min) | P2: score cache for identical context+offer |

  **Note:** Key set atomically via `SET NX PX <ttl_ms>` — no race condition on concurrent requests.

---

### COMP-007: ScoutAuditService — activation audit log
- **Path:** `src/backend/services/scout_audit_service.py`
- **Layer:** Scout
- **Action:** NEW
- **Responsibility:** Writes every match outcome to a persistent `scout_activation_log` SQLite table. Contains all fields required by AC-015/AC-016/AC-017. GPS coordinates are never stored.
- **Dependencies:** aiosqlite (already in requirements), sqlite3 (stdlib)
- **Interface:**
  ```python
  @dataclass
  class ScoutActivationRecord:
      member_id: str
      offer_id: str
      score: float
      rationale: str
      scoring_method: str    # "claude" | "fallback" | "cached"
      outcome: str           # "activated" | "queued" | "rate_limited" | "error"
      timestamp: str         # ISO 8601

  class ScoutAuditService:
      def __init__(self, database_url: str) -> None: ...
      async def log_match(self, record: ScoutActivationRecord) -> None: ...
  ```
- **Schema:**
  ```sql
  CREATE TABLE IF NOT EXISTS scout_activation_log (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      member_id       VARCHAR(100) NOT NULL,
      offer_id        VARCHAR(36)  NOT NULL,
      score           REAL         NOT NULL,
      rationale       TEXT,
      scoring_method  VARCHAR(20)  NOT NULL,
      outcome         VARCHAR(20)  NOT NULL,
      timestamp       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
      -- NO lat/lon columns ever (CON-002 / AC-017)
  );
  ```

---

### COMP-008: Scout match models
- **Path:** `src/backend/models/scout_match.py`
- **Layer:** Scout (Shared)
- **Action:** NEW
- **Responsibility:** Pydantic v2 request/response models for `POST /api/scout/match`. No changes to existing OfferBrief schema (CON-006).

---

### COMP-009: deps.py additions
- **Path:** `src/backend/api/deps.py`
- **Layer:** Scout
- **Action:** MODIFY — add `get_scout_match_service()`, `get_redis_delivery_service()`, `get_scout_audit_service()`, `get_claude_context_scoring_service()`
- All new DI factories use `@lru_cache(maxsize=1)` pattern (existing convention).

---

### COMP-010: config.py additions
- **Path:** `src/backend/core/config.py`
- **Layer:** Shared
- **Action:** MODIFY — add `SCOUT_ENABLED: bool = True` feature flag. Note: existing `PURCHASE_TRIGGER_SCORE_THRESHOLD = 70.0` stays unchanged (used by purchase-event webhook). New match endpoint uses hard-coded threshold of 60 per CON-001.

---

### COMP-011: Scout page
- **Path:** `src/frontend/app/scout/page.tsx`
- **Layer:** Scout Frontend
- **Action:** NEW (Server Component)
- **Responsibility:** Scout page shell. Exports metadata. Renders `<ContextDashboard />` inside a Suspense boundary.

---

### COMP-012: ContextDashboard component
- **Path:** `src/frontend/components/Scout/ContextDashboard.tsx`
- **Layer:** Scout Frontend
- **Action:** NEW (`'use client'`)
- **Responsibility:** Interactive simulation UI. Member profile selector (5 demo profiles), CTC store location preset selector, weather preset selector, day context selector, "Simulate Purchase" button. On submit calls `POST /api/scout/match`. Passes result to `<ActivationFeed />`.
- **Props:** None (self-contained with internal state)
- **State:** `selectedMember`, `selectedStore`, `weatherPreset`, `dayContext`, `feedItems[]`, `loading`, `error`

---

### COMP-013: ActivationFeed component
- **Path:** `src/frontend/components/Scout/ActivationFeed.tsx`
- **Layer:** Scout Frontend
- **Action:** NEW (`'use client'`)
- **Responsibility:** Renders the list of activation results. Each entry displays: offer title, Claude score (0–100 badge), Claude rationale, notification preview text, outcome badge (activated / queued / rate_limited), scoring method badge.
- **Props:** `items: ActivationFeedItem[]`

---

## API Contracts

### `POST /api/scout/match`

**Request model (`MatchRequest`):**
```python
class MatchRequest(BaseModel):
    member_id: str = Field(..., min_length=1, max_length=100)
    purchase_location: GeoPoint  # required — AC-007: 400 if absent
    purchase_category: str = Field(default="general", min_length=1, max_length=50)
    rewards_earned: int = Field(default=0, ge=0)
    day_context: Literal["weekday", "weekend", "long_weekend"] = "weekday"
    weather_condition: Optional[str] = None  # omit → API call; "unknown" → skip
```

**Response model (`MatchResponse`):**
```python
class MatchResponse(BaseModel):
    score: float = Field(..., ge=0, le=100)
    rationale: str
    notification_text: str
    offer_id: str
    outcome: Literal["activated", "queued", "rate_limited"]
    scoring_method: Literal["claude", "fallback", "cached"]
    queued: Optional[bool] = None       # present when outcome=queued
    delivery_time: Optional[str] = None # "HH:MM" next day, present when queued=True
    retry_after_seconds: Optional[int] = None  # present when outcome=rate_limited

class NoMatchResponse(BaseModel):
    matches: list = []
    message: str
```

**Status codes:**
| Code | Condition |
|------|-----------|
| 200 | Match result (activated / queued / rate_limited) or no-match |
| 400 | `purchase_location` absent → `{ "detail": "location signal required for activation" }` |
| 429 | Hourly rate limit exceeded → `{ "detail": "rate_limited", "retry_after_seconds": N }` |

**Note on 429 vs 200 with outcome=rate_limited:** Hourly member limit returns HTTP 429 (AC-008). Per-offer 24h dedup is handled silently by skipping that offer and evaluating the next candidate — it does NOT return 429 (AC-009: "no 429 — dedup is per-offer, not per-member").

---

### `GET /api/hub/offers?status=active` (existing Hub endpoint, consumed read-only)

No changes to this contract per CON-006/CON-008.

---

## Data Models

### New: `MatchRequest` / `MatchResponse` / `NoMatchResponse`
Defined in `src/backend/models/scout_match.py`. See API Contracts above.

### New: `EnrichedMatchContext`
Internal model used within `ScoutMatchService` — never serialized to API response.
```python
class EnrichedMatchContext(BaseModel):
    request: MatchRequest
    member: Optional[MemberProfile]          # None if unknown member_id
    nearby_stores: list[NearbyStore]         # empty list if none within 2km
    weather: Optional[WeatherConditions]     # None if API unavailable (graceful)
    enrichment_partial: bool = False         # True if any signal was absent
    absent_signals: list[str] = []           # e.g., ["weather", "behavioral_profile"]
```

### New: `ScoutActivationRecord`
Internal model for audit persistence. Defined in `scout_audit_service.py`.

### No changes to: `OfferBrief`, `GeoPoint`, `MemberProfile`, `NearbyStore`, `WeatherConditions`, `EnrichedContext`
All existing models are reused unchanged (CON-006).

---

## Architecture Decision Records

### ADR-001: Claude AI as Primary Scoring Engine

**Status:** Decided

**Context:**
The existing `ContextScoringService` uses a 7-factor deterministic formula. The hackathon demo goal is to make AI presence visible at the activation moment. The requirements explicitly state Claude must be the primary scoring engine (REQ-001).

**Alternatives Considered:**

**Alt A: Pure deterministic (keep existing ContextScoringService)**
- Pros: Zero latency overhead, no Claude cost, fully predictable
- Cons: No AI differentiation — Scout becomes indistinguishable from a rules engine. No natural-language rationale. No personalized notification copy. Undermines the hackathon AI narrative.

**Alt B: Claude primary + deterministic fallback (chosen)**
- Pros: AI is the visible intelligence layer. Claude generates natural-language rationale and personalized notification text — two demo differentiators not possible with rules. Deterministic fallback (AC-004) guarantees activation continues even if Claude is unavailable.
- Cons: Adds ~1.0–1.5s latency per Claude call. API cost per match. Dependency on external service.

**Alt C: Hybrid re-ranking (deterministic shortlist → Claude re-ranks top N)**
- Pros: Cheaper per call (Claude sees fewer candidates). Deterministic first-pass filters obviously poor matches.
- Cons: Claude is not the primary intelligence — it merely re-orders a pre-filtered list. Demo narrative is weakened ("AI ranks offers" vs "AI reads context and decides"). More complex pipeline.

**Decision:** Alt B. Claude is the primary scoring engine. The 3-second timeout with deterministic fallback (AC-004) satisfies CON-004 (p95 < 2s target — Claude p95 is ~1.2s for this prompt size per ASM-001).

**Consequences:**
- New `ClaudeContextScoringService` wraps existing `ContextScoringService` as fallback
- Prompt design must be deterministic to enable reliable demo outcomes
- `scoring_method` field in audit log captures which engine was used

---

### ADR-002: Hub-Matching Flow via New `/api/scout/match` Endpoint

**Status:** Decided

**Context:**
The existing `POST /api/scout/purchase-event` webhook calls Designer to generate a new offer per purchase event. The requirements specify Scout should match against Hub's existing active offers — the ones marketers designed via the Designer layer. These are fundamentally different patterns.

**Alternatives Considered:**

**Alt A: Modify existing purchase-event webhook to use Hub offers**
- Pros: Single endpoint, no API surface change.
- Cons: Breaking change to existing webhook behavior. The webhook is asynchronous (202 Accepted); the match flow is synchronous (needs score+rationale in response). Different response contracts. High risk of regressions in the existing purchase-event flow.

**Alt B: Add new `POST /api/scout/match` endpoint, keep webhook unchanged (chosen)**
- Pros: Zero regression risk on existing webhook. New endpoint has a synchronous response contract that enables the ContextDashboard UI. Clean separation of concerns: webhook = reactive trigger, match = interactive demo. Hub offers are the offer source of truth.
- Cons: Two endpoints that partially share logic (enrichment, rate limiting). Must share the Redis rate limiter to avoid double-counting activations across both flows.

**Alt C: Hybrid — check Hub first, fall back to Designer generation**
- Pros: Works even if Hub is empty.
- Cons: Complex conditional flow. Undermines Hub as the single source of truth for approved offers. Two different offer schemas may be returned from the same endpoint.

**Decision:** Alt B. The new `POST /api/scout/match` endpoint is added to `scout.py` alongside the existing webhook. Both flows share `RedisDeliveryConstraintService` for rate limiting.

**Consequences:**
- Existing `POST /api/scout/purchase-event` untouched — zero risk to current tests
- New endpoint has synchronous 200 response with score, rationale, notification_text
- `HubApiClient` gains `get_active_offers()` method
- Both endpoints share `RedisDeliveryConstraintService`

---

### ADR-003: Redis-Backed Rate Limiting

**Status:** Decided

**Context:**
The existing `DeliveryConstraintService` uses an in-memory `dict`. This violates CON-005 (rate limit state must survive restarts) and AC-011.

**Alternatives Considered:**

**Alt A: Keep in-memory (existing DeliveryConstraintService)**
- Pros: No Redis dependency, no infrastructure change, simple.
- Cons: State lost on every restart. Multi-instance deployments have independent rate limit windows — a member can bypass limits by hitting a different instance. Violates CON-005 and AC-011.

**Alt B: Redis-backed via `SET NX PX <ttl>` (chosen)**
- Pros: Survives restarts. Multi-instance safe. TTL-managed keys — no sweep job needed. Redis already required for Hub (`HUB_REDIS_ENABLED`). `SET NX` is atomic — no race conditions.
- Cons: Adds Redis dependency to Scout flow (already present in infra). Redis unavailability must be handled gracefully (fail-open: allow activation if Redis is down, log warning).

**Alt C: SQLite-backed via `scout_activation_log` with sweep job**
- Pros: Persistent without Redis. Works in dev without Redis.
- Cons: SQLite does not support TTL — requires a background sweep job. Concurrent writes to SQLite are serialized. Slower than Redis. Complexity outweighs benefit when Redis is already required.

**Decision:** Alt B. `RedisDeliveryConstraintService` uses `SET NX PX` for atomic, TTL-managed rate limit keys. The existing in-memory `DeliveryConstraintService` is kept for tests and the `HUB_REDIS_ENABLED=False` code path.

**Consequences:**
- New `RedisDeliveryConstraintService` class added to `delivery_constraint_service.py`
- `deps.py` returns `RedisDeliveryConstraintService` when `HUB_REDIS_ENABLED=True`, else existing in-memory service
- Redis unavailability: fail-open (log warning, allow activation) — no member-facing error

---

## Implementation Guidelines

Reference:
- `.claude/rules/fastapi-standards.md` — async/await, Pydantic v2, `@lru_cache` DI
- `.claude/rules/react-19-standards.md` — Server Components default, `'use client'` only for interactivity
- `.claude/rules/security.md` — PII handling: GPS never logged, member_id only
- `.claude/rules/testing.md` — pytest + httpx, coverage > 80%, freeze_time for quiet hours tests

**Critical implementation notes:**

1. **Claude response parsing must be defensive.** Use `try/except` around JSON parsing. If Claude returns malformed JSON, fall back to deterministic scorer — never raise a 500.

2. **GPS coordinates must never be logged or stored.** The `EnrichedMatchContext`, `ClaudeScoreResult`, and `ScoutActivationRecord` models must not contain lat/lon fields. Only `store_id`, `store_name`, `distance_km` are permitted.

3. **`asyncio.gather(return_exceptions=True)` for enrichment.** Missing enrichment signals do not block scoring — they result in `absent_signals` being populated and the prompt being adjusted. GPS location is the only required field (returning 400 if absent).

4. **Claude timeout = 3 seconds.** Use `httpx.AsyncClient(timeout=3.0)` for Claude calls. Do NOT reuse the existing 30s timeout in the purchase-event handler.

5. **Quiet hours check precedes scoring.** Check quiet hours before making any Claude API calls to avoid wasted API cost during 22:00–08:00 window.

6. **Score exactly 60 does NOT activate.** Threshold is strictly `> 60` per CON-001. The existing `ContextScoringService.score()` uses `>=` — the new `ClaudeContextScoringService` must use `>`.

7. **`RedisDeliveryConstraintService.record_activation()` is atomic.** Set both keys in a single Redis pipeline to prevent partial state.

---

## Testing Strategy

### Backend unit tests (pytest)
| File | Tests |
|------|-------|
| `tests/unit/backend/services/test_claude_context_scoring_service.py` | Claude score parsing, fallback on timeout, fallback on malformed JSON, prompt includes absent signals |
| `tests/unit/backend/services/test_redis_delivery_constraint_service.py` | Hourly limit blocks second call, dedup blocks same offer, quiet hours returns correct delivery_time, record_activation sets both keys |
| `tests/unit/backend/services/test_mock_member_profile_store.py` | All 5 profiles return correct data, unknown member_id returns None |
| `tests/unit/backend/services/test_ctc_store_fixtures.py` | Stores within radius returned sorted by distance, stores outside radius excluded, EC-005 (exactly 2km = excluded) |
| `tests/unit/backend/services/test_scout_match_service.py` | Full flow mocked: activation, queued, rate_limited, quiet hours, no offers, missing location 400 |

### Backend integration tests
| File | Tests |
|------|-------|
| `tests/integration/backend/api/test_scout_match_api.py` | `POST /api/scout/match` with real httpx TestClient, mocked Claude + Redis + Hub |

### Key edge case tests (from problem spec)
| EC | Test approach |
|----|---------------|
| EC-001 No offers | Mock `HubApiClient.get_active_offers()` → `[]`, assert 200 `{"matches":[], "message":...}` |
| EC-003 Score exactly 60 | Mock Claude returns score=60, assert outcome="queued" |
| EC-004 Claude timeout | Mock timeout in 3.1s, assert `scoring_method="fallback"` |
| EC-007 Request at 22:00 | `freeze_time("2026-01-01 22:00:00")`, assert `queued=True, delivery_time="08:00"` |
| EC-008 Request at 08:00 | `freeze_time("2026-01-01 08:00:00")`, assert activation proceeds |
| EC-009 59 min after hourly limit | Mock Redis key TTL=60, assert 429 `retry_after_seconds=60` |

### Frontend unit tests (Jest + React Testing Library)
| File | Tests |
|------|-------|
| `tests/unit/frontend/components/Scout/ContextDashboard.test.tsx` | Profile dropdown renders 5 members, submit calls API, loading state shown, error displayed |
| `tests/unit/frontend/components/Scout/ActivationFeed.test.tsx` | Activated/queued/rate_limited badges render, notification text visible, score displayed |

### Coverage target: ≥ 80% for all new Scout files

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| GPS coordinates in logs (CON-002, AC-017) | `EnrichedMatchContext` contains `GeoPoint` only transiently; `ScoutActivationRecord` schema has no lat/lon columns. `AuditLogService` pattern of logging only store_id/store_name is followed in `ScoutAuditService`. |
| Claude prompt injection via purchase_category | `purchase_category` validated by Pydantic `max_length=50`, no special characters. Prompt treats it as a quoted string value, not executable. |
| Member ID enumeration via rate limit | 429 response includes `retry_after_seconds` but no member-specific data. Same behavior for valid and invalid member_ids (no oracle). |
| Redis key collision | Keys namespaced `scout:rl:*` — no overlap with Hub's Redis keys (`hub:*`). |
| Claude API key exposure | Key loaded from `settings.CLAUDE_API_KEY` (env var / Azure Key Vault). Never in logs or API responses. |
| CORS | Existing CORS config covers `/api/scout/match` — no change needed. |

---

## Backward Compatibility

**Verdict: Fully compatible.**

- `POST /api/scout/purchase-event` — **unchanged**. Existing webhook logic, signature verification, and response format are not modified.
- `ContextScoringService` — **unchanged**. Used as fallback by `ClaudeContextScoringService`. Existing tests continue to pass.
- `DeliveryConstraintService` (in-memory) — **unchanged class**. New `RedisDeliveryConstraintService` is a separate class. DI selects based on `HUB_REDIS_ENABLED`.
- `OfferBrief` schema — **no changes** (CON-006).
- Hub API contracts — **no changes** (CON-008). Scout only reads `GET /api/hub/offers?status=active`.
- `HubAuditService` / `hub_audit_log` table — **not used by Scout**. Scout uses new `scout_activation_log` table via `ScoutAuditService`.

---

## Quality Gates

| Gate | Status | Notes |
|------|--------|-------|
| 1: Completeness (all requirements addressed) | ✅ PASS | REQ-001 → COMP-005, REQ-002 → COMP-002, REQ-003 → COMP-006, REQ-004 → COMP-005 prompt, REQ-005 → COMP-007, REQ-006 → COMP-005 notification_text, REQ-007 → COMP-011/012/013, REQ-008 → COMP-003 |
| 2: Architecture quality (ADRs, 3-layer separation) | ✅ PASS | 3 ADRs with 2+ alternatives. Designer→Scout bypass absent. Scout reads Hub, does not call Designer. |
| 3: Backward compatibility | ✅ PASS | Existing purchase-event webhook unchanged. OfferBrief unchanged. Hub API unchanged. |
| 4: Hub state integrity | ✅ PASS | Scout reads Hub offers read-only. No Hub state mutations. |
| 5: Security (PII, OWASP, Azure Key Vault) | ✅ PASS | GPS never in logs. Claude key in env/Key Vault. Pydantic validation on all inputs. |
| 6: Testing (coverage target, strategy per layer) | ✅ PASS | 80% coverage target. Unit + integration + edge cases defined for all new components. |
| 7: OfferBrief contract unchanged | ✅ PASS | New models in scout_match.py. No OfferBrief fields added/removed/changed. |
