# TriStar Layer Dependency Ordering

Wave assignment rules for implementation ordering in the TriStar 3-layer system.

---

## Wave Dependency Chain

```
Wave 1: src/shared/types/
    |
    v
Wave 2: src/backend/models/
    |
    v
Wave 3: src/backend/services/
    |
    v
Wave 4: src/backend/api/
    |
    v
Wave 5: src/frontend/services/
    |
    v
Wave 6: src/frontend/components/ + src/frontend/hooks/ + src/frontend/app/
    |
    v
Wave 7: tests/unit/ + tests/integration/ + tests/e2e/
```

---

## Wave 1: Shared Types (Foundation)

**Directory:** `src/shared/types/`

**Files:**
- `offer-brief.ts` - OfferBrief interface + Zod schema
- `segment.ts` - Segment type definitions
- `context-signal.ts` - Context signal types (GPS, weather, time, behavior)
- `risk-flags.ts` - Risk flag types and severity levels
- `hub-state.ts` - Hub state enum and transition types

**Dependencies:** None (this is the foundation layer)

**Verification:** TypeScript compiles, Zod schemas parse valid data and reject invalid data.

**Rule:** Changes here MUST be mirrored in Wave 2 before any other wave proceeds.

---

## Wave 2: Backend Models (Pydantic Mirror)

**Directory:** `src/backend/models/`

**Files:**
- `offer_brief.py` - OfferBrief Pydantic v2 BaseModel
- `segment.py` - Segment model
- `context_signal.py` - ContextSignal model
- `risk_flags.py` - RiskFlags model

**Dependencies:** Wave 1 (must mirror shared types exactly)

**Verification:** Pydantic models validate the same data that Zod schemas accept. Field names, types, and constraints match.

**Rule:** Run a sync check between TypeScript types and Pydantic models before proceeding to Wave 3.

---

## Wave 3: Backend Services (Business Logic)

**Directory:** `src/backend/services/`

**Files:**
- `offer_generator.py` - Claude API integration for OfferBrief generation
- `fraud_detector.py` - Fraud detection pipeline (over_discounting, cannibalization, frequency_abuse, offer_stacking)
- `context_matcher.py` - Context signal scoring engine (GPS, time, weather, behavior)
- `hub_state_manager.py` - Hub state machine transitions
- `notification_service.py` - Rate-limited notification delivery
- `claude_api.py` - Claude API client wrapper (in `src/backend/utils/`)

**Dependencies:** Wave 2 (uses Pydantic models for input/output)

**Verification:** Unit tests pass for each service with mocked external dependencies.

**Key Implementation Constraints:**
- All functions must be async
- Claude API calls: 3 retries with exponential backoff, 5 min TTL cache
- Fraud detector: block if ANY risk flag severity === 'critical'
- Context matcher: activate only if composite score > 60
- Hub state manager: atomic transitions, no race conditions
- Notification service: 1/hr/member, 24h dedup, quiet hours 10pm-8am

---

## Wave 4: Backend API Routes (HTTP Layer)

**Directory:** `src/backend/api/`

**Files:**
- `designer.py` - POST /api/designer/generate, GET /api/designer/offers
- `hub.py` - GET /api/hub/offers, PUT /api/hub/offers/{id}/status, GET /api/hub/audit/{id}
- `scout.py` - POST /api/scout/evaluate, POST /api/scout/activate

**Dependencies:** Wave 3 (calls service functions via Depends())

**Verification:** Route tests pass with mocked services. Status codes correct. Pydantic validation works.

**Key Implementation Constraints:**
- All routes async (async def)
- Dependency injection via Depends()
- JWT authentication on protected routes
- Rate limiting on public endpoints
- Custom exception handlers for domain errors
- Response models specified for OpenAPI docs

---

## Wave 5: Frontend Services (API Clients)

**Directory:** `src/frontend/services/`

**Files:**
- `api.ts` - Base API client (fetch wrapper with auth headers)
- `designer-api.ts` - Designer endpoint client functions
- `hub-api.ts` - Hub endpoint client functions
- `scout-api.ts` - Scout endpoint client functions

**Dependencies:** Wave 4 (API contracts must be finalized)

**Verification:** TypeScript compiles. API client functions match backend endpoint signatures.

**Key Implementation Constraints:**
- Use fetch API (not axios) for Next.js compatibility
- Include JWT token in Authorization header
- Handle error responses consistently
- Type-safe request/response with shared types from Wave 1

---

## Wave 6: Frontend Components (UI Layer)

**Directory:** `src/frontend/components/`, `src/frontend/hooks/`, `src/frontend/app/`

**Files (Components):**
- `components/Designer/OfferBriefForm.tsx` - Client Component (interactive form)
- `components/Designer/RiskFlagDisplay.tsx` - Server or Client Component
- `components/Hub/OfferList.tsx` - Server Component (data display)
- `components/Hub/StatusBadge.tsx` - Server Component (status indicator)
- `components/Scout/ContextDashboard.tsx` - Client Component (real-time updates)
- `components/Scout/ActivationLog.tsx` - Server Component (log display)

**Files (Hooks):**
- `hooks/useOfferValidation.ts` - Zod validation hook
- `hooks/useContextMatcher.ts` - Context matching hook

**Files (Pages):**
- `app/designer/page.tsx` - Designer page (Server Component)
- `app/designer/actions.ts` - Server Actions for designer
- `app/hub/page.tsx` - Hub page (Server Component)
- `app/scout/page.tsx` - Scout page (Server Component)

**Dependencies:** Wave 5 (uses API client functions)

**Verification:** Components render correctly. Forms validate input. Server Components fetch data. Client Components handle interaction.

**Key Implementation Constraints:**
- Server Components default (no 'use client' unless needed)
- React.use() for data fetching (not useEffect)
- useOptimistic for instant-feeling state changes
- Suspense boundaries around async components
- Tailwind CSS for styling
- ARIA labels on interactive elements

---

## Wave 7: Tests (Verification Layer)

**Directory:** `tests/`

**Files (Unit - Frontend):**
- `tests/unit/frontend/components/Designer/OfferBriefForm.test.tsx`
- `tests/unit/frontend/components/Hub/OfferList.test.tsx`
- `tests/unit/frontend/services/api.test.ts`

**Files (Unit - Backend):**
- `tests/unit/backend/services/test_offer_generator.py`
- `tests/unit/backend/services/test_fraud_detector.py`
- `tests/unit/backend/services/test_context_matcher.py`
- `tests/unit/backend/models/test_offer_brief.py`

**Files (Integration):**
- `tests/integration/test_designer_api.py`
- `tests/integration/test_hub_api.py`
- `tests/integration/test_scout_api.py`

**Files (E2E):**
- `tests/e2e/designer-flow.spec.ts`
- `tests/e2e/scout-flow.spec.ts`

**Dependencies:** Waves 1-6 (tests the implementation)

**Verification:** All tests pass. Coverage > 80%. Integration tests verify cross-layer flows.

**Key Implementation Constraints:**
- Jest + React Testing Library for frontend
- pytest + httpx AsyncClient for backend
- Playwright for E2E
- Mock Claude API, Weather API, Redis in unit tests
- Use freezegun for time-dependent tests (quiet hours, expiry)
- Test naming: test_<what>_when_<condition>_then_<expected>

---

## Implementation Constraints from Scoped Rules

Each wave must follow the coding standards defined in `.claude/rules/`:

| Rule File | Applies To | Key Constraints |
|-----------|-----------|-----------------|
| `react-19-standards.md` | Waves 5-6 | Server Components default, React.use(), useOptimistic |
| `fastapi-standards.md` | Waves 3-4 | async/await, Depends(), Pydantic v2, lifespan |
| `code-style.md` | All waves | PascalCase components, snake_case Python, 100 char lines |
| `testing.md` | Wave 7 | >80% coverage, Given/When/Then, mock externals |
| `security.md` | All waves | member_id only, Zod+Pydantic validation, no secrets in code |

---

## Cross-Wave Sync Points

These are moments where multiple waves must be verified together:

1. **Wave 1+2 Sync**: Zod schemas and Pydantic models must define identical fields
2. **Wave 3+4 Sync**: Service interfaces must match route handler expectations
3. **Wave 4+5 Sync**: Backend API contracts must match frontend API client calls
4. **Wave 1+6 Sync**: Frontend components must use shared types correctly
5. **Wave 3+7 Sync**: Unit tests must cover all service edge cases
