# Design Specification — partner-triggers-and-rewards

## Meta

| Field | Value |
|-------|-------|
| Feature | partner-triggers-and-rewards |
| Author | SDLC Architecture Skill |
| Date | 2026-04-03 |
| Status | Proposed |
| Problem Spec | docs/artifacts/partner-triggers-and-rewards/problem_spec.md |
| Branch | feat/partner-triggers-and-rewards |

---

## Problem Spec Reference

Addresses all 12 requirements from problem_spec.md (R-01 through R-12) and all 14 acceptance criteria (AC-01 through AC-14).

---

## Current Architecture

### Relevant Existing Components

| Component | Path | Notes |
|-----------|------|-------|
| `OfferBrief` model | `src/backend/models/offer_brief.py` | Has `TriggerType` enum (`marketer_initiated`, `purchase_triggered`). `Construct` model needs `payment_split`. |
| `TriggerType` enum | `src/backend/models/offer_brief.py:L13` | Needs new `partner_triggered` value |
| Scout API router | `src/backend/api/scout.py` | Has `_verify_webhook_signature()` HMAC helper — reusable for partner-trigger endpoint |
| `ScoutMatchService` | `src/backend/services/scout_match_service.py` | Orchestrates match pipeline; needs redemption enforcement hook |
| `DealScraperService` | `src/backend/services/deal_scraper_service.py` | Hard cap at 15/source in `_scrape_source()` L172; frontend calls `getInventorySuggestions(6)` |
| `AISuggestionsPanel` | `src/frontend/components/Designer/AISuggestionsPanel.tsx` | Calls `getInventorySuggestions(6)` — hardcoded limit |
| `InventorySuggestionCard` | `src/frontend/components/Designer/InventorySuggestionCard.tsx` | "Generate Offer" button calls `prefillObjectiveAction` — no duplicate guard |
| `ManualEntryForm` | `src/frontend/components/Designer/ManualEntryForm.tsx` | No dirty-flag tracking; controlled textarea only |
| `HubStore` | `src/backend/services/hub_store.py` | `save_offer()` is the write interface for partner offers |
| HMAC verification | `src/backend/api/scout.py:_verify_webhook_signature()` | Reuse for partner-trigger auth |

### Current Data Flow (Scout Activation)
```
PurchaseEvent → ScoutAPI → PurchaseEventHandler → ContextScoring → HubApiClient → DeliveryConstraints → Notification
```

### Current Data Flow Gap (Partner Trigger)
```
PartnerPurchaseEvent → [NO HANDLER] → [NO CLASSIFICATION] → [NO OFFER CREATION]
```

---

## Architecture

### New Components Overview

```
Layer 1 (Designer):
  AISuggestionsPanel ──→ getInventorySuggestions(no limit) [MODIFIED]
  InventorySuggestionCard ──→ offeredProductIds prop + disabled guard [MODIFIED]
  ManualEntryForm ──→ marketer_overridden dirty flag state [MODIFIED]

Layer 2 (Hub):
  HubStore.save_offer() ──→ auto-active partner offers [REUSED]

Layer 3 (Scout):
  POST /api/scout/partner-trigger [NEW endpoint]
  PartnerTriggerService [NEW service]
  RedemptionEnforcementService [NEW service]
  OfferBrief.Construct.payment_split [NEW field]
  TriggerType.partner_triggered [NEW enum value]
```

### Partner-Trigger Pipeline (New)

```
POST /api/scout/partner-trigger
  │
  ├─ HMAC verify (reuse _verify_webhook_signature)
  ├─ Pydantic validate PartnerPurchaseEvent
  ├─ Dedup check (event_id, 60s window)
  │
  ├─ PartnerTriggerService.classify_and_generate()
  │    ├─ Haiku: classify partner context → CTC product category
  │    ├─ On Haiku failure: fallback template for partner
  │    └─ Sonnet: generate full OfferBrief for predicted category
  │
  ├─ Set offer: status=active, trigger_type=partner_triggered,
  │             valid_until=now+24h, payment_split={75, 25}
  │
  └─ HubStore.save_offer(offer)  →  Hub contains active offer
       └─ return HTTP 202
```

### Redemption Enforcement (New)

```
Scout activation pipeline:
  ScoutMatchService.match()
    └─ [AFTER scoring, BEFORE notification dispatch]
         └─ RedemptionEnforcementService.validate_payment_split(offer, redemption_request)
              ├─ If payment_split absent → pass (backward compat)
              ├─ If points_pct > points_max_pct → raise RedemptionSplitError (422)
              └─ If valid → continue to notification
```

---

## API Contracts

### COMP-001 — `POST /api/scout/partner-trigger`

**Request model:** `PartnerPurchaseEvent`
```python
class PartnerPurchaseEvent(BaseModel):
    event_id: str = Field(..., description="Unique event ID for deduplication")
    partner_id: str = Field(..., description="Partner identifier e.g. 'tim_hortons'")
    partner_name: str = Field(..., min_length=1, max_length=100)
    purchase_amount: float = Field(..., ge=0)
    purchase_category: str = Field(..., description="Partner-side category e.g. 'coffee', 'food'")
    member_id: str = Field(..., description="Triangle member ID")
    timestamp: datetime
```

**Response model:** `PartnerTriggerResponse`
```python
class PartnerTriggerResponse(BaseModel):
    status: str  # "accepted" | "duplicate"
    offer_id: Optional[str]  # set if offer was created
    message: str
```

**Status codes:**
- `202 Accepted` — event processed, offer created/queued
- `400 Bad Request` — invalid payload or duplicate event_id
- `401 Unauthorized` — HMAC signature missing or invalid

**Auth:** `X-Webhook-Signature: sha256=<hmac>` using `SCOUT_WEBHOOK_SECRET`

---

### COMP-002 — Redemption Validation (Internal)

Not a new HTTP endpoint. Called internally within `ScoutMatchService` before notification dispatch.

```python
class RedemptionRequest(BaseModel):
    offer_id: str
    points_pct: float = Field(..., ge=0, le=100,
        description="Percentage of offer value to be paid in points (0-100)")
    cash_pct: float = Field(..., ge=0, le=100)

    @model_validator(mode="after")
    def validate_sum(self) -> "RedemptionRequest":
        if abs((self.points_pct + self.cash_pct) - 100.0) > 0.01:
            raise ValueError("points_pct + cash_pct must equal 100")
        return self
```

**Enforcement:** If `offer.construct.payment_split` is set:
- `points_pct > payment_split.points_max_pct` → raise `RedemptionSplitError`
- Returns `HTTP 422` with `detail: "Points redemption exceeds 75% maximum. Cash payment required for remaining 25%."`

---

## Data Models

### Modified: `OfferBrief.Construct` — add `payment_split`

```python
class PaymentSplit(BaseModel):
    """Triangle Rewards payment split constraint."""
    points_max_pct: float = Field(75.0, ge=0, le=100,
        description="Maximum percentage of offer value payable in points")
    cash_min_pct: float = Field(25.0, ge=0, le=100,
        description="Minimum percentage payable via credit/debit")

    @model_validator(mode="after")
    def validate_split(self) -> "PaymentSplit":
        if abs((self.points_max_pct + self.cash_min_pct) - 100.0) > 0.01:
            raise ValueError("points_max_pct + cash_min_pct must equal 100")
        return self


class Construct(BaseModel):
    type: str = Field(..., min_length=1)
    value: float = Field(..., ge=0)
    description: str = Field(..., min_length=1)
    payment_split: Optional[PaymentSplit] = None  # NEW — optional for backward compat
```

### Modified: `TriggerType` enum — add `partner_triggered`

```python
class TriggerType(str, Enum):
    marketer_initiated = "marketer_initiated"
    purchase_triggered = "purchase_triggered"
    partner_triggered = "partner_triggered"   # NEW
```

### New: `PartnerPurchaseEvent` model

File: `src/backend/models/partner_event.py` (new file)

```python
class PartnerPurchaseEvent(BaseModel): ...  # see API contract above

class PartnerTriggerResponse(BaseModel): ...

class RedemptionRequest(BaseModel): ...

class RedemptionSplitError(Exception):
    def __init__(self, points_pct: float, max_pct: float):
        self.points_pct = points_pct
        self.max_pct = max_pct
```

### Frontend: `InventorySuggestionCard` prop change

```typescript
interface InventorySuggestionCardProps {
  suggestion: InventorySuggestion;
  isOffered: boolean;  // NEW — true if offer already generated for this product_id
}
```

---

## Component Definitions

### COMP-001 — Partner Trigger API Endpoint
- **Path:** `src/backend/api/scout.py` (add route to existing router)
- **Layer:** Scout (Layer 3)
- **Responsibility:** Receive, authenticate, deduplicate, and dispatch partner purchase events
- **Dependencies:** `PartnerTriggerService`, `_verify_webhook_signature()` (existing)
- **Interface:** `POST /api/scout/partner-trigger` — see API contract

### COMP-002 — `PartnerTriggerService`
- **Path:** `src/backend/services/partner_trigger_service.py` (new file)
- **Layer:** Scout (Layer 3)
- **Responsibility:** Classify partner purchase context via Haiku, generate OfferBrief via Sonnet, save to Hub
- **Dependencies:** `anthropic.Anthropic`, `HubApiClient`, `claude_api.py`
- **Interface:**
  ```python
  async def classify_and_generate(event: PartnerPurchaseEvent) -> OfferBrief
  async def _classify_with_haiku(event: PartnerPurchaseEvent) -> str  # returns CTC category
  async def _fallback_category(partner_id: str) -> str  # fallback on Haiku failure
  async def _generate_offer(member_id: str, category: str, partner_name: str) -> OfferBrief
  ```

### COMP-003 — Partner Fallback Templates
- **Path:** `src/backend/services/partner_trigger_service.py` (inline dict)
- **Layer:** Scout (Layer 3)
- **Responsibility:** Provide generic CTC offer objectives per partner when Haiku fails
- **Interface:**
  ```python
  _PARTNER_FALLBACK_CATEGORIES: dict[str, str] = {
      "tim_hortons": "automotive_accessories",
      "westjet": "travel_accessories",
      "sport_chek": "outdoor_camping",
      "default": "seasonal_promotions",
  }
  ```

### COMP-004 — `RedemptionEnforcementService`
- **Path:** `src/backend/services/redemption_enforcement_service.py` (new file)
- **Layer:** Scout (Layer 3)
- **Responsibility:** Validate Triangle Rewards payment split against offer constraints
- **Dependencies:** `OfferBrief`, `PaymentSplit`, `RedemptionRequest`
- **Interface:**
  ```python
  def validate_payment_split(offer: OfferBrief, redemption: RedemptionRequest) -> None
  # Raises RedemptionSplitError if violation detected
  ```

### COMP-005 — `PartnerPurchaseEvent` Pydantic Model
- **Path:** `src/backend/models/partner_event.py` (new file)
- **Layer:** Shared models
- **Responsibility:** Request/response models for partner trigger endpoint

### COMP-006 — `PaymentSplit` Pydantic Model
- **Path:** `src/backend/models/offer_brief.py` (add to existing)
- **Layer:** Shared models
- **Responsibility:** Encode and validate the 75/25 payment constraint

### COMP-007 — `AISuggestionsPanel` (modified)
- **Path:** `src/frontend/components/Designer/AISuggestionsPanel.tsx`
- **Layer:** Designer (Layer 1)
- **Change:** Remove hardcoded `getInventorySuggestions(6)` → call without limit parameter. Track `offeredProductIds: Set<string>` state; pass `isOffered` prop to each `InventorySuggestionCard`.
- **Interface:** Gains `offeredProductIds` internal state; updated on offer generation events.

### COMP-008 — `InventorySuggestionCard` (modified)
- **Path:** `src/frontend/components/Designer/InventorySuggestionCard.tsx`
- **Layer:** Designer (Layer 1)
- **Change:** Accept `isOffered: boolean` prop. When `true`, render button as `disabled` with "Offer Created" label.

### COMP-009 — `ManualEntryForm` (modified)
- **Path:** `src/frontend/components/Designer/ManualEntryForm.tsx`
- **Layer:** Designer (Layer 1)
- **Change:** Add `overriddenFields: Set<string>` state. On `onChange` of `offer_percentage` input, add `'offer_percentage'` to the set. When AI suggestion arrives, skip fields present in `overriddenFields`.

### COMP-010 — `DealScraperService` (modified)
- **Path:** `src/backend/services/deal_scraper_service.py`
- **Layer:** Designer (Layer 1 backend)
- **Change:** Remove `[:15]` cap in `_scrape_source()`. Remove hardcoded `6` from `getInventorySuggestions(6)` call in `AISuggestionsPanel`. Make limit an optional parameter defaulting to `None` (no limit).

---

## Data Flows

### Flow 1 — Partner Purchase Trigger (Happy Path)

```
1. Partner system sends POST /api/scout/partner-trigger
   Headers: X-Webhook-Signature: sha256=<hmac>
   Body: { event_id, partner_id: "tim_hortons", purchase_category: "coffee",
           purchase_amount: 8.50, member_id: "M-12345", timestamp }

2. Scout API: _verify_webhook_signature() → valid

3. Scout API: Pydantic validates PartnerPurchaseEvent

4. PartnerTriggerService.classify_and_generate():
   a. Haiku prompt: "Partner: Tim Hortons. Purchase: coffee, $8.50.
      Predict the most relevant Canadian Tire product category."
   b. Haiku response: "automotive_accessories" (travel mug, car cleaning)
   c. Sonnet: generate OfferBrief for "automotive_accessories" targeting member M-12345
   d. Set: status=active, trigger_type=partner_triggered,
          valid_until=now+24h, payment_split={75, 25}

5. HubApiClient.save_offer(offer) → Hub stores active offer

6. Return HTTP 202: { status: "accepted", offer_id: "..." }

Total latency target: < 2s
```

### Flow 2 — Haiku Failure Fallback

```
1-3. Same as Flow 1

4. PartnerTriggerService.classify_and_generate():
   a. Haiku call → timeout / API error
   b. _fallback_category("tim_hortons") → "automotive_accessories"
   c. Sonnet: generate OfferBrief using fallback category
   d. Set fields as above

5-6. Same as Flow 1
```

### Flow 3 — Redemption Validation (75/25 Enforcement)

```
Member attempts redemption:
  Scout activation pipeline → ScoutMatchService.match()
    → RedemptionEnforcementService.validate_payment_split(offer, redemption)
      → offer.construct.payment_split = {points_max_pct: 75, cash_min_pct: 25}
      → redemption.points_pct = 80 → EXCEEDS 75%
      → raise RedemptionSplitError(points_pct=80, max_pct=75)
    → Scout API returns HTTP 422
      { "detail": "Points redemption (80%) exceeds maximum allowed (75%)" }
```

### Flow 4 — Designer Dirty Flag (Override Protection)

```
1. AI suggestion received: offer_percentage = 30%
   → ManualEntryForm: overriddenFields does NOT contain 'offer_percentage'
   → Field updated to 30%

2. Marketer manually types 20% in offer_percentage input
   → onChange fires → overriddenFields.add('offer_percentage')

3. New AI suggestion arrives: offer_percentage = 35%
   → overriddenFields HAS 'offer_percentage'
   → AI value skipped; field stays at 20% (marketer's value)
```

---

## Decisions (ADRs)

### ADR-001: Partner Trigger as Separate Endpoint vs Extended Purchase Event

**Context:** Partner purchases could either extend the existing `POST /api/scout/purchase-event` endpoint with a `partner_id` field, or be a fully separate endpoint.

**Alternatives:**
- **A) Extend existing endpoint** — add `partner_id?: string` to `PurchaseEventPayload`. Simple, single endpoint.
  - Pro: Less code. Con: Existing dedup/scoring logic runs unnecessarily; confuses Scout match pipeline.
- **B) Separate endpoint `POST /api/scout/partner-trigger`** ← Chosen
  - Pro: Clean separation of concerns; partner pipeline is fundamentally different (Haiku classification, auto-active Hub write, no context scoring). Independent scaling. Easier to extend per-partner.
  - Con: One more route to maintain.

**Decision:** Separate endpoint (B). The partner-trigger pipeline bypasses context scoring entirely and writes directly to Hub as `active` — fundamentally different from the purchase-event flow.

**Consequences:** New router entry in `scout.py`. New `PartnerTriggerService`. Dedup reuses same `_seen_events` dict pattern.

---

### ADR-002: payment_split as Optional Field on Construct vs Separate Model

**Context:** The 75/25 rule could be modelled as a top-level `OfferBrief` field, a field on `Construct`, or a separate validation model.

**Alternatives:**
- **A) Top-level `OfferBrief.payment_split`** — Clearly visible. Con: Conceptually belongs to the offer construct/value, not the brief metadata.
- **B) Field on `Construct.payment_split`** ← Chosen — `PaymentSplit` is a sub-model of `Construct`.
  - Pro: Semantically correct (payment split governs how the construct value is redeemed). Backward compatible (Optional). Easy to extend.
- **C) Separate `RedemptionPolicy` model** — Most flexible. Con: Over-engineered for current scope.

**Decision:** `Construct.payment_split: Optional[PaymentSplit] = None`. Absent = no constraint (backward compatible).

**Consequences:** `PaymentSplit` is a new Pydantic model. Frontend TypeScript types in `shared/types/offer-brief.ts` must mirror this.

---

### ADR-003: Haiku Classification Prompt Strategy

**Context:** Haiku must predict a CTC product category from a partner purchase event. Prompt design affects accuracy.

**Alternatives:**
- **A) Zero-shot** — "Given this purchase, suggest a CTC category." Simple but low accuracy.
- **B) Few-shot with partner examples** ← Chosen — Include 3-4 examples per partner in system prompt.
  - `Tim Hortons coffee → travel mugs, car cleaning`
  - `Tim Hortons food → kitchen/storage`
  - Pro: Higher accuracy, cheap to maintain.
- **C) RAG over CTC product catalogue** — Highest accuracy. Con: Requires vector store, out of scope.

**Decision:** Few-shot system prompt with per-partner examples (B). Fallback to `_PARTNER_FALLBACK_CATEGORIES` dict on failure.

**Consequences:** `PartnerTriggerService` maintains a `_PARTNER_SYSTEM_PROMPTS` dict keyed by `partner_id`. Adding a new partner requires adding prompt examples.

---

### ADR-004: Dirty Flag Implementation — Set vs Individual Booleans

**Context:** `ManualEntryForm` needs to track which fields have been manually edited.

**Alternatives:**
- **A) `overriddenFields: Set<string>`** ← Chosen — Generic; works for any field name.
  - Pro: Extensible to any future editable field without state changes.
- **B) `offerPctOverridden: boolean`** — Simple, explicit. Con: Needs new boolean per field.

**Decision:** `overriddenFields: Set<string>` (A). More extensible; minimal extra complexity.

**Consequences:** `ManualEntryForm` gains one `useState<Set<string>>`. AI suggestion application checks `!overriddenFields.has(fieldName)` before updating.

---

## Implementation Guidelines

### Backend

1. **Order of changes:** Models first (`offer_brief.py` → `partner_event.py`) → Services (`partner_trigger_service.py`, `redemption_enforcement_service.py`) → API (`scout.py`) → Tests
2. **Haiku call pattern:** Use synchronous `anthropic.Anthropic` (existing pattern in `DealScraperService`) inside `asyncio.to_thread()` for non-blocking. Target < 800ms per call.
3. **HMAC reuse:** Call existing `_verify_webhook_signature()` directly; do not duplicate HMAC logic.
4. **`valid_until` requirement:** `OfferBrief` model validator already requires `valid_until` for `purchase_triggered`. Extend this to `partner_triggered` as well.
5. **Fallback must not raise:** `_fallback_category()` must always return a string. Wrap in `try/except Exception` with a hardcoded `"seasonal_promotions"` final fallback.
6. **Scraper limit removal:** In `deal_scraper_service.py` line 172, change `raw_deals[:15]` to `raw_deals`. In `AISuggestionsPanel`, change `getInventorySuggestions(6)` to `getInventorySuggestions()`.

### Frontend

1. **`isOffered` state management:** `AISuggestionsPanel` tracks `offeredProductIds: Set<string>` in local state. When the parent page detects a successful `prefillObjectiveAction` result, the `product_id` is added. Pass `isOffered={offeredProductIds.has(suggestion.product_id)}` to each card.
2. **Disabled button styling:** Use `disabled:opacity-50 disabled:cursor-not-allowed` Tailwind classes. Show "Offer Created" text when disabled.
3. **Dirty flag clear rule:** `overriddenFields` is never cleared automatically. Resetting the form (if implemented) should clear it.
4. **Server Component boundary:** `AISuggestionsPanel` is `'use client'`; `InventorySuggestionCard` can remain a pure component.

### Testing Strategy

| Test File | Type | Coverage Target |
|-----------|------|----------------|
| `tests/unit/redemption_logic_test.py` | Unit (pytest) | 100% of `RedemptionEnforcementService` |
| `tests/unit/backend/services/test_partner_trigger_service.py` | Unit (pytest) | Happy path, Haiku failure, fallback |
| `tests/integration/backend/test_partner_trigger_api.py` | Integration | Tim Hortons purchase → Hub offer |
| `tests/unit/frontend/components/Designer/InventorySuggestionCard.test.tsx` | Unit (Jest) | `isOffered=true` disables button |
| `tests/unit/frontend/components/Designer/ManualEntryForm.test.tsx` | Unit (Jest) | Dirty flag prevents AI override |

---

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| Partner webhook spoofing | HMAC-SHA256 via `SCOUT_WEBHOOK_SECRET` (existing pattern) |
| Partner `member_id` injection | Pydantic validates field format; logs use member_id only (no PII) |
| Haiku prompt injection | Partner-controlled fields (`purchase_category`, `partner_name`) are interpolated into prompt but capped to 100 chars max; output is JSON-parsed not eval'd |
| Duplicate offer creation | `event_id` dedup via `_seen_events` dict (60s window) |
| Excessive scraper requests | Existing 15-minute cache TTL unchanged; no rate limit change needed |
| `points_pct` overflow | Pydantic `Field(..., ge=0, le=100)` on `RedemptionRequest` |

**OWASP Mapping:**
- A03 Injection: prompt field length capping, no string-concat SQL
- A07 Auth Failures: HMAC on all partner webhooks
- A09 Logging Failures: member_id only in `PartnerTriggerService` logs

---

## Testing Strategy

### Unit Tests

**`tests/unit/redemption_logic_test.py`**
```
test_valid_75_25_split_accepted
test_valid_50_50_split_accepted
test_invalid_80_20_split_rejected_422
test_boundary_exactly_75_accepted
test_boundary_75_plus_epsilon_rejected
test_no_payment_split_backward_compatible
```

**`tests/unit/backend/services/test_partner_trigger_service.py`**
```
test_tim_hortons_coffee_classifies_to_automotive
test_haiku_timeout_uses_fallback_category
test_fallback_always_returns_string
test_generated_offer_has_partner_triggered_type
test_generated_offer_has_valid_until_set
test_generated_offer_has_payment_split_75_25
```

### Integration Tests

**`tests/integration/backend/test_partner_trigger_api.py`**
```
test_tim_hortons_purchase_creates_active_hub_offer
test_invalid_hmac_returns_401
test_duplicate_event_id_returns_400
test_offer_visible_in_hub_get_offers
```

### Frontend Tests

**`InventorySuggestionCard.test.tsx`**
```
test_generate_button_enabled_when_not_offered
test_generate_button_disabled_when_is_offered
test_button_shows_offer_created_when_disabled
```

**`ManualEntryForm.test.tsx`** (additions)
```
test_ai_suggestion_updates_unmodified_offer_pct
test_ai_suggestion_does_not_override_manually_edited_offer_pct
test_dirty_flag_set_on_manual_change
```
