# Implementation Plan: partner-triggers-and-rewards

## Overview

| Field | Value |
|-------|-------|
| Feature | partner-triggers-and-rewards |
| Total Files | 17 (6 new, 11 modified) |
| Waves | 7 |
| Complexity | High |
| Branch | feat/partner-triggers-and-rewards |
| Design Review | APPROVE_WITH_CONCERNS (57/100) |

---

## Pre-Implementation Baseline

Before writing any code:
1. Create branch: `git checkout -b feat/partner-triggers-and-rewards`
2. Run full test suite and record baseline counts:
   ```bash
   pytest tests/ --co -q 2>/dev/null | tail -1   # backend count
   npm test -- --passWithNoTests 2>/dev/null | grep "Tests:"  # frontend count
   ```
3. Record counts in `impl_manifest.md` under `## Baseline Test Counts`

---

## Wave Plan

### Wave 1: Shared Types

**Goal:** Establish the single source of truth for new types across frontend and backend.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 1 | `src/shared/types/offer-brief.ts` | MODIFY | COMP-006 | Add `partner_triggered` to `TriggerType` union; add `PaymentSplit` interface; add optional `payment_split?: PaymentSplit` to `Construct` |

**Exact changes to `offer-brief.ts`:**
```typescript
// 1. Extend TriggerType union
export type TriggerType = 'marketer_initiated' | 'purchase_triggered' | 'partner_triggered';

// 2. Add PaymentSplit interface
export interface PaymentSplit {
  points_max_pct: number;   // max % payable in Triangle points (default 75)
  cash_min_pct: number;     // min % payable via credit/debit (default 25)
}

// 3. Add payment_split to Construct (optional — backward compat)
export interface Construct {
  type: string;
  value: number;
  description: string;
  payment_split?: PaymentSplit;  // ADD THIS
}

// 4. Update TRIGGER_TYPES constant
export const TRIGGER_TYPES: TriggerType[] = ['marketer_initiated', 'purchase_triggered', 'partner_triggered'];
```

**Wave 1 Verification:**
- [ ] `npx tsc --noEmit` passes with no new errors
- [ ] `partner_triggered` is valid in TriggerType assignments
- [ ] `PaymentSplit` interface is exported

---

### Wave 2: Backend Models

**Goal:** Mirror Wave 1 types in Pydantic v2; add new models for partner events and redemption.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 2 | `src/backend/models/offer_brief.py` | MODIFY | COMP-006 | Add `PaymentSplit` model; add `payment_split: Optional[PaymentSplit]` to `Construct`; add `partner_triggered` to `TriggerType` enum; extend `valid_until` validator |
| 3 | `src/backend/models/partner_event.py` | NEW | COMP-005 | `PartnerPurchaseEvent`, `PartnerTriggerResponse`, `RedemptionRequest`, `RedemptionSplitError` |

**Exact changes to `offer_brief.py`:**
```python
# 1. Add to TriggerType enum
class TriggerType(str, Enum):
    marketer_initiated = "marketer_initiated"
    purchase_triggered = "purchase_triggered"
    partner_triggered = "partner_triggered"   # NEW

# 2. Add PaymentSplit model (before Construct)
class PaymentSplit(BaseModel):
    points_max_pct: float = Field(75.0, ge=0, le=100)
    cash_min_pct: float = Field(25.0, ge=0, le=100)

    @model_validator(mode="after")
    def validate_split(self) -> "PaymentSplit":
        if abs((self.points_max_pct + self.cash_min_pct) - 100.0) > 0.01:
            raise ValueError("points_max_pct + cash_min_pct must equal 100")
        return self

# 3. Add payment_split to Construct
class Construct(BaseModel):
    type: str = Field(..., min_length=1)
    value: float = Field(..., ge=0)
    description: str = Field(..., min_length=1)
    payment_split: Optional[PaymentSplit] = None   # NEW

# 4. Extend valid_until validator
@model_validator(mode="after")
def validate_valid_until_for_purchase_triggered(self) -> "OfferBrief":
    triggered_types = {TriggerType.purchase_triggered, TriggerType.partner_triggered}
    if self.trigger_type in triggered_types and self.valid_until is None:
        raise ValueError("valid_until is required for purchase_triggered and partner_triggered offers")
    return self
```

**New file `src/backend/models/partner_event.py`:**
```python
from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, model_validator

class PartnerPurchaseEvent(BaseModel):
    event_id: str = Field(..., description="Unique event ID for deduplication")
    partner_id: str = Field(..., description="Partner identifier e.g. 'tim_hortons'")
    partner_name: str = Field(..., min_length=1, max_length=100)
    purchase_amount: float = Field(..., ge=0)
    purchase_category: str = Field(..., min_length=1, max_length=100)
    member_id: str = Field(..., description="Triangle member ID")
    timestamp: datetime

class PartnerTriggerResponse(BaseModel):
    status: str   # "accepted" | "duplicate"
    offer_id: Optional[str] = None
    message: str

class RedemptionRequest(BaseModel):
    offer_id: str
    points_pct: float = Field(..., ge=0, le=100)
    cash_pct: float = Field(..., ge=0, le=100)

    @model_validator(mode="after")
    def validate_sum(self) -> "RedemptionRequest":
        if abs((self.points_pct + self.cash_pct) - 100.0) > 0.01:
            raise ValueError("points_pct + cash_pct must equal 100")
        return self

class RedemptionSplitError(Exception):
    def __init__(self, points_pct: float, max_pct: float) -> None:
        self.points_pct = points_pct
        self.max_pct = max_pct
        super().__init__(
            f"Points redemption ({points_pct:.1f}%) exceeds maximum allowed ({max_pct:.1f}%)"
        )
```

**Wave 2 Verification:**
- [ ] `python -c "from src.backend.models.offer_brief import TriggerType; assert TriggerType.partner_triggered"` passes
- [ ] `python -c "from src.backend.models.partner_event import PartnerPurchaseEvent"` passes
- [ ] `PaymentSplit(points_max_pct=80, cash_min_pct=20)` raises `ValueError` (sum != 100)
- [ ] `PaymentSplit(points_max_pct=75, cash_min_pct=25)` succeeds

---

### Wave 3: Backend Services

**Goal:** New business logic services + fix existing services.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 4 | `src/backend/services/redemption_enforcement_service.py` | NEW | COMP-004 | `RedemptionEnforcementService.validate_payment_split()` — 75/25 enforcement |
| 5 | `src/backend/services/partner_trigger_service.py` | NEW | COMP-002, COMP-003 | Haiku classification, Sonnet generation, fallback templates, Hub save, FraudCheck |
| 6 | `src/backend/services/hub_api_client.py` | MODIFY | COMP-001 | Fix F-001: allow `partner_triggered + active` in `save_offer()` assertion |
| 7 | `src/backend/services/deal_scraper_service.py` | MODIFY | COMP-010 | Remove `[:15]` cap at line 172 |

**New file `src/backend/services/redemption_enforcement_service.py`:**
```python
from src.backend.models.offer_brief import OfferBrief
from src.backend.models.partner_event import RedemptionRequest, RedemptionSplitError

class RedemptionEnforcementService:
    def validate_payment_split(self, offer: OfferBrief, redemption: RedemptionRequest) -> None:
        """Enforce payment split. Raises RedemptionSplitError if points exceed max_pct."""
        if offer.construct.payment_split is None:
            return  # no constraint — backward compatible
        max_pct = offer.construct.payment_split.points_max_pct
        if redemption.points_pct > max_pct:
            raise RedemptionSplitError(redemption.points_pct, max_pct)
```

**New file `src/backend/services/partner_trigger_service.py`:**
Key design decisions:
- Haiku for classification (few-shot prompt per partner)
- Sonnet for offer generation (reuses `claude_api.py` pattern)
- `_partner_seen_events: dict[str, datetime]` — isolated from `purchase_event_handler._seen_events`
- `FraudCheckService.validate()` called after generation; blocks on `severity == critical`
- Fallback: if Haiku fails → use `_PARTNER_FALLBACK_CATEGORIES[partner_id]`

```python
_PARTNER_FALLBACK_CATEGORIES: dict[str, str] = {
    "tim_hortons": "automotive_accessories",
    "westjet": "travel_accessories",
    "sport_chek": "outdoor_camping",
    "default": "seasonal_promotions",
}

_PARTNER_SYSTEM_PROMPTS: dict[str, str] = {
    "tim_hortons": """You classify Canadian Tire cross-sell opportunities from Tim Hortons purchases.
Examples:
- coffee/beverage purchase → travel_mugs or car_accessories
- food/baked goods purchase → kitchen_storage
- drive-through purchase → automotive_cleaning
Return ONLY a single CTC product category string. No explanation.""",
    "default": """Classify the most relevant Canadian Tire product category for this partner purchase.
Return ONLY a single product category string.""",
}
```

**Modification to `hub_api_client.py` line 40:**
```python
# BEFORE:
if offer.status == OfferStatus.active and offer.trigger_type != TriggerType.purchase_triggered:

# AFTER:
_AUTO_ACTIVE_TRIGGER_TYPES = {TriggerType.purchase_triggered, TriggerType.partner_triggered}
if offer.status == OfferStatus.active and offer.trigger_type not in _AUTO_ACTIVE_TRIGGER_TYPES:
```

**Modification to `deal_scraper_service.py` line 172:**
```python
# BEFORE:
for raw in raw_deals[:15]:

# AFTER:
for raw in raw_deals:
```

**Wave 3 Verification:**
- [ ] `from src.backend.services.redemption_enforcement_service import RedemptionEnforcementService` imports
- [ ] `from src.backend.services.partner_trigger_service import PartnerTriggerService` imports
- [ ] `RedemptionEnforcementService().validate_payment_split(offer_no_split, req)` passes without error
- [ ] Run existing hub_api tests: `pytest tests/integration/backend/api/test_hub_api.py -x`

---

### Wave 4: Backend API Routes

**Goal:** Add partner-trigger endpoint; fix Hub API F-001 server-side assertion.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 8 | `src/backend/api/scout.py` | MODIFY | COMP-001 | Add `POST /api/scout/partner-trigger` route using `BackgroundTasks` |
| 9 | `src/backend/api/hub.py` | MODIFY | — | Fix F-001: allow `partner_triggered + active` in save_offer validation |
| 10 | `src/backend/api/deps.py` | MODIFY | — | Add `get_partner_trigger_service` and `get_redemption_enforcement_service` dependency factories |

**Route pattern for `scout.py`:**
```python
@router.post(
    "/partner-trigger",
    response_model=PartnerTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def partner_trigger(
    request: Request,
    event: PartnerPurchaseEvent,
    background_tasks: BackgroundTasks,        # async generation — satisfies 2s SLA
    x_webhook_signature: Optional[str] = Header(default=None),
    partner_service: PartnerTriggerService = Depends(get_partner_trigger_service),
) -> PartnerTriggerResponse:
    # 1. HMAC verify (reuse existing helper)
    if settings.ENVIRONMENT != "development":
        body = await request.body()
        if not _verify_webhook_signature(body, x_webhook_signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    # 2. Dedup check
    if partner_service.is_duplicate(event.event_id):
        return PartnerTriggerResponse(status="duplicate", message="Event already processed")
    # 3. Queue generation as background task — return 202 immediately
    background_tasks.add_task(partner_service.classify_and_generate, event)
    return PartnerTriggerResponse(status="accepted", message="Partner event accepted for processing")
```

**Fix to `hub.py` line 84:**
```python
# BEFORE:
if offer.status == OfferStatus.active and offer.trigger_type != TriggerType.purchase_triggered:

# AFTER:
_AUTO_ACTIVE_TYPES = {TriggerType.purchase_triggered, TriggerType.partner_triggered}
if offer.status == OfferStatus.active and offer.trigger_type not in _AUTO_ACTIVE_TYPES:
```

**Wave 4 Verification:**
- [ ] `curl -X POST http://localhost:8000/api/scout/partner-trigger` with valid payload returns 202
- [ ] `curl -X POST http://localhost:8000/api/scout/partner-trigger` without HMAC in prod mode returns 401
- [ ] `pytest tests/integration/backend/api/test_hub_api.py -x` still passes (no regression)

---

### Wave 5: Frontend Services

**Goal:** Update API client to remove hardcoded limit.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 11 | `src/frontend/services/designer-api.ts` | MODIFY | COMP-010 | Change `getInventorySuggestions(limit = 3)` default to `getInventorySuggestions(limit?: number)` — no default limit sent to backend |

**Exact change:**
```typescript
// BEFORE:
export async function getInventorySuggestions(limit = 3): Promise<InventorySuggestion[]> {
  const response = await fetch(`${BASE_URL}/api/designer/suggestions?limit=${limit}`, {

// AFTER:
export async function getInventorySuggestions(limit?: number): Promise<InventorySuggestion[]> {
  const params = limit !== undefined ? `?limit=${limit}` : '';
  const response = await fetch(`${BASE_URL}/api/designer/suggestions${params}`, {
```

**Wave 5 Verification:**
- [ ] `npx tsc --noEmit` passes
- [ ] `getInventorySuggestions()` call (no arg) compiles without error

---

### Wave 6: Frontend Components

**Goal:** Dirty flag in ManualEntryForm; disable Generate button; remove hardcoded limit call.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 12 | `src/frontend/components/Designer/ManualEntryForm.tsx` | MODIFY | COMP-009 | Add `overriddenFields: Set<string>` state; add `construct_value` editable field with dirty flag |
| 13 | `src/frontend/components/Designer/InventorySuggestionCard.tsx` | MODIFY | COMP-008 | Add `isOffered: boolean` prop; disable button with "Offer Created" label when true |
| 14 | `src/frontend/components/Designer/AISuggestionsPanel.tsx` | MODIFY | COMP-007 | Track `offeredProductIds: Set<string>`; call `getInventorySuggestions()` without limit; pass `isOffered` to each card |

**ManualEntryForm dirty flag pattern:**
```typescript
const [overriddenFields, setOverriddenFields] = useState<Set<string>>(new Set());

function markOverridden(fieldName: string) {
  setOverriddenFields(prev => new Set(prev).add(fieldName));
}

// On AI suggestion received — only update fields not overridden:
function applyAISuggestion(suggestion: Partial<OfferFields>) {
  if (!overriddenFields.has('construct_value') && suggestion.construct_value !== undefined) {
    setConstructValue(suggestion.construct_value);
  }
}

// Input with dirty flag:
<input
  name="construct_value"
  type="number"
  value={constructValue}
  onChange={(e) => {
    setConstructValue(Number(e.target.value));
    markOverridden('construct_value');
  }}
/>
```

**InventorySuggestionCard button change:**
```typescript
// Props change:
interface InventorySuggestionCardProps {
  suggestion: InventorySuggestion;
  isOffered: boolean;  // NEW
}

// Button:
<button
  type="submit"
  disabled={isOffered}
  className={`w-full rounded-md border px-4 py-2 text-sm font-medium transition
    focus:outline-none focus:ring-2 focus:ring-ct-red focus:ring-offset-2
    ${isOffered
      ? 'border-gray-300 bg-gray-100 text-gray-400 cursor-not-allowed'
      : 'border-ct-red bg-white text-ct-red hover:bg-ct-red hover:text-white'
    }`}
  aria-label={isOffered ? 'Offer already created' : `Use objective: ${suggestion.suggested_objective}`}
  aria-disabled={isOffered}
>
  {isOffered ? 'Offer Created' : 'Generate Offer'}
</button>
```

**Wave 6 Verification:**
- [ ] `npx tsc --noEmit` passes
- [ ] AISuggestionsPanel renders without errors
- [ ] InventorySuggestionCard with `isOffered=true` shows disabled button in browser

---

### Wave 7: Tests

**Goal:** Full unit + integration coverage for all new and modified code.

| # | File | Action | Tests For | Key Scenarios |
|---|------|--------|-----------|---------------|
| 15 | `tests/unit/redemption_logic_test.py` | NEW | COMP-004 | 75/25 split valid; 80/20 rejected; no split backward compat; boundary 75% exact; boundary 75.001% rejected |
| 16 | `tests/unit/backend/services/test_partner_trigger_service.py` | NEW | COMP-002, COMP-003 | Happy path classification; Haiku failure → fallback; fallback always returns string; offer has partner_triggered type; offer has valid_until; fraud check blocks critical offers |
| 17 | `tests/integration/backend/test_partner_trigger_api.py` | NEW | COMP-001 | Tim Hortons payload → 202 + Hub offer; invalid HMAC → 401; duplicate event_id → 400; offer visible in GET /api/hub/offers |
| 18 | `tests/unit/frontend/components/Designer/InventorySuggestionCard.test.tsx` | MODIFY | COMP-008 | Button enabled when isOffered=false; button disabled when isOffered=true; "Offer Created" text when disabled |
| 19 | `tests/unit/frontend/components/Designer/ManualEntryForm.test.tsx` | MODIFY | COMP-009 | AI suggestion updates unmodified construct_value; AI suggestion skips overridden construct_value; dirty flag set on manual change |

**Wave 7 Verification:**
- [ ] `pytest tests/unit/redemption_logic_test.py -v` — all 6 tests pass
- [ ] `pytest tests/unit/backend/services/test_partner_trigger_service.py -v` — all tests pass
- [ ] `pytest tests/integration/backend/test_partner_trigger_api.py -v -m integration` — all 4 tests pass
- [ ] `npm test -- InventorySuggestionCard` — all tests pass
- [ ] `npm test -- ManualEntryForm` — all tests pass
- [ ] `pytest --cov=src/backend --cov-report=term-missing` — new code ≥ 80% coverage

---

## Acceptance Criteria Mapping

| AC ID | Description | Files (Wave) | Test File |
|-------|-------------|--------------|-----------|
| AC-01 | OfferBrief accepts payment_split | offer_brief.py (W2), offer-brief.ts (W1) | redemption_logic_test.py |
| AC-02 | 75% points + 25% cash → accepted | redemption_enforcement_service.py (W3) | redemption_logic_test.py |
| AC-03 | 80% points → rejected HTTP 422 | redemption_enforcement_service.py (W3), scout.py (W4) | redemption_logic_test.py |
| AC-04 | No payment_split → backward compat | redemption_enforcement_service.py (W3) | redemption_logic_test.py |
| AC-05 | Valid Tim Hortons payload + HMAC → 202 | scout.py (W4), partner_trigger_service.py (W3) | test_partner_trigger_api.py |
| AC-06 | Invalid HMAC → 401 | scout.py (W4) | test_partner_trigger_api.py |
| AC-07 | Hub has active offer within SLA | partner_trigger_service.py (W3), hub.py (W4) | test_partner_trigger_api.py |
| AC-08 | Offer has partner_triggered + valid_until | offer_brief.py (W2), partner_trigger_service.py (W3) | test_partner_trigger_service.py |
| AC-09 | Haiku failure → fallback offer created | partner_trigger_service.py (W3) | test_partner_trigger_service.py |
| AC-10 | Scraper returns > 6 items | deal_scraper_service.py (W3) | existing scraper tests |
| AC-11 | AI cannot overwrite manual offer value | ManualEntryForm.tsx (W6) | ManualEntryForm.test.tsx |
| AC-12 | Generate button disabled after offer | InventorySuggestionCard.tsx (W6), AISuggestionsPanel.tsx (W6) | InventorySuggestionCard.test.tsx |
| AC-13 | redemption_logic_test.py passes | redemption_logic_test.py (W7) | self |
| AC-14 | Integration test: Tim Hortons → Hub | test_partner_trigger_api.py (W7) | self |

---

## Design Review Concerns — Resolution

| Finding | Severity | Resolution in Plan |
|---------|----------|--------------------|
| F-001: HubApiClient assertion blocks partner_triggered+active | Critical | W3 file #6 (hub_api_client.py) + W4 file #9 (hub.py) both updated |
| F-002: shared/types/offer-brief.ts not in modified files | Major | W1 file #1 — explicit TypeScript changes documented |
| F-005: 2s SLA with sequential Haiku+Sonnet | Major | W4 file #8 — BackgroundTasks pattern; return 202 immediately |
| F-006: offer_percentage field doesn't exist | Major | W6 file #12 — dirty flag applied to `construct_value` field added to ManualEntryForm |
| F-003: valid_until validator not extended | Minor | W2 file #2 — validator updated to include `partner_triggered` |
| F-004: _seen_events dict isolation | Minor | W3 file #5 — `_partner_seen_events` isolated dict with `partner:` prefix |
| F-007: No fraud detection for partner offers | Minor | W3 file #5 — `FraudCheckService.validate()` called in `classify_and_generate()` |

---

## Risk Register

| Risk | Impact | Mitigation | Wave |
|------|--------|------------|------|
| R-01: Hub API rejects partner_triggered+active | High | Fix both hub.py and hub_api_client.py in same wave (W3+W4); run hub integration tests after each | W3, W4 |
| R-02: Haiku latency causes 2s SLA breach | High | BackgroundTasks decouples HTTP response from generation; 202 returned before Claude calls | W4 |
| R-03: TypeScript/Pydantic schema drift | High | Wave 1 (TS) before Wave 2 (Pydantic); verify field names match exactly | W1, W2 |
| R-04: offer_percentage ambiguity | Medium | Implement as `construct_value` numeric input in ManualEntryForm; document in component | W6 |
| R-05: FraudCheck blocks all partner offers | Medium | Partner offers use controlled templates with capped discount values; add test for non-critical fraud result | W3 |
| R-06: Scraper returns 100s of items | Low | Frontend AISuggestionsPanel uses virtual scroll or pagination; backend Haiku context limit still caps at 100KB HTML | W3, W6 |

---

## Pipeline Continuation

After implementation completes:
1. Run `simplify` skill on changed files
2. Run `code-review` + `generate-tests` + `security-scan` in parallel (Phase 7)
3. Run `sdlc-verify` + domain skills (Phase 8)
4. Run `sdlc-risk` (Phase 9)
5. Run `create-pr` targeting `main` (Phase 10)
