# Implementation Plan: designer-layer

## Overview

| Field | Value |
|-------|-------|
| **Total Files** | 49 (45 new, 4 config/data) |
| **Waves** | 7 |
| **Complexity** | High |
| **Design Review Decision** | APPROVE_WITH_CONCERNS (50/100) |
| **Major Findings to Resolve** | 4 (F-001, F-002, F-003, F-004) |

### Design Review Concern Resolution Summary

| Finding | Severity | Resolution | Wave |
|---------|----------|------------|------|
| F-001: Cache returns shared offer_id | Major | COMP-004: generate fresh UUID on cache hit | Wave 3 |
| F-002: Missing Hub member query endpoint | Major | COMP-020: in-memory per-session tracking (MVP); Hub endpoint documented for production | Wave 3 |
| F-003: Hub draft→active enforcement unspecified | Major | COMP-007 + hub.py: assert trigger_type in Hub client; document enforcement contract | Wave 3+4 |
| F-004: valid_until expiry has no owner | Major | main.py: background asyncio task sweeps active→expired every 5 min | Wave 4 |
| F-005: Scout JWT lifecycle no owner | Minor | Add `src/backend/services/scout_service_auth.py` (COMP-024) | Wave 3 |
| F-007: GPS coords not in PII spec | Minor | COMP-022: exclude location from all audit log writes | Wave 3 |
| F-008: Context enrichment serial | Minor | COMP-018: use asyncio.gather for parallel enrichment | Wave 3 |
| F-009: Feature flag absent | Minor | COMP-023: add PURCHASE_TRIGGER_ENABLED + PILOT_MEMBER_IDS flags | Wave 2 |
| F-010: InventorySuggestionCard undefined | Minor | Add as COMP-024b in Wave 6 | Wave 6 |

---

## Wave Plan

### Wave 1: Shared Types (Foundation)

**Goal:** Define the OfferBrief contract that all other waves depend on.
**Verification:** TypeScript compiles, Zod validates sample data, rejects invalid data.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 1 | `src/shared/types/offer-brief.ts` | NEW | COMP-001 | OfferBrief interface, Zod schema, TriggerType, OfferStatus, all nested types (Segment, Construct, Channel, KPIs, RiskFlags) |

**Wave 1 Verification Checklist:**
- [ ] `OfferBrief` interface has all fields: offer_id, objective, segment, construct, channels, kpis, risk_flags, status, trigger_type, created_at, valid_until
- [ ] `TriggerType` = `'marketer_initiated' | 'purchase_triggered'`
- [ ] `OfferStatus` = `'draft' | 'approved' | 'active' | 'expired'`
- [ ] `OfferBriefSchema` Zod schema validates a complete sample OfferBrief JSON
- [ ] `OfferBriefSchema` rejects: missing offer_id, objective < 10 chars, empty channels array
- [ ] TypeScript strict mode compiles with zero errors

---

### Wave 2: Backend Models + Configuration

**Goal:** Mirror Wave 1 types in Pydantic v2 and establish runtime configuration.
**Verification:** Pydantic validates same data that Zod accepts. Settings loads from .env.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 2 | `src/backend/models/offer_brief.py` | NEW | COMP-002 | Pydantic v2 OfferBrief, Segment, Construct, Channel, KPIs, RiskFlags, OfferStatus enum, TriggerType enum |
| 3 | `src/backend/models/purchase_event.py` | NEW | — | PurchaseEvent, PurchaseEventPayload, EnrichedContext, MemberProfile, NearbyStore, WeatherConditions, GeoPoint Pydantic models for Scout layer |
| 4 | `src/backend/core/config.py` | NEW | COMP-023 | Settings (pydantic-settings BaseSettings). Fields: CLAUDE_API_KEY, HUB_API_URL, INVENTORY_FILE_PATH, JWT_SECRET, WEATHER_API_KEY, NOTIFICATION_PROVIDER_URL, QUIET_HOURS_START=22, QUIET_HOURS_END=8, PURCHASE_TRIGGER_SCORE_THRESHOLD=70.0, PURCHASE_TRIGGER_RATE_LIMIT_HOURS=6, CACHE_TTL_SECONDS=300, **PURCHASE_TRIGGER_ENABLED=False** (F-009), **PURCHASE_TRIGGER_PILOT_MEMBERS=""** (F-009) |
| 5 | `.env.example` | NEW | — | Template: CLAUDE_API_KEY, HUB_API_URL, INVENTORY_FILE_PATH, JWT_SECRET, WEATHER_API_KEY, PURCHASE_TRIGGER_ENABLED |
| 6 | `data/inventory.csv` | NEW | — | Mock inventory data (10 products across Sport Chek, Mark's, Canadian Tire) |

**Wave 1+2 Sync Check (REQUIRED before Wave 3):**
- [ ] All `OfferBrief` fields in TypeScript interface exist in Python `OfferBrief` Pydantic model with compatible types
- [ ] `TriggerType` enum values match exactly: `marketer_initiated`, `purchase_triggered`
- [ ] `OfferStatus` enum values match: `draft`, `approved`, `active`, `expired`
- [ ] `valid_until` is Optional in both schemas (only set for purchase-triggered offers)

---

### Wave 3: Backend Services (Business Logic)

**Goal:** Implement all service-layer components. This is the largest wave.
**Verification:** Unit tests pass for each service with mocked dependencies.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 7 | `src/backend/core/security.py` | NEW | COMP-003 | JWT validation: `get_current_user()`, `require_marketing_role()`, `AuthUser` model. Decodes HS256 JWT from Bearer token. |
| 8 | `src/backend/services/claude_api.py` | NEW | COMP-004 | Anthropic SDK wrapper. `generate_from_objective()`, `generate_from_purchase_context()`. Retry: 3× exponential backoff (1s/2s/4s). Cache: 5-min TTL in-process dict, key=SHA256(lower(objective)). **F-001 FIX: Generate fresh UUID4 for offer_id on every cache hit.** Parse Claude JSON response → validate with Pydantic. |
| 9 | `src/backend/services/inventory_service.py` | NEW | COMP-005 | Load CSV from INVENTORY_FILE_PATH at startup. `get_suggestions(limit=3)`: return overstock items (>500 units) sorted by urgency. `get_overstock_items()`. Staleness check: if file mtime >24h, set `stale=True` in response. |
| 10 | `src/backend/services/fraud_check_service.py` | NEW | COMP-006 | Integrates loyalty-fraud-detection skill logic. Check: over_discounting (>30% = critical), offer_stacking (>3 active = critical), cannibalization, frequency_abuse. `validate(offer, member_id)` → `FraudCheckResult(severity, flags, warnings, blocked)`. Blocked = True if any flag severity=critical. |
| 11 | `src/backend/services/hub_api_client.py` | NEW | COMP-007 | httpx async client for Hub API. `save_offer(offer)` → POST /api/hub/offers. **F-003 FIX: Assert that if status=active is sent, trigger_type must be purchase_triggered. Raise AssertionError otherwise.** `get_offer(offer_id)` → GET /api/hub/offers/{id}. `get_recent_member_offers(member_id, since)` → GET /api/hub/offers?member_id=&since= (documents Hub endpoint requirement). |
| 12 | `src/backend/services/audit_log_service.py` | NEW | COMP-022 | Structured compliance logging. `log_generation()`, `log_approval()`, `log_delivery()`, `log_fraud_block()`. `_scrub_pii(text)` removes emails (regex), phone numbers (regex). **F-007 FIX: Explicitly exclude location/lat/lon from all log writes.** Uses loguru with JSON format. |
| 13 | `src/backend/services/purchase_event_handler.py` | NEW | COMP-018 | Process purchase events. Enrich with member history, nearby stores, weather using **asyncio.gather (F-008 FIX)** for parallel execution. Deduplicate transactions within 60-second window using in-memory set. Check PURCHASE_TRIGGER_ENABLED and PILOT_MEMBER_IDS before proceeding (F-009). |
| 14 | `src/backend/services/context_scoring_service.py` | NEW | COMP-019 | Score purchase context 0–100. Factors: purchase_value (max 20), proximity (max 25), frequency (max 15), category_affinity (max 20), partner_crosssell (max 15), weather (max 10), time_alignment (max 5). `score(context)` → `ContextScore(total, breakdown, should_trigger)`. `should_trigger = total > 70.0`. |
| 15 | `src/backend/services/delivery_constraint_service.py` | NEW | COMP-020 | Rate limit enforcement. **F-002 FIX (MVP): Use in-memory dict `{member_id: [timestamp]}` to track recent offers per member. Note in docstring: production requires Hub query endpoint GET /api/hub/offers?member_id=&since=.** `can_deliver(member_id, amount)`: check 6h window, 24h window (unless amount > $100), quiet hours. `queue_for_morning(member_id, offer_id)`. |
| 16 | `src/backend/services/notification_service.py` | NEW | COMP-021 | Send push notifications. `send_push(member_id, offer)`: 3 retries. `send_email_fallback(member_id, offer)`: triggered after 3 push failures. Returns `NotificationResult(delivered, channel, attempted_at, delivered_at)`. Mock implementation for MVP (log + return success). |
| 17 | `src/backend/services/scout_service_auth.py` | NEW | COMP-024 | **F-005 FIX.** Service JWT lifecycle manager. `generate_service_token()`: creates JWT with role=system, exp=24h. `get_valid_token()`: returns current token, regenerates if 80% of TTL elapsed. Stores token in memory. |

**Wave 3 Verification Checklist:**
- [ ] `claude_api.py` cache hit returns different `offer_id` (UUID) from original cached offer
- [ ] `claude_api.py` retries 3× on API failure with 1s/2s/4s delays
- [ ] `fraud_check_service.py` returns `blocked=True` for discount > 30%
- [ ] `fraud_check_service.py` returns `blocked=True` for offer_stacking > 3 active
- [ ] `hub_api_client.py` raises AssertionError if `status=active` + `trigger_type=marketer_initiated`
- [ ] `purchase_event_handler.py` uses `asyncio.gather` for parallel enrichment
- [ ] `purchase_event_handler.py` respects PURCHASE_TRIGGER_ENABLED=False (discards event)
- [ ] `delivery_constraint_service.py` blocks if member received offer within 6h
- [ ] `audit_log_service.py` scrubs emails from objective text
- [ ] `audit_log_service.py` does NOT log `location.lat` or `location.lon`

---

### Wave 4: Backend API Routes

**Goal:** Wire services together in FastAPI routes with authentication and error handling.
**Verification:** Route tests pass with mocked services. Auth is enforced.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 18 | `pyproject.toml` | NEW | — | FastAPI, pydantic-settings, anthropic, httpx, python-jose[cryptography], loguru, pytest, pytest-asyncio, pytest-cov, freezegun, coverage |
| 19 | `src/backend/api/deps.py` | NEW | — | Shared DI helpers: `get_claude_service()`, `get_fraud_service()`, `get_hub_client()`, `get_inventory_service()`, `get_audit_service()` |
| 20 | `src/backend/api/designer.py` | NEW | COMP-008 | POST /api/designer/generate → GenerateOfferRequest → ClaudeApiService + FraudCheckService + AuditLogService. POST /api/designer/generate-purchase → PurchaseContextRequest → ClaudeApiService + FraudCheckService + HubApiClient (status=active) + AuditLogService. POST /api/designer/approve/{offer_id} → HubApiClient (status=approved). GET /api/designer/suggestions → InventoryService. All routes: JWT + marketing role via Depends(require_marketing_role) EXCEPT generate-purchase which uses Depends(require_system_role). Custom exception handlers for FraudBlockedError (422), ClaudeApiError (503), HubSaveError (502). |
| 21 | `src/backend/api/scout.py` | NEW | COMP-017 | POST /api/scout/purchase-event → validate HMAC-SHA256 signature from X-Webhook-Signature header. Reject if is_refund=True or amount ≤ 0. Check PURCHASE_TRIGGER_ENABLED. Call PurchaseEventHandler → ContextScoringService. If score > 70: DeliveryConstraintService.can_deliver → if allowed: call POST /api/designer/generate-purchase internally. Return 202 Accepted. |
| 22 | `src/backend/api/hub.py` | NEW | — | Hub stub for integration. POST /api/hub/offers: in-memory dict store (dev). Validates trigger_type enforcement: if status=active AND trigger_type != purchase_triggered → return 422. GET /api/hub/offers/{id}. GET /api/hub/offers?member_id=&since=. PUT /api/hub/offers/{id}/status. **F-003 FIX: Hub validates trigger_type before accepting status=active.** |
| 23 | `src/backend/main.py` | NEW | — | FastAPI app with lifespan. Register routers (designer, scout, hub). CORS middleware. Request logging middleware. Global exception handlers. **F-004 FIX: Background asyncio task `expire_offers_task()`: every 300s, scan Hub in-memory dict, set status=expired for offers where valid_until < now.** |

**Wave 3+4 Sync Check (REQUIRED before Wave 5):**
- [ ] `POST /api/designer/generate` returns 201 with OfferBrief + fraud_check + cached
- [ ] `POST /api/designer/generate-purchase` returns 201 with offer_id + status=active
- [ ] `POST /api/designer/approve/{id}` returns 200 with updated status
- [ ] `POST /api/scout/purchase-event` returns 202 Accepted
- [ ] Unauthenticated requests to /api/designer/* return 401
- [ ] role=analyst (non-marketing) requests return 403
- [ ] Hub POST with status=active + trigger_type=marketer_initiated returns 422

**Wave 4 Verification Checklist:**
- [ ] `pytest tests/unit/backend/ -v` — all pass
- [ ] Swagger UI loads at http://localhost:8000/docs
- [ ] Background expiry task starts with application

---

### Wave 5: Frontend Services

**Goal:** Type-safe API client connecting Next.js frontend to FastAPI backend.
**Verification:** TypeScript compiles. Functions match backend API contracts.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 24 | `package.json` | NEW | — | next, react, react-dom, typescript, tailwindcss, zod, @testing-library/react, @testing-library/user-event, jest, playwright |
| 25 | `src/frontend/services/designer-api.ts` | NEW | COMP-016 | `generateOffer(objective, segmentHints)` → POST /api/designer/generate. `approveOffer(offerId)` → POST /api/designer/approve/{id}. `getInventorySuggestions()` → GET /api/designer/suggestions. `generateFromPurchaseContext(ctx)` → POST /api/designer/generate-purchase. All functions: include JWT Bearer token in Authorization header (from cookie/localStorage). Error handling: throw typed errors for 401, 403, 422, 503. |

**Wave 4+5 Sync Check:**
- [ ] `generateOffer()` request body matches `GenerateOfferRequest` Pydantic model
- [ ] Response type matches `OfferBrief` from `src/shared/types/offer-brief.ts`
- [ ] `approveOffer()` handles 400 (critical risk) with typed error
- [ ] TypeScript compiles with zero errors

---

### Wave 6: Frontend Components

**Goal:** Build all Designer UI components following React 19 patterns.
**Verification:** Components render correctly, forms validate, Server Components fetch data.

| # | File | Action | COMP-ID | Description |
|---|------|--------|---------|-------------|
| 26 | `src/frontend/app/designer/actions.ts` | NEW | — | Server Actions (`'use server'`). `generateOfferAction(formData)` → calls ClaudeAPI via backend. `approveOfferAction(offerId)` → calls Hub via backend. Used by ManualEntryForm and ApproveButton. |
| 27 | `src/frontend/app/designer/page.tsx` | NEW | COMP-009 | Server Component. Fetches inventory suggestions server-side with `await getInventorySuggestions()`. Renders `<ModeSelectorTabs>` + layout. `<Suspense fallback={<LoadingSpinner />}>` around data-dependent sections. |
| 28 | `src/frontend/components/Designer/InventorySuggestionCard.tsx` | NEW | COMP-024b | **F-010 FIX.** Server Component. Path: as shown. Props: `{ suggestion: InventorySuggestion }`. Displays product name, stock level, urgency badge, suggested objective. "Use This Objective" button populates ManualEntryForm. |
| 29 | `src/frontend/components/Designer/AISuggestionsPanel.tsx` | NEW | COMP-010 | Server Component. Receives `suggestions: InventorySuggestion[]` as props (fetched by parent page). Maps to `<InventorySuggestionCard>`. Shows "Stock data unavailable" notice if `stale=true`. |
| 30 | `src/frontend/components/Designer/ManualEntryForm.tsx` | NEW | COMP-011 | `'use client'`. Textarea for objective (10–500 chars). Zod validation on submit using `OfferBriefSchema`. Calls `generateOfferAction` Server Action. `useFormStatus` for pending state (disable button + show spinner). On success: set result state and render `<OfferBriefCard offer={result}>`. |
| 31 | `src/frontend/components/Designer/ModeSelectorTabs.tsx` | NEW | COMP-012 | `'use client'`. Tab switcher with `useState<'ai' \| 'manual'>`. Renders `<AISuggestionsPanel>` or `<ManualEntryForm>` based on mode. Tab styling: active = blue border, inactive = gray. |
| 32 | `src/frontend/components/Designer/RiskFlagBadge.tsx` | NEW | COMP-015 | Server Component. Props: `{ riskFlags: RiskFlags }`. Critical = red bg + warning icon. Medium = yellow bg + caution icon. Low = gray bg + info icon. Lists active flag names (over_discounting, etc.). |
| 33 | `src/frontend/components/Designer/OfferBriefCard.tsx` | NEW | COMP-013 | Server Component. Displays all OfferBrief fields in card layout. Sections: Segment, Construct (type + value + validity), Channels (priority-ordered), KPIs (redemption rate, uplift %), Risk Flags (`<RiskFlagBadge>`), Approve button (`<ApproveButton>`). |
| 34 | `src/frontend/components/Designer/ApproveButton.tsx` | NEW | COMP-014 | `'use client'`. Disabled when `riskFlags.severity === 'critical'`. Tooltip on disabled: "Critical risk detected — cannot approve." Calls `approveOfferAction`. `useOptimistic` for instant status update. On success: show green "Saved to Hub" toast. On error: show red error message with retry. |

**Wave 6 Verification Checklist:**
- [ ] `/designer` page loads and shows mode selector
- [ ] AI Suggestions mode shows top-3 inventory recommendations
- [ ] Manual Entry form rejects objective < 10 chars with inline error
- [ ] Manual Entry form shows spinner during generation
- [ ] Generated OfferBrief displays all fields (segment name, construct type+value, channels, KPIs)
- [ ] Critical risk flag → red badge + Approve button disabled
- [ ] Medium risk flag → yellow badge + Approve button enabled
- [ ] Approve success → "Saved to Hub" confirmation visible

---

### Wave 7: Tests

**Goal:** >80% unit test coverage, all integration tests pass, E2E critical paths verified.
**Verification:** `pytest --cov=src/backend --cov-report=term-missing` + `npm test` + `npm run test:e2e`.

| # | File | Action | Tests For | Key Scenarios |
|---|------|--------|-----------|---------------|
| 35 | `tests/__init__.py` | NEW | — | Package marker |
| 36 | `tests/fixtures/offer_brief_responses.json` | NEW | — | Sample Claude API responses for mocking |
| 37 | `tests/unit/backend/models/test_offer_brief.py` | NEW | COMP-002 | Valid OfferBrief validates, missing offer_id fails, invalid status rejected, trigger_type enum validates |
| 38 | `tests/unit/backend/services/test_claude_api.py` | NEW | COMP-004 | Cache miss calls Claude API; cache hit returns fresh UUID (F-001); retry on 3× failure; invalid JSON from Claude raises error |
| 39 | `tests/unit/backend/services/test_inventory_service.py` | NEW | COMP-005 | Returns top-3 overstock items; low-stock excluded; stale=True when mtime >24h |
| 40 | `tests/unit/backend/services/test_fraud_check_service.py` | NEW | COMP-006 | Discount >30% → severity=critical; offer_stacking >3 → critical; low discount → severity=low; blocked=True iff critical |
| 41 | `tests/unit/backend/services/test_context_scoring_service.py` | NEW | COMP-019 | Partner store purchase = +15pts; proximity <1km = +25pts; total >70 → should_trigger=True; total ≤70 → should_trigger=False; score at exactly 70 → should_trigger=False |
| 42 | `tests/unit/backend/services/test_delivery_constraint_service.py` | NEW | COMP-020 | Blocks if member received offer within 6h; allows if >6h passed; allows if amount >$100 within 24h; quiet hours (10pm) → queues for 8am; exact boundary: 10:00pm = queued |
| 43 | `tests/unit/backend/services/test_purchase_event_handler.py` | NEW | COMP-018 | Enrichment is concurrent (mock gather); PURCHASE_TRIGGER_ENABLED=False → event discarded; refund event discarded; split transactions (60s window) deduplicated |
| 44 | `tests/unit/frontend/components/Designer/ManualEntryForm.test.tsx` | NEW | COMP-011 | Empty submit → validation error shown; objective <10 chars → error; valid objective → shows spinner; form success → OfferBriefCard rendered |
| 45 | `tests/unit/frontend/components/Designer/ApproveButton.test.tsx` | NEW | COMP-014 | severity=critical → button disabled; severity=medium → button enabled; click → optimistic update; success → "Saved to Hub" visible; error → retry shown |
| 46 | `tests/unit/frontend/components/Designer/RiskFlagBadge.test.tsx` | NEW | COMP-015 | Critical → red badge; medium → yellow badge; low → gray badge; flag names listed |
| 47 | `tests/integration/backend/api/test_designer_api.py` | NEW | COMP-008 | POST /generate 201 with valid objective; POST /generate 400 with short objective; POST /generate 401 without token; POST /generate 422 with fraud critical; POST /approve/{id} 200; POST /approve/{id} 409 wrong status |
| 48 | `tests/integration/backend/api/test_scout_purchase_event.py` | NEW | COMP-017 | POST /purchase-event 202 valid payload; POST /purchase-event 400 with refund; POST /purchase-event 400 missing member_id; PURCHASE_TRIGGER_ENABLED=False → 202 but no offer generated |
| 49 | `tests/e2e/designer-flow.spec.ts` | NEW | End-to-end | 1) Navigate to /designer; 2) Select Manual Entry; 3) Enter valid objective; 4) Wait for OfferBrief; 5) Verify segment + construct displayed; 6) Click Approve; 7) Verify "Saved to Hub" |

**Wave 7 Verification Checklist:**
- [ ] `pytest tests/unit/ --cov=src/backend --cov-report=term-missing` → coverage ≥ 80%
- [ ] `npm test` → all Jest tests pass
- [ ] `pytest tests/integration/` → all integration tests pass
- [ ] `npm run test:e2e` → designer-flow.spec.ts passes end-to-end
- [ ] No tests make real Claude API calls (all mocked via fixtures)
- [ ] Time-dependent tests use `freezegun` (quiet hours boundary, rate limit window)

---

## Acceptance Criteria Mapping

| AC ID | Description (abbreviated) | Primary Files | Test File | Waves |
|-------|---------------------------|---------------|-----------|-------|
| AC-001 | Suggest "Clear winter inventory" for 500+ units | inventory_service.py, AISuggestionsPanel | test_inventory_service.py | 3, 6 |
| AC-002 | Exclude low-stock (<50) from suggestions | inventory_service.py | test_inventory_service.py | 3 |
| AC-003 | Top-3 AI suggestions on page load | designer/page.tsx, AISuggestionsPanel | ManualEntryForm.test.tsx | 6 |
| AC-004 | Call Claude API with marketer objective | claude_api.py, designer.py | test_claude_api.py | 3, 4 |
| AC-005 | Parse Claude response into OfferBrief | claude_api.py | test_claude_api.py | 3 |
| AC-006 | Retry on timeout, < 3 attempts | claude_api.py | test_claude_api.py | 3 |
| AC-007 | Error message after 3 retries exhausted | claude_api.py, designer.py | test_claude_api.py, test_designer_api.py | 3, 4 |
| AC-008 | Invoke fraud detection after generation | fraud_check_service.py, designer.py | test_fraud_check_service.py | 3, 4 |
| AC-009 | Block approval on severity=critical | fraud_check_service.py, ApproveButton | test_fraud_check_service.py, ApproveButton.test.tsx | 3, 4, 6 |
| AC-010 | Allow approval with warning on low/medium | fraud_check_service.py, ApproveButton | test_fraud_check_service.py | 3, 6 |
| AC-011 | POST offer to Hub on approval | hub_api_client.py, designer.py | test_designer_api.py | 3, 4 |
| AC-012 | Show "Offer saved to Hub" success | ApproveButton.tsx | ApproveButton.test.tsx | 6 |
| AC-013 | Show error + retry if Hub save fails | hub_api_client.py, ApproveButton | test_designer_api.py | 3, 4, 6 |
| AC-014 | 401 on unauthenticated Designer request | security.py, designer.py | test_designer_api.py | 3, 4 |
| AC-015 | 403 on non-marketing role | security.py, designer.py | test_designer_api.py | 3, 4 |
| AC-016 | Allow marketing role access | security.py, designer.py | test_designer_api.py | 3, 4 |
| AC-017 | AI Suggestions mode shows recommendations | ModeSelectorTabs, AISuggestionsPanel | — | 6 |
| AC-018 | Manual Entry mode shows objective form | ModeSelectorTabs, ManualEntryForm | ManualEntryForm.test.tsx | 6 |
| AC-019 | Both modes save with identical OfferBrief schema | hub_api_client.py | test_designer_api.py | 3, 4 |
| AC-020 | /designer shows mode selector | designer/page.tsx, ModeSelectorTabs | designer-flow.spec.ts | 6, 7 |
| AC-024 | Tim Hortons purchase triggers Scout listener | scout.py | test_scout_purchase_event.py | 4 |
| AC-028 | Score > 70 → call Designer API | context_scoring_service.py, scout.py | test_context_scoring_service.py | 3, 4 |
| AC-029 | Designer generates offer from purchase context | claude_api.py, designer.py | test_claude_api.py | 3, 4 |
| AC-030 | Auto-save to Hub with status=active | hub_api_client.py, hub.py | test_designer_api.py | 3, 4 |
| AC-036 | Enforce 6h rate limit per member | delivery_constraint_service.py | test_delivery_constraint_service.py | 3 |
| AC-041 | Score ≤ 70 → no trigger | context_scoring_service.py | test_context_scoring_service.py | 3 |
| AC-042 | Rate limit: max 1 per member per 6h | delivery_constraint_service.py | test_delivery_constraint_service.py | 3 |
| AC-044 | Quiet hours 10pm-8am → queue for 8am | delivery_constraint_service.py | test_delivery_constraint_service.py | 3 |
| AC-048 | Rewards system publishes purchase event | scout.py | test_scout_purchase_event.py | 4 |
| AC-049 | Reject invalid/incomplete purchase events | scout.py | test_scout_purchase_event.py | 4 |
| AC-050 | Reject refund transactions | scout.py | test_scout_purchase_event.py | 4 |

---

## Risk Register

| ID | Risk | Impact | Mitigation | Wave |
|----|------|--------|------------|------|
| R-001 | Wave 1+2 schema drift (TypeScript vs Pydantic) | High | Run explicit sync check at Wave 2 completion before proceeding. Optional: add a JSON round-trip test. | 1-2 |
| R-002 | Claude API unavailable during development | High | Implement mock_claude_api fixture early (Wave 3). All tests use fixture, not real API. | 3 |
| R-003 | Hub API not yet implemented (dependency on Hub layer) | High | Implement Hub stub in hub.py (Wave 4) sufficient for integration tests. Document production endpoint requirements. | 4 |
| R-004 | F-002 (Hub member query) — production gap | Medium | MVP uses in-memory tracking in delivery_constraint_service.py. Leave TODO comment documenting Hub query endpoint needed. Add to impl_manifest as known tech debt. | 3 |
| R-005 | Scout→Designer service JWT not tested end-to-end | Medium | Integration test for POST /scout/purchase-event must mock the Scout→Designer JWT call. COMP-024 (ScoutServiceAuth) unit tested separately. | 3, 4 |
| R-006 | Context scoring threshold (70) may not match real-world effectiveness | Medium | Threshold is externalized as `PURCHASE_TRIGGER_SCORE_THRESHOLD` setting. Can tune without code change. | 3 |
| R-007 | valid_until expiry background task timing | Low | Background task runs every 5 min. Offers may be active for up to 5 min past expiry. Acceptable for MVP. | 4 |
| R-008 | PURCHASE_TRIGGER_ENABLED=False default prevents demo | Low | Set PURCHASE_TRIGGER_ENABLED=True in .env for demo environment. Document in .env.example. | 2 |
| R-009 | Frontend JWT storage (localStorage vs httpOnly cookie) | Medium | Use httpOnly cookie for JWT storage (secure, XSS-resistant). Document in security.md. Set in auth flow. | 5 |
| R-010 | asyncio.gather in COMP-018 fails if one enrichment call throws | Low | Use `asyncio.gather(*tasks, return_exceptions=True)`. Handle individual failures gracefully (partial data). | 3 |

---

## Design Review Concerns Resolution

| Finding | Severity | How Addressed in This Plan |
|---------|----------|---------------------------|
| F-001: Cache returns shared offer_id | Major | **Wave 3, claude_api.py**: Generate UUID4 on every cache hit. Documented in Wave 3 service spec. Verified by test_claude_api.py. |
| F-002: Missing Hub member query endpoint | Major | **Wave 3, delivery_constraint_service.py**: In-memory tracking for MVP. TODO comment documents production requirement. Wave 4, hub.py: adds the missing GET endpoint as part of Hub stub. |
| F-003: Hub draft→active enforcement | Major | **Wave 3, hub_api_client.py**: Client-side assertion. **Wave 4, hub.py**: Server-side 422 if status=active + wrong trigger_type. Both layers enforce. |
| F-004: valid_until expiry | Major | **Wave 4, main.py**: Background asyncio task every 300s sweeps hub in-memory dict. |
| F-005: Scout JWT lifecycle | Minor | **Wave 3**: New file `scout_service_auth.py` (COMP-024) with generate + refresh logic. |
| F-006: COMP-013 mapped to REQ-005 | Minor | Mapping error is documentation-only. Noted in impl_manifest. |
| F-007: GPS coords not in PII spec | Minor | **Wave 3, audit_log_service.py**: Explicitly excludes location fields from all log writes. |
| F-008: Context enrichment serial | Minor | **Wave 3, purchase_event_handler.py**: asyncio.gather for concurrent enrichment. Noted in Wave 3 verification. |
| F-009: Feature flag absent | Minor | **Wave 2, config.py**: PURCHASE_TRIGGER_ENABLED + PURCHASE_TRIGGER_PILOT_MEMBERS added to Settings. |
| F-010: InventorySuggestionCard missing | Minor | **Wave 6**: Added as file #28. |

---

## Pipeline Continuation

After implementation (Phase 5) completes:

1. **Phase 6 (Simplify):** `simplify` skill reviews all 49 files for code quality, reuse, and efficiency.
2. **Phase 7 (Review):** `code-review` skill auto-detects .ts/.tsx/.py and runs appropriate checklist. `generate-tests` fills coverage gaps. `security-scan` checks OWASP, PII, secrets.
3. **Phase 8 (Verification):** `sdlc-verify` scores requirement coverage + test pass rate. Then `security-scan`. Then `loyalty-fraud-detection` (on fraud_check_service.py). Then `semantic-context-matching` (on context_scoring_service.py).
4. **Phase 9 (Risk):** `sdlc-risk` assesses technical, domain, operational risks.
5. **Phase 10 (PR):** `create-pr` targets `planning` branch with conventional commit format.

---

## Pre-Implementation Baseline

**Run before any file changes to establish baseline:**

```bash
# Backend baseline (expected: 0 tests, project not initialized)
pytest tests/ --co -q 2>/dev/null || echo "No tests yet (expected)"

# Frontend baseline (expected: no package.json yet)
npm test 2>/dev/null || echo "No package.json yet (expected)"

# Confirm src/ is empty
ls src/ 2>/dev/null || echo "src/ does not exist (expected for greenfield)"
```

**Baseline Test Counts (expected):**
- Backend unit: 0 passing, 0 failing
- Frontend unit: 0 passing, 0 failing
- Integration: 0
- E2E: 0

**Target (after Wave 7):**
- Backend unit: ≥ 40 passing, 0 failing, coverage ≥ 80%
- Frontend unit: ≥ 15 passing, 0 failing
- Integration: ≥ 12 passing
- E2E: ≥ 1 passing (critical path)
