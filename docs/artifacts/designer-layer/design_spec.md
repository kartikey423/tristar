# Design Specification: designer-layer

## Meta

| Field | Value |
|-------|-------|
| **Feature Name** | designer-layer |
| **Problem Spec Ref** | `docs/artifacts/designer-layer/problem_spec.md` |
| **Created** | 2026-03-27 |
| **Author** | SDLC Architecture Skill |
| **Status** | Proposed |
| **Revision** | 1.0 |

---

## Problem Spec Reference

This design addresses all requirements from `problem_spec.md`:

| Req | Description | Priority | Addressed By |
|-----|-------------|----------|--------------|
| REQ-001 | AI-Driven Inventory Analysis | P0 | COMP-005, COMP-010 |
| REQ-002 | Claude API Integration | P0 | COMP-004, COMP-009 |
| REQ-003 | Fraud Detection Integration | P0 | COMP-006 |
| REQ-004 | Hub Integration for Approved Offers | P0 | COMP-007, COMP-011 |
| REQ-005 | JWT Auth + RBAC | P0 | COMP-003, COMP-013 |
| REQ-006 | Dual-Mode Offer Creation | P0 | COMP-009, COMP-010, COMP-014 |
| REQ-007 | Frontend Designer UI | P0 | COMP-008–COMP-016 |
| REQ-008 | Purchase-Triggered Offer Generation | P0 | COMP-018–COMP-021 |
| REQ-009 | Context Signal Scoring | P0 | COMP-019 |
| REQ-010 | Delivery Constraints | P0 | COMP-020, COMP-021 |
| REQ-011 | Purchase Event Data Integration | P0 | COMP-017, COMP-018 |
| REQ-012 | Caching for Duplicate Objectives | P1 | COMP-004 |
| REQ-013 | Audit Logging | P1 | COMP-022 |
| REQ-014 | Risk Flag Visual Indicators | P1 | COMP-015 |
| REQ-015 | Purchase-Triggered Monitoring Dashboard | P1 | COMP-016 |
| REQ-016 | Partner Store Effectiveness Tracking | P1 | COMP-022 |

---

## Current Architecture

### Baseline State (Greenfield)

TriStar is a greenfield project. No source code exists. The architecture defined here establishes the initial implementation following these existing artifacts:

- `docs/ARCHITECTURE.md` — System overview, Mermaid diagrams, component topology
- `.claude/CLAUDE.md` — Technology stack: React 19 + Next.js 15 (frontend), FastAPI + Pydantic v2 (backend)
- `.claude/rules/` — Coding standards for React 19, FastAPI, security, testing, code style

### Existing Constraints from Architecture Doc

- **3-layer pattern** enforced: Designer → Hub → Scout, no bypasses
- **Hub state machine**: `draft → approved → active → expired` (all valid transitions defined)
- **OfferBrief contract**: Shared TypeScript/Pydantic schema
- **Context scoring threshold**: > 60 for standard activation (> 70 for purchase-triggered per requirements)
- **Rate limits**: 1 notification/member/hour, no duplicates in 24h, quiet hours 10pm–8am

### New Additions in This Feature

The designer-layer introduces two new inter-layer flows that extend the baseline architecture:

1. **Standard flow** (marketer-initiated): Marketer → Designer UI → Claude API → Fraud Check → Hub save
2. **Purchase-triggered flow** (new): Rewards system → Purchase Event → Scout context scoring → Designer API → Claude API → Hub save → Scout activation

The purchase-triggered flow introduces a **Scout → Designer call** which appears to violate the 3-layer rule. See ADR-001 for the justification of this pattern through Hub intermediation.

---

## Architecture

### System Topology (Designer Layer)

```
┌──────────────────────────────────────────────────────────────┐
│                    DESIGNER LAYER (Layer 1)                   │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   Next.js 15 Frontend                   │ │
│  │                                                         │ │
│  │  /designer (page.tsx - Server Component)                │ │
│  │  ├── ModeSelectorTabs (Client Component)                │ │
│  │  ├── AISuggestionsPanel (Server Component)              │ │
│  │  │   └── InventorySuggestionCard (Server Component)    │ │
│  │  ├── ManualEntryForm (Client Component)                 │ │
│  │  ├── OfferBriefCard (Server Component)                  │ │
│  │  │   └── RiskFlagBadge (Server Component)              │ │
│  │  └── DesignerDashboard (Server Component) [P1]          │ │
│  └─────────────────────────────────────────────────────────┘ │
│                          │ HTTP/JSON                          │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │                   FastAPI Backend                       │ │
│  │                                                         │ │
│  │  /api/designer/*                                        │ │
│  │  ├── POST /generate          (marketer-initiated)       │ │
│  │  ├── POST /generate-purchase (purchase-triggered)       │ │
│  │  ├── POST /approve/{offer_id}                          │ │
│  │  ├── GET  /suggestions       (inventory-based)          │ │
│  │  └── GET  /dashboard         (P1 monitoring)            │ │
│  │                                                         │ │
│  │  Services:                                              │ │
│  │  ├── ClaudeApiService        (offer generation)         │ │
│  │  ├── InventoryService        (mock CSV/JSON loader)     │ │
│  │  ├── FraudCheckService       (skill integration)        │ │
│  │  ├── HubApiClient            (saves to Hub)             │ │
│  │  └── AuditLogService         (compliance logging) [P1]  │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
         │                                    │
         │ POST /api/hub/offers               │ Webhook/Event
         ▼                                    │
┌─────────────────┐               ┌───────────────────────────┐
│   HUB (Layer 2) │               │     SCOUT (Layer 3)       │
│                 │◄──────────────│                           │
│  offer lifecycle│  read active  │  Purchase Event Listener  │
│  draft→approved │  offers       │  ContextScoringService    │
│  approved→active│               │  NotificationService      │
└─────────────────┘               └───────────────────────────┘
         ▲
         │ POST /api/hub/offers (status=active)
         │ (purchase-triggered path only)
         │
┌─────────────────────────────────┐
│  POST /api/designer/generate-purchase
│  (Scout calls Designer when score > 70)
└─────────────────────────────────┘
```

### Purchase-Triggered Flow Detail

```
Rewards System
     │
     │ POST /api/scout/purchase-event
     │ {member_id, store_id, amount, category, location, timestamp}
     ▼
Scout: PurchaseEventHandler
     │
     │ gather context signals
     │ (member history, nearby stores, weather)
     ▼
Scout: ContextScoringService
     │ score = Σ(purchase_value + proximity + affinity + frequency + weather)
     │
     ├─── score ≤ 70 ──► log "below threshold", discard
     │
     └─── score > 70 ──► POST /api/designer/generate-purchase
                              │
                         Designer: PurchaseTriggerController
                              │
                              ├── validate rate limits (6h per member)
                              ├── check quiet hours (10pm–8am)
                              │
                              ├── call ClaudeApiService (context-enriched prompt)
                              │
                              ├── call FraudCheckService
                              │     ├── severity=critical → BLOCK, return 422
                              │     └── severity<critical → proceed
                              │
                              └── POST /api/hub/offers (status=active)
                                       │
                                  Hub saves offer
                                       │
                              return {offer_id, status=active}
                                       │
                         Scout: NotificationService
                              │
                              └── push notification to member (< 2min SLA)
```

---

## Component Catalogue

### Shared Layer

#### COMP-001: OfferBrief TypeScript Schema
- **Path:** `src/shared/types/offer-brief.ts`
- **Layer:** Shared
- **Responsibility:** Single source of truth for OfferBrief schema. Defines TypeScript interfaces and Zod validators for all OfferBrief fields.
- **Dependencies:** None (foundational)
- **Interface:**
  ```
  export const OfferBriefSchema: ZodSchema
  export interface OfferBrief { offer_id, objective, segment, construct, channels, kpis, risk_flags, status, created_at, trigger_type }
  export interface Segment { name, definition, estimated_size, criteria, exclusions }
  export interface Construct { type, value, description, valid_from, valid_until }
  export interface Channel { channel_type, priority, delivery_rules }
  export interface KPIs { expected_redemption_rate, expected_uplift_pct, estimated_cost_per_redemption, roi_projection, target_reach }
  export interface RiskFlags { over_discounting, cannibalization, frequency_abuse, offer_stacking, warnings, severity }
  export type OfferStatus = 'draft' | 'approved' | 'active' | 'expired'
  export type TriggerType = 'marketer_initiated' | 'purchase_triggered'
  ```

#### COMP-002: OfferBrief Pydantic Model
- **Path:** `src/backend/models/offer_brief.py`
- **Layer:** Shared (backend mirror)
- **Responsibility:** Pydantic v2 mirror of COMP-001. Used for API request/response validation on backend.
- **Dependencies:** None (foundational)
- **Interface:**
  ```python
  class OfferBrief(BaseModel)
  class Segment(BaseModel)
  class Construct(BaseModel)
  class Channel(BaseModel)
  class KPIs(BaseModel)
  class RiskFlags(BaseModel)
  class OfferStatus(str, Enum): draft, approved, active, expired
  class TriggerType(str, Enum): marketer_initiated, purchase_triggered
  ```

#### COMP-003: JWT Auth Middleware
- **Path:** `src/backend/core/security.py`
- **Layer:** Shared (backend)
- **Responsibility:** JWT token validation and RBAC enforcement. Extracts user_id and role from token. Rejects non-marketing users from Designer endpoints.
- **Dependencies:** None
- **Interface:**
  ```python
  async def get_current_user(credentials: HTTPAuthCredentials) -> AuthUser
  async def require_marketing_role(user: AuthUser) -> AuthUser
  class AuthUser(BaseModel): user_id, role, email
  ```

### Backend — Designer API

#### COMP-004: ClaudeApiService
- **Path:** `src/backend/services/claude_api.py`
- **Layer:** Designer (Backend)
- **Responsibility:** Wraps Anthropic SDK. Builds structured prompts for marketer-initiated and purchase-triggered contexts. Handles retry with exponential backoff (3 attempts, 1s/2s/4s). Implements 5-minute TTL cache for identical objectives.
- **Dependencies:** COMP-002 (OfferBrief model), COMP-023 (Settings)
- **Interface:**
  ```python
  async def generate_from_objective(objective: str, segments: list[str]) -> OfferBrief
  async def generate_from_purchase_context(context: PurchaseContext) -> OfferBrief
  async def _build_marketer_prompt(objective: str, inventory: list[InventoryItem]) -> str
  async def _build_purchase_prompt(context: PurchaseContext) -> str
  async def _call_with_retry(prompt: str, max_attempts: int = 3) -> str
  async def _parse_offer_brief(raw_response: str) -> OfferBrief
  ```

#### COMP-005: InventoryService
- **Path:** `src/backend/services/inventory_service.py`
- **Layer:** Designer (Backend)
- **Responsibility:** Loads and queries mock inventory data (CSV/JSON). Provides top-N suggestions based on stock levels. Identifies overstock (>500 units) and low-stock (<50 units) items.
- **Dependencies:** COMP-023 (Settings — inventory file path)
- **Interface:**
  ```python
  async def get_suggestions(limit: int = 3) -> list[InventorySuggestion]
  async def get_item(product_id: str) -> InventoryItem | None
  async def get_overstock_items(threshold: int = 500) -> list[InventoryItem]
  class InventoryItem(BaseModel): product_id, name, stock_level, category, store_id, unit_cost
  class InventorySuggestion(BaseModel): item, suggested_objective, urgency_level
  ```

#### COMP-006: FraudCheckService
- **Path:** `src/backend/services/fraud_check_service.py`
- **Layer:** Designer (Backend)
- **Responsibility:** Integrates with the `loyalty-fraud-detection` skill. Evaluates over-discounting, cannibalization, frequency_abuse, offer_stacking. Returns risk severity. Blocks auto-save if critical.
- **Dependencies:** COMP-002 (OfferBrief), Hub API (for active offer count)
- **Interface:**
  ```python
  async def validate(offer: OfferBrief, member_id: str | None = None) -> FraudCheckResult
  class FraudCheckResult(BaseModel): severity, flags, warnings, blocked
  ```

#### COMP-007: HubApiClient
- **Path:** `src/backend/services/hub_api_client.py`
- **Layer:** Designer (Backend)
- **Responsibility:** HTTP client for Hub API. Saves approved offers (marketer-initiated: status=approved, purchase-triggered: status=active). Handles Hub API errors with retry.
- **Dependencies:** COMP-002 (OfferBrief), COMP-023 (Settings — hub URL)
- **Interface:**
  ```python
  async def save_offer(offer: OfferBrief) -> HubSaveResult
  async def get_offer(offer_id: str) -> OfferBrief | None
  class HubSaveResult(BaseModel): offer_id, status, hub_url
  ```

#### COMP-008: Designer API Router
- **Path:** `src/backend/api/designer.py`
- **Layer:** Designer (Backend)
- **Responsibility:** FastAPI router for all /api/designer/* endpoints. Orchestrates ClaudeApiService, FraudCheckService, HubApiClient. Enforces JWT auth + marketing role via dependency injection.
- **Dependencies:** COMP-003, COMP-004, COMP-005, COMP-006, COMP-007, COMP-022
- **Interface (endpoints):**
  ```
  POST /api/designer/generate          → GenerateOfferResponse
  POST /api/designer/generate-purchase → GeneratePurchaseResponse
  POST /api/designer/approve/{offer_id}→ ApproveOfferResponse
  GET  /api/designer/suggestions        → SuggestionsResponse
  GET  /api/designer/dashboard          → DashboardResponse [P1]
  ```

### Backend — Scout Purchase-Triggered Flow

#### COMP-017: PurchaseEventRouter
- **Path:** `src/backend/api/scout.py` (extended)
- **Layer:** Scout (Backend)
- **Responsibility:** Receives purchase events from rewards system webhook. Validates payload completeness. Filters refunds (negative amounts). Publishes to internal processing queue.
- **Dependencies:** COMP-018, COMP-023
- **Interface:**
  ```
  POST /api/scout/purchase-event → PurchaseEventAck
  ```

#### COMP-018: PurchaseEventHandler
- **Path:** `src/backend/services/purchase_event_handler.py`
- **Layer:** Scout (Backend)
- **Responsibility:** Processes validated purchase events. Enriches with member history, nearby stores, weather data. Deduplicates split transactions within 60-second window.
- **Dependencies:** COMP-019, COMP-023
- **Interface:**
  ```python
  async def handle(event: PurchaseEvent) -> PurchaseContext
  async def _enrich_with_member_history(member_id: str) -> MemberProfile
  async def _find_nearby_ctc_stores(lat: float, lon: float, radius_km: float) -> list[NearbyStore]
  async def _get_weather(lat: float, lon: float) -> WeatherConditions
  class PurchaseEvent(BaseModel): member_id, store_id, store_name, store_type, location, amount, category, items, timestamp
  class PurchaseContext(BaseModel): purchase_event, member_profile, nearby_stores, weather, scored_at
  ```

#### COMP-019: ContextScoringService
- **Path:** `src/backend/services/context_scoring_service.py`
- **Layer:** Scout (Backend)
- **Responsibility:** Scores purchase context across 7 factors to determine if Designer should be triggered. Returns score 0–100 with factor breakdown. Threshold: > 70 to trigger.
- **Dependencies:** COMP-018 output (PurchaseContext)
- **Interface:**
  ```python
  def score(context: PurchaseContext) -> ContextScore
  class ContextScore(BaseModel):
      total: float
      breakdown: dict[str, float]  # {purchase_value, proximity, frequency, affinity, partner_crosssell, weather, time}
      should_trigger: bool  # total > 70
  ```
  **Scoring factors:**
  - `purchase_value`: >$50 = 20pts, $20–$50 = 10pts, <$20 = 5pts
  - `proximity`: CTC store <1km = 25pts, 1–2km = 15pts, >2km = 0pts
  - `frequency`: 2+ purchases this week = 15pts, 1 = 10pts, first in 30d = 5pts
  - `affinity`: Top-3 category match = 20pts, top-10 = 10pts, no match = 5pts
  - `partner_crosssell`: Purchase at partner (Tim Hortons, Westside) = 15pts bonus
  - `weather`: Conditions match offer category = 10pts
  - `time`: Within member's shopping hours = 5pts

#### COMP-020: DeliveryConstraintService
- **Path:** `src/backend/services/delivery_constraint_service.py`
- **Layer:** Scout (Backend)
- **Responsibility:** Enforces rate limits (1 per member per 6h), deduplication (24h window unless >$100 purchase), quiet hours (10pm–8am queue), notification preferences. Manages queued notifications for 8am delivery.
- **Dependencies:** Hub API (check recent offers for member), COMP-023
- **Interface:**
  ```python
  async def can_deliver(member_id: str, purchase_amount: float) -> DeliveryDecision
  async def queue_for_morning(member_id: str, offer_id: str) -> None
  class DeliveryDecision(BaseModel): allowed, reason, deliver_at  # None = now, datetime = queued
  ```

#### COMP-021: NotificationService
- **Path:** `src/backend/services/notification_service.py`
- **Layer:** Scout (Backend)
- **Responsibility:** Sends push notifications to members with 2-minute SLA. Retries 3 times on failure. Falls back to email after 3 failed push attempts. Marks offers with 4-hour urgency.
- **Dependencies:** COMP-023 (notification provider settings)
- **Interface:**
  ```python
  async def send_push(member_id: str, offer: OfferBrief) -> NotificationResult
  async def send_email_fallback(member_id: str, offer: OfferBrief) -> NotificationResult
  class NotificationResult(BaseModel): delivered, channel, attempted_at, delivered_at
  ```

### Backend — Shared Services

#### COMP-022: AuditLogService
- **Path:** `src/backend/services/audit_log_service.py`
- **Layer:** Shared (Backend)
- **Responsibility:** Structured compliance logging. Logs offer generation events with trigger_type, offer_id, marketer_id/system, timestamp. Scrubs PII from objectives before writing.
- **Dependencies:** COMP-023
- **Interface:**
  ```python
  async def log_generation(offer_id: str, trigger_type: TriggerType, actor_id: str, objective: str) -> None
  async def log_approval(offer_id: str, actor_id: str) -> None
  async def log_delivery(offer_id: str, member_id: str, channel: str, result: str) -> None
  async def log_fraud_block(offer_id: str, severity: str, flags: list[str]) -> None
  def _scrub_pii(text: str) -> str  # removes emails, names, phone numbers
  ```

#### COMP-023: Settings
- **Path:** `src/backend/core/config.py`
- **Layer:** Shared (Backend)
- **Responsibility:** Pydantic-settings config loaded from .env. Single source of all environment variables.
- **Dependencies:** None
- **Interface:**
  ```python
  class Settings(BaseSettings):
      CLAUDE_API_KEY: str
      HUB_API_URL: str
      INVENTORY_FILE_PATH: str
      JWT_SECRET: str
      WEATHER_API_KEY: str
      NOTIFICATION_PROVIDER_URL: str
      QUIET_HOURS_START: int = 22
      QUIET_HOURS_END: int = 8
      PURCHASE_TRIGGER_SCORE_THRESHOLD: float = 70.0
      PURCHASE_TRIGGER_RATE_LIMIT_HOURS: int = 6
      CACHE_TTL_SECONDS: int = 300
  ```

### Frontend — Designer UI

#### COMP-009: Designer Page
- **Path:** `src/frontend/app/designer/page.tsx`
- **Layer:** Designer (Frontend)
- **Responsibility:** Root Server Component for /designer route. Fetches inventory suggestions server-side. Renders layout with ModeSelectorTabs, AISuggestionsPanel, ManualEntryForm.
- **Dependencies:** COMP-010, COMP-011, COMP-012, COMP-016
- **Interface:** `export default async function DesignerPage()`

#### COMP-010: AISuggestionsPanel
- **Path:** `src/frontend/components/Designer/AISuggestionsPanel.tsx`
- **Layer:** Designer (Frontend)
- **Responsibility:** Server Component. Fetches top-3 inventory suggestions via GET /api/designer/suggestions. Renders suggestion cards with product details and suggested objectives.
- **Dependencies:** COMP-016 (API service), COMP-001 (types)
- **Interface:** `export function AISuggestionsPanel({ suggestions }: Props)`

#### COMP-011: ManualEntryForm
- **Path:** `src/frontend/components/Designer/ManualEntryForm.tsx`
- **Layer:** Designer (Frontend)
- **Responsibility:** Client Component ('use client'). Textarea for business objective (10–500 chars). Zod validation on submit. Posts to POST /api/designer/generate. Shows loading state via useFormStatus. Displays result in OfferBriefCard.
- **Dependencies:** COMP-001 (Zod schema), COMP-016 (API service)
- **Interface:** `export function ManualEntryForm({ onResult }: Props)`

#### COMP-012: ModeSelectorTabs
- **Path:** `src/frontend/components/Designer/ModeSelectorTabs.tsx`
- **Layer:** Designer (Frontend)
- **Responsibility:** Client Component. Tab switcher between "AI Suggestions" and "Manual Entry" modes. Uses useState for selected mode. Renders appropriate child panel.
- **Dependencies:** COMP-010, COMP-011
- **Interface:** `export function ModeSelectorTabs()`

#### COMP-013: OfferBriefCard
- **Path:** `src/frontend/components/Designer/OfferBriefCard.tsx`
- **Layer:** Designer (Frontend)
- **Responsibility:** Server Component. Displays all OfferBrief fields (segment, construct, channels, kpis) in structured card layout. Includes RiskFlagBadge and ApproveButton sub-components.
- **Dependencies:** COMP-001 (types), COMP-014, COMP-015
- **Interface:** `export function OfferBriefCard({ offer }: { offer: OfferBrief })`

#### COMP-014: ApproveButton
- **Path:** `src/frontend/components/Designer/ApproveButton.tsx`
- **Layer:** Designer (Frontend)
- **Responsibility:** Client Component. Approval button disabled when severity='critical'. Calls POST /api/designer/approve/{offer_id}. Uses useOptimistic for instant status update. Shows error if Hub save fails.
- **Dependencies:** COMP-001 (types), COMP-016 (API service)
- **Interface:** `export function ApproveButton({ offerId, riskSeverity }: Props)`

#### COMP-015: RiskFlagBadge
- **Path:** `src/frontend/components/Designer/RiskFlagBadge.tsx`
- **Layer:** Designer (Frontend)
- **Responsibility:** Server Component. Color-coded badge for fraud detection severity. Red/icon for critical, yellow for medium, gray for low. Lists active risk flags.
- **Dependencies:** COMP-001 (RiskFlags type)
- **Interface:** `export function RiskFlagBadge({ riskFlags }: { riskFlags: RiskFlags })`

#### COMP-016: Designer API Service
- **Path:** `src/frontend/services/designer-api.ts`
- **Layer:** Designer (Frontend)
- **Responsibility:** Type-safe HTTP client for Designer backend. Handles auth headers (JWT from cookie/header). Maps API responses to TypeScript types. Centralises error handling.
- **Dependencies:** COMP-001 (types)
- **Interface:**
  ```typescript
  export async function generateOffer(objective: string): Promise<OfferBrief>
  export async function approveOffer(offerId: string): Promise<ApproveResult>
  export async function getInventorySuggestions(): Promise<InventorySuggestion[]>
  export async function getDashboard(): Promise<DashboardData>
  ```

---

## API Contracts

### POST /api/designer/generate

**Description:** Generate OfferBrief from business objective (marketer-initiated)

**Authentication:** Bearer JWT, role=marketing

**Rate Limit:** 10 req/min per user

**Request:**
```json
{
  "objective": "Reactivate lapsed high-value members before summer season",
  "segment_hints": ["lapsed_90_days", "high_value"]
}
```

**Request Model (Pydantic):**
```python
class GenerateOfferRequest(BaseModel):
    objective: str = Field(..., min_length=10, max_length=500)
    segment_hints: list[str] = Field(default_factory=list, max_items=5)
```

**Response (201 Created):**
```json
{
  "offer": { ...OfferBrief },
  "fraud_check": {
    "severity": "low",
    "flags": [],
    "blocked": false
  },
  "cached": false,
  "generation_ms": 2340
}
```

**Error Responses:**
- `400` — Validation error (objective too short/long, invalid segment_hints)
- `401` — Missing or invalid JWT
- `403` — JWT valid but role != marketing
- `422` — Fraud detection severity=critical (offer blocked)
- `503` — Claude API unavailable after 3 retries

---

### POST /api/designer/generate-purchase

**Description:** Generate OfferBrief from purchase context (purchase-triggered, called by Scout)

**Authentication:** Bearer JWT (service-to-service token, role=system)

**Rate Limit:** 100 req/min (internal Scout calls)

**Request:**
```json
{
  "member_id": "mbr_abc123",
  "purchase_event": {
    "store_id": "tim_hortons_001",
    "store_name": "Tim Hortons - King & Bay",
    "store_type": "partner",
    "location": { "lat": 43.648, "lon": -79.383 },
    "amount": 8.50,
    "category": "food_beverage",
    "items": ["coffee", "muffin"],
    "timestamp": "2026-03-27T14:32:00Z"
  },
  "context": {
    "member_profile": {
      "segment": "high_value",
      "category_affinity": ["outdoor_gear", "automotive"],
      "last_ctc_purchase_days": 45,
      "weekly_purchase_count": 3
    },
    "nearby_ctc_stores": [
      { "store_id": "sport_chek_002", "name": "Sport Chek Union Station", "distance_km": 0.4 }
    ],
    "weather": { "temp_celsius": -8, "condition": "light_snow" },
    "context_score": 78
  }
}
```

**Request Model (Pydantic):**
```python
class PurchaseContextRequest(BaseModel):
    member_id: str
    purchase_event: PurchaseEventPayload
    context: EnrichedContext

class PurchaseEventPayload(BaseModel):
    store_id: str
    store_name: str
    store_type: Literal["ctc", "partner"]
    location: GeoPoint
    amount: float = Field(..., gt=0)
    category: str
    items: list[str]
    timestamp: datetime

class EnrichedContext(BaseModel):
    member_profile: MemberProfile
    nearby_ctc_stores: list[NearbyStore]
    weather: WeatherConditions
    context_score: float = Field(..., ge=0, le=100)
```

**Response (201 Created):**
```json
{
  "offer_id": "offer_xyz789",
  "offer": { ...OfferBrief with status=active },
  "hub_saved": true,
  "deliver_at": null
}
```

**`deliver_at` semantics:** `null` = deliver immediately, ISO timestamp = deliver at that time (quiet hours queue)

**Error Responses:**
- `400` — Invalid payload (missing fields, negative amount, refund detected)
- `401` — Missing service token
- `422` — Fraud severity=critical (generation blocked)
- `429` — Rate limit hit (member received offer within 6h)
- `503` — Claude API unavailable

---

### POST /api/designer/approve/{offer_id}

**Description:** Marketer approves an offer, transitioning it from draft → approved in Hub

**Authentication:** Bearer JWT, role=marketing

**Path Param:** `offer_id: str`

**Response (200 OK):**
```json
{
  "offer_id": "offer_abc123",
  "status": "approved",
  "hub_url": "/api/hub/offers/offer_abc123"
}
```

**Error Responses:**
- `400` — Offer has critical risk flags (cannot approve)
- `404` — offer_id not found
- `409` — Offer not in draft state (invalid transition)
- `403` — Marketer role check failed

---

### POST /api/scout/purchase-event

**Description:** Receives purchase events from the rewards system webhook

**Authentication:** Webhook secret (HMAC-SHA256 signature in X-Webhook-Signature header)

**Request:**
```json
{
  "member_id": "mbr_abc123",
  "store_id": "tim_hortons_001",
  "store_name": "Tim Hortons - King & Bay",
  "store_type": "partner",
  "location": { "lat": 43.648, "lon": -79.383 },
  "amount": 8.50,
  "category": "food_beverage",
  "items": ["coffee"],
  "timestamp": "2026-03-27T14:32:00Z",
  "is_refund": false
}
```

**Response (202 Accepted):**
```json
{ "event_id": "evt_001", "status": "processing" }
```

**Validation Rules:**
- Reject if `is_refund = true`
- Reject if `amount <= 0`
- Reject if `member_id` is missing
- Accept if any non-required field is missing (partial data → COMP-018 handles gracefully)

---

### GET /api/designer/suggestions

**Description:** Returns top-3 AI-recommended offer suggestions based on inventory

**Authentication:** Bearer JWT, role=marketing

**Response (200 OK):**
```json
{
  "suggestions": [
    {
      "product_id": "prod_001",
      "product_name": "Men's Winter Parka",
      "stock_level": 847,
      "category": "outdoor_gear",
      "urgency_level": "high",
      "suggested_objective": "Clear winter apparel inventory — 847 parkas in stock, end of season approaching"
    }
  ],
  "inventory_updated_at": "2026-03-27T08:00:00Z",
  "stale": false
}
```

---

## Data Models

### OfferBrief (Shared Contract — TypeScript + Pydantic)

**New field added for this feature:** `trigger_type`

**TypeScript (`src/shared/types/offer-brief.ts`):**
```typescript
export type TriggerType = 'marketer_initiated' | 'purchase_triggered';
export type OfferStatus = 'draft' | 'approved' | 'active' | 'expired';

export interface OfferBrief {
  offer_id: string;           // UUID, immutable
  objective: string;          // 10–500 chars
  segment: Segment;
  construct: Construct;
  channels: Channel[];
  kpis: KPIs;
  risk_flags: RiskFlags;
  status: OfferStatus;
  trigger_type: TriggerType;  // NEW: distinguishes marketer vs purchase-triggered
  created_at: string;         // ISO 8601
  valid_until?: string;       // ISO 8601 — purchase-triggered: now + 4h
}

export interface Segment {
  name: string;
  definition: string;
  estimated_size: number;
  criteria: string[];
  exclusions: string[];
}

export interface Construct {
  type: 'points_multiplier' | 'percentage_discount' | 'bonus_points' | 'cashback';
  value: number;
  description: string;
  valid_from: string;
  valid_until: string;
}

export interface Channel {
  channel_type: 'push' | 'email' | 'in_app' | 'sms';
  priority: number;           // 1 = highest
  delivery_rules: string[];
}

export interface KPIs {
  expected_redemption_rate: number;   // 0.0–1.0
  expected_uplift_pct: number;        // percentage
  estimated_cost_per_redemption: number;
  roi_projection: number;
  target_reach: number;
}

export interface RiskFlags {
  over_discounting: boolean;
  cannibalization: boolean;
  frequency_abuse: boolean;
  offer_stacking: boolean;
  warnings: string[];
  severity: 'low' | 'medium' | 'critical';
}
```

**Zod Schema (runtime validation):**
```typescript
export const OfferBriefSchema = z.object({
  offer_id: z.string().uuid(),
  objective: z.string().min(10).max(500),
  segment: SegmentSchema,
  construct: ConstructSchema,
  channels: z.array(ChannelSchema).min(1),
  kpis: KPIsSchema,
  risk_flags: RiskFlagsSchema,
  status: z.enum(['draft', 'approved', 'active', 'expired']),
  trigger_type: z.enum(['marketer_initiated', 'purchase_triggered']),
  created_at: z.string().datetime(),
  valid_until: z.string().datetime().optional(),
});
```

---

### Hub State Machine (Extended)

The purchase-triggered flow introduces one new valid transition:

```
EXISTING:
draft → approved          (requires: fraud check pass + marketer approval)
approved → active         (requires: context score > 60, no critical risk)
active → expired          (requires: time expiry OR redemption limit)
draft → expired           (requires: marketer cancellation OR timeout)
approved → expired        (requires: marketer cancellation OR activation window)

NEW (purchase-triggered only):
draft → active            (requires: purchase context score > 70 + fraud check pass + no rate limit)
```

The `draft → active` shortcut is ONLY valid when `trigger_type = 'purchase_triggered'`. Hub must validate `trigger_type` before allowing this transition.

---

### Database Schema (Azure SQL — Audit Trail)

```sql
-- offer_generation_log: compliance audit trail
CREATE TABLE offer_generation_log (
    id           BIGINT IDENTITY PRIMARY KEY,
    offer_id     VARCHAR(36) NOT NULL,        -- UUID
    trigger_type VARCHAR(20) NOT NULL,         -- 'marketer_initiated' | 'purchase_triggered'
    actor_id     VARCHAR(100) NOT NULL,        -- marketer_id or 'system'
    objective    NVARCHAR(500),                -- scrubbed of PII
    member_id    VARCHAR(100),                 -- for purchase-triggered (no PII)
    store_id     VARCHAR(100),                 -- originating store
    context_score DECIMAL(5,2),               -- purchase-triggered context score
    fraud_severity VARCHAR(10),               -- 'low' | 'medium' | 'critical'
    fraud_blocked BIT DEFAULT 0,
    created_at   DATETIME2 DEFAULT GETUTCDATE(),
    INDEX idx_offer_id (offer_id),
    INDEX idx_member_id (member_id),
    INDEX idx_created_at (created_at)
);

-- partner_effectiveness: for REQ-016 partner tracking
CREATE TABLE partner_effectiveness (
    id             BIGINT IDENTITY PRIMARY KEY,
    store_id       VARCHAR(100) NOT NULL,
    store_name     VARCHAR(200) NOT NULL,
    store_type     VARCHAR(20) NOT NULL,       -- 'ctc' | 'partner'
    offers_triggered INT DEFAULT 0,
    offers_delivered INT DEFAULT 0,
    offers_redeemed  INT DEFAULT 0,
    conversion_rate  AS (CAST(offers_redeemed AS FLOAT) / NULLIF(offers_triggered, 0)),
    last_updated   DATETIME2 DEFAULT GETUTCDATE(),
    INDEX idx_store_id (store_id)
);
```

---

### Mock Inventory Data Format

```csv
product_id,name,stock_level,category,store_id,unit_cost,suggested_segment
prod_001,Men's Winter Parka,847,outdoor_gear,sport_chek_001,189.99,high_value
prod_002,Motor Oil 5W-30 (6-pack),1240,automotive,canadian_tire_001,34.99,active
prod_003,WorkGuard Safety Boots,312,footwear,marks_001,149.99,lapsed_90_days
prod_004,Camping Tent 4-Person,89,outdoor_gear,sport_chek_002,299.99,high_value
prod_005,Snow Blower 24-inch,23,seasonal,canadian_tire_002,599.99,active
```

---

## Decisions (ADRs)

### ADR-001: Scout Calls Designer for Purchase-Triggered Offers

**Status:** Proposed

**Context:**
The purchase-triggered feature requires Scout (Layer 3) to request offer generation from Designer (Layer 1) when a high-scoring purchase context is detected. The TriStar architectural pattern (Pattern 1) states: "All inter-layer communication flows through Hub. No direct Designer→Scout bypass." A Scout→Designer call appears to violate this rule.

**Alternatives Considered:**

**Option A: Scout pre-generates offer itself (no Designer call)**
- Pros: Fully independent, no inter-layer coupling, fastest
- Cons: Duplicates Claude API logic in Scout; violates single-responsibility (Scout becomes a generator); cannot reuse Designer's fraud detection pipeline

**Option B: Hub acts as request broker (Scout→Hub→Designer)**
- Pros: All communication through Hub, maintains pattern purity
- Cons: Adds 200–400ms latency to Hub (state machine not designed for request routing); Hub becomes a message bus, not a state store; Hub becomes single point of failure for generation
- Verdict: Hub state machine should manage offers, not broker generation requests

**Option C: Scout calls Designer API directly (this design)**
- Pros: Clear separation — Scout handles context, Designer handles generation; reuses fraud detection, Claude API client, audit logging; simple HTTP call, low latency
- Cons: Creates Scout→Designer dependency (violates directional rule); requires service-to-service auth

**Option D: Event queue (Scout publishes event, Designer consumes)**
- Pros: Fully decoupled, resilient, no direct dependency
- Cons: Adds message queue infrastructure (Redis Streams or Azure Service Bus); adds significant complexity for MVP; 2-minute SLA harder to guarantee with queue processing

**Decision:** Option C (Scout calls Designer API directly) for MVP.

**Justification:** The architectural rule targets preventing Designer from activating offers by bypassing Hub's state machine (which would allow untested offers to reach members). Scout→Designer does NOT bypass Hub — the offer is still saved to Hub (status=active) after generation. The communication direction is Scout→Designer→Hub, not Designer→Scout. This maintains Hub as the authoritative state store. The rule should be interpreted as "Hub is the state authority, not a message bus."

**Consequences:**
- (+) Simple HTTP call, measurable SLA, reuses all Designer services
- (+) Scout remains focused on context scoring and delivery
- (-) Scout has a compile-time dependency on Designer's API contract
- (-) Requires service-to-service JWT token (system role)
- Migration path: When message infrastructure is available (Phase 2), replace with event-driven approach (Option D) without changing behavior

---

### ADR-002: Mock Inventory Data as CSV/JSON File

**Status:** Proposed

**Context:** REQ-001 requires inventory-aware offer suggestions. The assumptions confirm real-time inventory integration is out of scope for MVP. The system needs inventory data accessible to the backend service.

**Alternatives Considered:**

**Option A: Hardcoded inventory in Python dict**
- Pros: Zero setup, no file I/O
- Cons: Cannot be changed without code deployment; not representative of real integration path

**Option B: CSV/JSON file loaded at startup (this design)**
- Pros: Realistic data format (mirrors what a real CSV export from inventory system would look like); easy to swap for real integration later; can be updated without deployment
- Cons: Stale if file not updated; requires file path config

**Option C: SQLite table with mock data**
- Pros: Queryable, realistic DB integration pattern
- Cons: Adds DB dependency for a mock; overkill for MVP; setup friction

**Decision:** Option B — CSV file loaded at service startup with staleness check.

**Consequences:**
- (+) Easy to replace with real inventory API in Phase 2 (swap InventoryService implementation)
- (+) Data visible and editable without code changes
- (-) Stale data if file not refreshed; UI shows "Stock data unavailable" warning if file >24h old

---

### ADR-003: JWT Service-to-Service Token for Scout→Designer

**Status:** Proposed

**Context:** The Scout service needs to call the Designer API (/api/designer/generate-purchase) with authorization. The Designer API requires a JWT with role claim. Scout is a backend service, not a human user.

**Alternatives Considered:**

**Option A: Shared API key (X-API-Key header)**
- Pros: Simple, no JWT setup
- Cons: No expiry, no role claims, harder to audit, not standard TriStar auth pattern

**Option B: Service JWT with role='system' (this design)**
- Pros: Consistent with TriStar JWT pattern; role='system' distinguishes service calls from marketer calls; auditable; can include service_name claim
- Cons: Requires JWT generation for Scout service; token rotation needed

**Option C: mTLS (mutual TLS)**
- Pros: Most secure for service-to-service
- Cons: Complex certificate management; Azure setup required; overkill for MVP

**Decision:** Option B — Service JWT with role='system', generated at Scout startup, 24-hour expiry.

**Consequences:**
- (+) Consistent auth pattern across all services
- (+) Scout calls appear in audit logs with actor_id='system:scout'
- (-) Requires Scout to manage token refresh (24h expiry)
- Migration: Azure Managed Identity in production replaces manual JWT

---

### ADR-004: In-Memory Cache for Identical Objectives (5-min TTL)

**Status:** Proposed

**Context:** REQ-012 requires caching OfferBrief results for identical objectives for 5 minutes. The system does not have Redis available in dev environment.

**Alternatives Considered:**

**Option A: Redis cache (production pattern)**
- Pros: Shared across multiple FastAPI instances, survives restarts
- Cons: Redis not available in dev; adds dependency; over-engineered for single-instance MVP

**Option B: In-process dict with TTL (this design)**
- Pros: Zero dependencies; works in dev; sufficient for single-instance
- Cons: Not shared across multiple instances; lost on restart

**Option C: No caching (simplest)**
- Pros: Fewest moving parts
- Cons: Every identical objective pays full Claude API cost; violates REQ-012

**Decision:** Option B for MVP (in-process dict with TTL). Cache key = SHA-256 hash of lowercased, stripped objective string.

**Consequences:**
- (+) Works immediately with no infrastructure changes
- Migration: Replace `_cache: dict` with `redis.get/set` calls in Phase 2 (interface unchanged)

---

## Implementation Guidelines

### Frontend Standards

All frontend components follow `.claude/rules/react-19-standards.md`:

- **Server Components by default** — COMP-009, COMP-010, COMP-013, COMP-015 are Server Components
- **Client Components only when interactive** — COMP-011, COMP-012, COMP-014 require `'use client'`
- **Data fetching** — Server Components use `async/await` in component body; Client Components use `React.use()` with Suspense
- **Forms** — ManualEntryForm uses Server Actions (`'use server'` action function) with `useFormStatus` for pending state
- **Optimistic updates** — ApproveButton uses `useOptimistic` for instant status change before Hub confirms

**File naming:**
- Pages: `page.tsx` (kebab-case directories)
- Components: `PascalCase.tsx`
- Services: `camelCase.ts`
- Types: already in `src/shared/types/`

### Backend Standards

All backend follows `.claude/rules/fastapi-standards.md`:

- **Async everywhere** — All route handlers and service methods use `async def`
- **Dependency injection** — `ClaudeApiService`, `FraudCheckService`, `HubApiClient` injected via `Depends()`
- **Pydantic v2 models** — `model_config = ConfigDict(from_attributes=True)` for ORM compat
- **Exception handling** — Custom exceptions (`FraudBlockedError`, `HubSaveError`) mapped in global handler
- **Structured logging** — loguru with JSON output, always include `offer_id`, never include PII

**Error classes:**
```python
class FraudBlockedError(Exception):
    def __init__(self, severity: str, flags: list[str]): ...

class ClaudeApiError(Exception):
    def __init__(self, attempts: int, last_error: str): ...

class HubSaveError(Exception):
    def __init__(self, status_code: int, detail: str): ...

class RateLimitError(Exception):
    def __init__(self, member_id: str, retry_after_seconds: int): ...
```

### Security Standards

Following `.claude/rules/security.md`:

- **Input validation** — All request bodies validated by Pydantic before service calls
- **PII in logs** — `AuditLogService._scrub_pii()` removes email patterns, phone patterns before logging
- **Secrets** — All API keys from `Settings` (loaded from .env / Azure Key Vault)
- **SQL injection** — Audit log uses SQLAlchemy ORM only; no raw SQL string concatenation
- **CORS** — `allow_origins=["http://localhost:3000"]` in dev; locked to Azure App Service URL in prod
- **HTTPS** — `HTTPSRedirectMiddleware` active in `ENVIRONMENT=production`
- **Webhook security** — Purchase event endpoint validates HMAC-SHA256 signature in `X-Webhook-Signature` header

### Testing Strategy

Following `.claude/rules/testing.md`:

| Test Type | Target | Coverage |
|-----------|--------|----------|
| Unit (pytest) | ClaudeApiService, FraudCheckService, ContextScoringService, DeliveryConstraintService | >80% |
| Unit (Jest) | ManualEntryForm, ApproveButton, RiskFlagBadge, ModeSelectorTabs | >80% |
| Integration (httpx) | POST /generate, POST /generate-purchase, POST /approve, POST /purchase-event | All P0 ACs |
| E2E (Playwright) | Full marketer flow, full purchase-triggered flow | Critical paths |

**Mock Claude API:** All tests use fixtures from `tests/fixtures/offer_brief_responses.json` — no real API calls in CI.

**Mock Hub API:** `httpx.MockTransport` intercepts Hub calls — returns 201 Created with fixture data.

---

## Security Considerations

### OWASP Mapping

| OWASP Risk | Designer Layer Mitigation |
|------------|--------------------------|
| A01: Broken Access Control | JWT + RBAC on all /api/designer/* endpoints; service token for Scout→Designer |
| A02: Cryptographic Failures | HTTPS enforced in prod; JWT signed with HS256; webhook HMAC-SHA256 |
| A03: Injection | Pydantic validates all inputs; Zod validates frontend; SQLAlchemy ORM for DB |
| A05: Security Misconfiguration | CORS restricted; no wildcard origins; Azure Key Vault for secrets |
| A07: Authentication Failures | JWT 1h expiry for users; 24h service token for Scout; rate limiting on generate endpoint |
| A09: Logging Failures | Structured audit log for all generation events; PII scrubbed; trigger_type tracked |

### PII Handling

- **Logs:** Only `member_id`, `offer_id`, `marketer_id` in logs. `AuditLogService._scrub_pii()` removes emails, phone numbers from objective text before writing.
- **API responses:** No PII in API responses (member names, emails never returned)
- **Purchase event payloads:** `member_id` used as identifier; full name/email never accepted or stored

---

## Quality Gate Validation

| Gate | Result | Evidence |
|------|--------|----------|
| **Completeness** | ✅ PASS | All 11 P0 requirements mapped to components in Problem Spec Reference table |
| **Architecture Quality** | ✅ PASS | ADR-001 justifies Scout→Designer; 3-layer separation maintained; Hub remains state authority |
| **Backward Compatibility** | ✅ PASS | Greenfield, N/A |
| **Hub State Integrity** | ✅ PASS | New `draft→active` transition gated on `trigger_type=purchase_triggered`; all invalid transitions still blocked |
| **Security** | ✅ PASS | OWASP table complete; PII handling documented; secrets via Settings/Key Vault |
| **Testing** | ✅ PASS | Coverage targets set; mock strategy defined; critical paths mapped |
| **OfferBrief Contract** | ✅ PASS | TypeScript interface + Zod schema + Pydantic model all defined; `trigger_type` added consistently to both |

---

**End of Design Specification**
