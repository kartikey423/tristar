# TriStar Architectural Patterns

Canonical patterns that define TriStar's architecture. All new features must conform to these patterns unless an ADR explicitly justifies deviation.

---

## Pattern 1: 3-Layer Architecture

**Rule:** Designer (Claude API copilot) -> Hub (state store) -> Scout (activation engine). All inter-layer communication flows through Hub. No direct Designer->Scout bypass.

**Designer (Layer 1):**
- Receives business objectives from marketers
- Calls Claude API (claude-sonnet-4-6) to generate structured OfferBrief
- Runs fraud detection pre-check before sending to Hub
- Frontend: React 19 + Next.js 15 marketer copilot UI
- Backend: FastAPI routes in `src/backend/api/designer.py`

**Hub (Layer 2):**
- Central state store for all offers
- Manages offer lifecycle (draft -> approved -> active -> expired)
- Dev: Python dict in memory. Prod: Azure Redis Cache
- Provides query interface for both Designer and Scout
- Backend: FastAPI routes in `src/backend/api/hub.py`

**Scout (Layer 3):**
- Real-time activation engine
- Ingests context signals (GPS, time, weather, behavior)
- Scores offers against context (0-100, activate if >60)
- Delivers notifications respecting rate limits
- Backend: FastAPI routes in `src/backend/api/scout.py`

**Communication Rule:** Designer writes to Hub. Scout reads from Hub. Designer never talks directly to Scout. If a feature seems to require Designer->Scout communication, it must go through Hub state.

---

## Pattern 2: OfferBrief Contract

**Rule:** TypeScript types (Zod validated) in `src/shared/types/` are the single source of truth. Pydantic v2 models in `src/backend/models/` must mirror them exactly.

**Frontend (Source of Truth):**
```
src/shared/types/offer-brief.ts
- Zod schema for runtime validation
- TypeScript interface for compile-time checks
- Exported for use by all frontend components
```

**Backend (Mirror):**
```
src/backend/models/offer_brief.py
- Pydantic v2 BaseModel mirroring the TypeScript interface
- Field validators matching Zod constraints
- Used for API request/response validation
```

**Change Protocol:** Any change to OfferBrief MUST update both files simultaneously. A PR that changes one without the other must be rejected.

**Core Fields:**
- `offer_id: string` - UUID, immutable after creation
- `objective: string` - Business objective (10-500 chars)
- `segment: Segment` - Target segment definition
- `construct: Construct` - Offer mechanics (type, value, description)
- `channels: Channel[]` - Delivery channels with priority
- `kpis: KPIs` - Expected performance metrics
- `risk_flags: RiskFlags` - Fraud detection results
- `status: Status` - Lifecycle state (draft/approved/active/expired)
- `created_at: DateTime` - Creation timestamp

---

## Pattern 3: Hub State Machine

**Rule:** Atomic state transitions with no race conditions. Every transition must be validated.

**States:**
- `draft` - Initial state after Designer generates OfferBrief
- `approved` - Fraud check passed, marketer approved
- `active` - Activation rules met (context score > 60), offer is live
- `expired` - Time-based expiry or redemption limit reached

**Valid Transitions:**
```
draft -> approved     (requires: fraud check pass + marketer approval)
approved -> active    (requires: context score > 60, no critical risk flags)
active -> expired     (requires: time expiry OR redemption limit reached)
draft -> expired      (requires: marketer cancellation OR timeout)
approved -> expired   (requires: marketer cancellation OR activation window passed)
```

**Invalid Transitions (must be rejected):**
```
approved -> draft     (no reverting approval)
active -> approved    (no deactivating to approved)
active -> draft       (no reverting active offers)
expired -> *          (terminal state, no transitions out)
```

**Concurrency:** Hub must use atomic operations (Redis WATCH/MULTI or in-memory locks) to prevent race conditions on state transitions.

---

## Pattern 4: Context Signal Scoring

**Rule:** GPS proximity, time/day, weather, and member behavior each score 0-100. Weighted average determines activation. Activate when composite score > 60.

**Signal Weights (default):**
| Signal | Weight | Score Range |
|--------|--------|-------------|
| GPS Proximity | 30% | 0-100 (100 = <500m, 0 = >5km) |
| Time/Day | 25% | 0-100 (100 = peak hours for segment) |
| Weather | 20% | 0-100 (100 = ideal conditions for offer) |
| Member Behavior | 25% | 0-100 (100 = high engagement, recent activity) |

**GPS Scoring:**
- < 500m: score 100
- 500m - 1km: score 80
- 1km - 2km: score 50
- 2km - 5km: score 20
- > 5km: score 0

**Fallback:** If a signal is unavailable, exclude it from weighted average and redistribute weight proportionally among remaining signals.

---

## Pattern 5: Fraud Detection Pipeline

**Rule:** Pre-approval check runs before any offer can transition from draft to approved. Critical severity blocks the transition.

**Risk Flags:**
- `over_discounting`: Discount exceeds 30% of item value. Severity: warning (20-30%), critical (>30%)
- `cannibalization`: New offer competes with existing active offer for the same segment. Severity: warning (partial overlap), critical (full overlap)
- `frequency_abuse`: Member would receive more than 3 offers per day. Severity: warning (3/day), critical (>5/day)
- `offer_stacking`: Member has more than 2 concurrent active offers. Severity: warning (2 active), critical (>3 active)

**Blocking Rule:** If ANY risk flag has severity === 'critical', the transition from draft to approved MUST be blocked. The marketer sees the risk flags and must modify the offer before re-submitting.

---

## Pattern 6: Rate Limiting

**Rule:** Protect members from notification spam. Enforce at Scout layer before delivery.

**Limits:**
- **Per-member frequency**: Maximum 1 notification per member per hour
- **Deduplication**: No duplicate offers to the same member within 24 hours
- **Quiet hours**: No notifications between 10pm and 8am (member's local timezone)

**Queue Behavior:**
- If rate limited, queue the notification for delivery when the window opens
- If quiet hours, queue for 8am next day
- If duplicate within 24h, discard silently (log for audit)

---

## Pattern 7: Shared Types Strategy

**Rule:** TypeScript interfaces (frontend) + Pydantic BaseModel (backend). Changes to shared types must update both simultaneously.

**Frontend types location:** `src/shared/types/`
- `offer-brief.ts` - OfferBrief, Segment, Construct, Channel, KPIs, RiskFlags
- Runtime validation: Zod schemas
- Compile-time validation: TypeScript strict mode

**Backend models location:** `src/backend/models/`
- `offer_brief.py` - Matching Pydantic v2 models
- Runtime validation: Pydantic Field validators
- API documentation: auto-generated from models

**Sync Check:** CI pipeline should verify that TypeScript interfaces and Pydantic models define the same fields with compatible types.

---

## Pattern 8: Server Components Default

**Rule:** React 19 Server Components are the default. Client Components ('use client') only when interactivity is required.

**Server Components (default):**
- Page layouts (`app/*/page.tsx`)
- Data display components (OfferList, StatusBadge)
- Static content (headers, footers, navigation)

**Client Components ('use client'):**
- Forms (OfferBriefForm)
- Interactive elements (approval buttons, filters)
- Components using hooks (useState, useEffect, useOptimistic)
- Components using browser APIs

**Data Fetching:**
- Server Components: direct async/await in component body
- Client Components: React.use() with Suspense boundary
- Never useEffect for data fetching

---

## Pattern 9: Async-First Backend

**Rule:** All FastAPI routes use async/await. No blocking synchronous operations in async contexts.

**Route Pattern:**
```
async def route_handler(
    request: RequestModel,
    db: AsyncSession = Depends(get_db),
    service: Service = Depends(get_service),
) -> ResponseModel:
```

**Dependency Injection:** Use FastAPI's `Depends()` for all service dependencies. Never instantiate services directly in route handlers.

**Logging:** Structured JSON logging with loguru. Always include context (member_id, offer_id, operation). Never include PII.

**Error Handling:** Custom exception classes mapped to HTTP status codes via global exception handlers. Never return raw exceptions to clients.

---

## Pattern 10: Azure Deployment

**Rule:** Each layer maps to Azure services with appropriate security boundaries.

| Component | Azure Service | Configuration |
|-----------|--------------|---------------|
| Frontend | Azure App Service | Next.js 15, CORS restricted |
| Backend API | Azure Functions | FastAPI, managed identity |
| Hub State | Azure Redis Cache | Encrypted connections |
| Persistence | Azure SQL Database | Parameterized queries, encrypted at rest |
| Secrets | Azure Key Vault | All API keys and credentials |
| Static Assets | Azure CDN | Cache-Control headers |

**Security Boundaries:**
- Frontend can only call Backend API (no direct database/Redis access)
- Backend uses managed identity for Azure services (no stored credentials)
- Redis requires TLS connections
- SQL Database requires parameterized queries only
- Key Vault accessed via managed identity, never hardcoded
