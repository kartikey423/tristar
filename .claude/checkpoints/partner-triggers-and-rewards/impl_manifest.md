# Implementation Manifest: partner-triggers-and-rewards

## Summary

- **Feature:** Partner Triggers and Rewards (75/25 payment split, Tim Hortons webhook, Designer enhancements)
- **Branch:** feat/partner-triggers-and-rewards
- **Implementation Date:** 2026-04-03
- **Waves Completed:** 7 of 7
- **Status:** Implementation complete — ready for Phase 6 (Simplify)

## Baseline Test Counts

| Suite | Before |
|-------|--------|
| Backend (pytest) | 191 passed, 9 failed (pre-existing) |
| Frontend (jest) | 41 passed, 6 failed (pre-existing) |

## Final Test Counts

| Suite | After | Delta |
|-------|-------|-------|
| Backend (pytest) | 203 passed, 9 failed (same pre-existing) | +12 |
| Frontend (jest) | 47 passed, 6 failed (same pre-existing) | +6 |

New tests added: 36 total (15 redemption_logic + 16 partner_trigger_service + 5 integration)

## Files Created

| File | Layer | Description |
|------|-------|-------------|
| `src/backend/models/partner_event.py` | Backend | `PartnerPurchaseEvent`, `PartnerTriggerResponse`, `RedemptionRequest`, `RedemptionSplitError` |
| `src/backend/services/redemption_enforcement_service.py` | Backend | 75/25 payment split validation |
| `src/backend/services/partner_trigger_service.py` | Backend | Haiku classification + offer generation + Hub save |
| `tests/unit/redemption_logic_test.py` | Tests | 15 tests covering AC-01–AC-04 + boundaries |
| `tests/unit/backend/services/test_partner_trigger_service.py` | Tests | 16 tests covering dedup, fallback, offer generation, fraud check |
| `tests/integration/backend/test_partner_trigger_api.py` | Tests | 5 integration tests covering AC-05–AC-08 + dedup |

## Files Modified

| File | Layer | Change |
|------|-------|--------|
| `src/shared/types/offer-brief.ts` | Shared | Added `partner_triggered` TriggerType, `PaymentSplit` interface+schema, updated `Construct` |
| `src/backend/models/offer_brief.py` | Backend | Added `partner_triggered` enum, `PaymentSplit` model, updated `Construct`, extended `valid_until` validator |
| `src/backend/services/hub_api_client.py` | Backend | F-001: allow `partner_triggered+active` via `_AUTO_ACTIVE_TRIGGER_TYPES` set |
| `src/backend/services/hub_store.py` | Backend | F-001: server-side allow `partner_triggered+active` |
| `src/backend/services/deal_scraper_service.py` | Backend | Removed 6-item hard limit on clearance item extraction |
| `src/backend/api/deps.py` | Backend | Added `get_partner_trigger_service()` and `get_redemption_enforcement_service()` |
| `src/backend/api/scout.py` | Backend | Added `POST /api/scout/partner-trigger` with HMAC auth + BackgroundTasks |
| `src/backend/api/hub.py` | Backend | F-001: extended active-status check for `partner_triggered` |
| `src/frontend/services/designer-api.ts` | Frontend | Made `limit` param optional in `getInventorySuggestions()` |
| `src/frontend/components/Designer/InventorySuggestionCard.tsx` | Frontend | Added `isOffered` prop — disables Generate button when offer exists |
| `src/frontend/components/Designer/AISuggestionsPanel.tsx` | Frontend | Added `offeredProductIds` set state, `handleOfferGenerated()`, no-limit refresh |
| `src/frontend/components/Designer/ManualEntryForm.tsx` | Frontend | Added `constructValue` + `overriddenFields` dirty-flag state, `construct_value` input field |

## Test Files

| File | Tests | Status |
|------|-------|--------|
| `tests/unit/redemption_logic_test.py` | 15 | ✅ All passing |
| `tests/unit/backend/services/test_partner_trigger_service.py` | 16 | ✅ All passing |
| `tests/integration/backend/test_partner_trigger_api.py` | 5 | ✅ All passing |

## Acceptance Criteria Coverage

| AC | Description | Status |
|----|-------------|--------|
| AC-01 | OfferBrief accepts payment_split field | ✅ |
| AC-02 | 75% points + 25% cash accepted | ✅ |
| AC-03 | 80% points + 20% cash rejected (422) | ✅ |
| AC-04 | No payment_split → backward compatible | ✅ |
| AC-05 | Valid Tim Hortons payload + HMAC → 202 | ✅ |
| AC-06 | Invalid HMAC → 401 | ✅ |
| AC-07 | Offer appears in Hub after trigger | ✅ |
| AC-08 | Offer has partner_triggered type + valid_until | ✅ |
| AC-09 | Duplicate event_id → 400 | ✅ |
| AC-10 | Haiku failure → fallback category used | ✅ |
| AC-11 | Scraper returns all clearance items (no 6-item cap) | ✅ |
| AC-12 | Generate button disabled after offer created | ✅ |
| AC-13 | Marketer-entered construct_value not overwritten by AI | ✅ |
| AC-14 | Fraud check blocks critical-severity partner offers | ✅ |

## Simplification

5 issues fixed across 6 files:

1. **Extracted `AUTO_ACTIVE_TRIGGER_TYPES` constant** (`offer_brief.py`) — eliminated 3 identical inline set literals in `hub.py`, `hub_api_client.py`, and the `OfferBrief` validator. All now import the single `frozenset` source-of-truth.

2. **Moved `_verify_webhook_signature` to `security.py`** — webhook HMAC verification now lives alongside JWT auth. `scout.py` imports `verify_webhook_signature(body, sig, secret)` from `core.security`. Removed `hashlib`/`hmac` imports from `scout.py`.

3. **Removed dead code `applyAISuggestedConstructValue`** (`ManualEntryForm.tsx`) — function was defined but never called. Removed 5 lines of unreachable code.

4. **Eliminated wrapper `<div onClick>` in `AISuggestionsPanel.tsx`** — `handleOfferGenerated` is now passed as `onOfferGenerated` prop to `InventorySuggestionCard`, which calls it on form submit. The wrapper div adding no layout value is gone.

5. **Cleaned stale task-reference comments** from `hub.py` and `hub_api_client.py` docstrings ("F-003 FIX:" prefix removed).
