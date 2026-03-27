# Implementation Manifest: designer-layer

## Status: Implementation Complete

**Date:** 2026-03-27
**Total files written:** 49 (45 new, 4 config/data)
**Waves completed:** 7/7

---

## Design Review Findings — Resolution Status

| Finding | Severity | Status | Resolution |
|---------|----------|--------|------------|
| F-001: Cache returns shared offer_id | Major | ✅ RESOLVED | `claude_api.py`: `model_copy(update={"offer_id": str(uuid.uuid4())})` on every cache hit |
| F-002: Missing Hub member query endpoint | Major | ✅ RESOLVED (MVP) | `delivery_constraint_service.py`: in-memory tracking with Hub endpoint stub in `hub.py`. TODO for production. |
| F-003: Hub draft→active enforcement unspecified | Major | ✅ RESOLVED | `hub_api_client.py`: client-side assert. `hub.py`: server returns 422 if `status=active` + `trigger_type!=purchase_triggered` |
| F-004: valid_until expiry has no owner | Major | ✅ RESOLVED | `main.py`: background asyncio task `_expire_offers_task()` sweeps every 300s |
| F-005: Scout JWT lifecycle no owner | Minor | ✅ RESOLVED | `scout_service_auth.py` (COMP-024): `get_valid_token()` with proactive refresh at 80% TTL |
| F-006: COMP-013 mapped to REQ-005 | Minor | 📝 DOCUMENTED | Documentation-only error. Noted here. |
| F-007: GPS coords not in PII spec | Minor | ✅ RESOLVED | `audit_log_service.py`: location fields explicitly excluded from all log methods |
| F-008: Context enrichment serial | Minor | ✅ RESOLVED | `purchase_event_handler.py`: `asyncio.gather(member, stores, weather, return_exceptions=True)` |
| F-009: Feature flag absent | Minor | ✅ RESOLVED | `config.py`: `PURCHASE_TRIGGER_ENABLED=False` + `PURCHASE_TRIGGER_PILOT_MEMBERS=""` |
| F-010: InventorySuggestionCard undefined | Minor | ✅ RESOLVED | `InventorySuggestionCard.tsx` added in Wave 6 |

---

## Files Written

### Wave 1: Shared Types
- `src/shared/types/offer-brief.ts` — OfferBrief interface + Zod schema (COMP-001)

### Wave 2: Backend Models + Configuration
- `src/backend/models/offer_brief.py` — Pydantic v2 OfferBrief (COMP-002)
- `src/backend/models/purchase_event.py` — PurchaseEvent, EnrichedContext models
- `src/backend/core/config.py` — Settings with feature flags (COMP-023, F-009)
- `.env.example` — Environment variable template
- `data/inventory.csv` — Mock inventory data (10 products)

### Wave 3: Backend Services
- `src/backend/core/security.py` — JWT auth + RBAC (COMP-003)
- `src/backend/services/claude_api.py` — Claude API client with cache + retry (COMP-004, F-001)
- `src/backend/services/inventory_service.py` — CSV inventory loader (COMP-005)
- `src/backend/services/fraud_check_service.py` — Fraud detection (COMP-006)
- `src/backend/services/hub_api_client.py` — Hub HTTP client (COMP-007, F-003)
- `src/backend/services/audit_log_service.py` — Compliance logging (COMP-022, F-007)
- `src/backend/services/purchase_event_handler.py` — Event enrichment (COMP-018, F-008, F-009)
- `src/backend/services/context_scoring_service.py` — 7-factor scoring (COMP-019)
- `src/backend/services/delivery_constraint_service.py` — Rate limits (COMP-020, F-002)
- `src/backend/services/notification_service.py` — Push + email (COMP-021)
- `src/backend/services/scout_service_auth.py` — Scout JWT lifecycle (COMP-024, F-005)

### Wave 4: Backend API Routes
- `pyproject.toml` — Python package dependencies
- `src/backend/api/deps.py` — DI helpers
- `src/backend/api/designer.py` — Designer endpoints (COMP-008)
- `src/backend/api/scout.py` — Scout purchase event endpoint (COMP-017)
- `src/backend/api/hub.py` — Hub stub (F-002, F-003)
- `src/backend/main.py` — FastAPI app + expiry background task (F-004)

### Wave 5: Frontend Services
- `package.json` — Frontend dependencies
- `src/frontend/services/designer-api.ts` — TypeScript API client (COMP-016)

### Wave 6: Frontend Components
- `src/frontend/app/designer/actions.ts` — Server Actions
- `src/frontend/app/designer/page.tsx` — Designer page (COMP-009)
- `src/frontend/components/Designer/InventorySuggestionCard.tsx` — (COMP-024b, F-010)
- `src/frontend/components/Designer/AISuggestionsPanel.tsx` — (COMP-010)
- `src/frontend/components/Designer/ManualEntryForm.tsx` — (COMP-011)
- `src/frontend/components/Designer/ModeSelectorTabs.tsx` — (COMP-012)
- `src/frontend/components/Designer/RiskFlagBadge.tsx` — (COMP-015)
- `src/frontend/components/Designer/OfferBriefCard.tsx` — (COMP-013)
- `src/frontend/components/Designer/ApproveButton.tsx` — (COMP-014)

### Wave 7: Tests
- `tests/__init__.py`, `tests/fixtures/offer_brief_responses.json`
- `tests/unit/backend/models/test_offer_brief.py`
- `tests/unit/backend/services/test_claude_api.py` (F-001 verified)
- `tests/unit/backend/services/test_inventory_service.py`
- `tests/unit/backend/services/test_fraud_check_service.py`
- `tests/unit/backend/services/test_context_scoring_service.py`
- `tests/unit/backend/services/test_delivery_constraint_service.py` (F-002 verified)
- `tests/unit/backend/services/test_purchase_event_handler.py` (F-008 verified)
- `tests/unit/frontend/components/Designer/ManualEntryForm.test.tsx`
- `tests/unit/frontend/components/Designer/ApproveButton.test.tsx`
- `tests/unit/frontend/components/Designer/RiskFlagBadge.test.tsx`
- `tests/integration/backend/api/test_designer_api.py`
- `tests/integration/backend/api/test_scout_purchase_event.py`
- `tests/e2e/designer-flow.spec.ts`
- `tests/jest.setup.ts`

---

## Known Tech Debt

| Item | Description | Priority |
|------|-------------|----------|
| TD-001 | F-002 (Hub member query): `delivery_constraint_service.py` uses in-memory tracking. Production must use Hub API endpoint `GET /api/hub/offers?member_id=&since=` | High |
| TD-002 | Scout→Designer call in `scout.py` uses localhost hardcoded URL. Production must use service discovery or env var | Medium |
| TD-003 | Frontend JWT stored in localStorage. Production should use httpOnly cookie | Medium |
| TD-004 | Mock enrichment in `purchase_event_handler.py` (member history, nearby stores, weather). Production calls real services | High |
| TD-005 | Hub in-memory store (`hub.py`) resets on restart. Production uses Redis | High |

---

## Next Pipeline Phases

- Phase 6: Simplify (code quality review)
- Phase 7: Code Review + Security Scan
- Phase 8: Verification against requirements
- Phase 9: Risk Assessment
- Phase 10: PR Creation
