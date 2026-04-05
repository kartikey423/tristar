# TriStar Architecture

**Project:** Triangle Smart Targeting and Real-Time Activation
**Hackathon:** CTC True North 2026 (March 9-18)
**Last Updated:** 2026-04-05

---

## Executive Summary

TriStar transforms the Triangle loyalty program from a reactive points ledger into a proactive, AI-powered engagement platform. The system combines intelligent offer design (Designer) with real-time contextual activation (Scout), connected through a shared state (Hub), and delivers a realistic iPhone-style push notification demo that takes a customer from notification → offer details → avail offer in one seamless flow.

**Three Core Layers:**
1. **Designer (Marketer Copilot)** — AI-powered offer design generating OfferBriefs from business objectives or inventory signals
2. **The Hub (Shared Context State)** — Central repository managing offer lifecycle with append-only audit log
3. **Scout (Real-Time Activation Engine)** — Context-aware delivery with four flows: purchase events, hub matching, partner triggers, and customer self-activation

---

## System Overview

```mermaid
graph TB
    subgraph "Layer 1: Designer (Marketer Copilot)"
        A[Business Objective Input]
        A2[Inventory Suggestion]
        A3[Live Deal Scraper]
        B[Claude API<br/>claude-sonnet-4-6]
        C[Offer Generator]
        D[OfferBrief Output]
        E{Fraud Detection<br/>over_discounting · stacking<br/>cannibalization · frequency}
        F[Save to Hub<br/>status: draft]
        G[Fraud Alert<br/>severity: critical → block]

        A --> B
        A2 --> B
        A3 --> B
        B --> C
        C --> D
        D --> E
        E -->|Pass| F
        E -->|Fail| G
    end

    subgraph "The Hub (Shared Context State)"
        H[(Offer Store<br/>Redis / In-Memory)]
        I[Status Engine<br/>draft → approved → active → expired]
        J[Audit Log<br/>SQLite · Append-Only]
        K[Background Expiry Sweep<br/>every 300s]

        F --> H
        H --> I
        I --> J
        K --> I
    end

    subgraph "Layer 3: Scout (Real-Time Activation Engine)"
        subgraph "Flow A: Purchase Event"
            PA[POST /scout/purchase-event<br/>HMAC-signed webhook]
            PB[Deterministic Scorer<br/>7 factors · threshold ≥ 70]
            PC[Designer: generate-purchase<br/>service JWT · internal call]
        end
        subgraph "Flow B: Hub Match"
            MB[POST /scout/match<br/>purchase context]
            MC[Claude AI Scorer<br/>+ deterministic fallback<br/>threshold > 60]
            MD[DeliveryConstraintService<br/>CASL · rate-limit · dedup · quiet-hours]
        end
        subgraph "Flow C: Partner Trigger"
            PT[POST /scout/partner-trigger<br/>HMAC-signed webhook]
            PU[Claude Haiku<br/>classification + location zone + time type]
            PV[OfferBrief<br/>status: active · valid 24h]
        end
        subgraph "Flow D: Customer Self-Activation"
            CA[Customer taps notification<br/>View Offer → Avail Offer]
            CB[POST /hub/offers/id/customer-accept<br/>NEXT_PUBLIC_MARKETER_JWT]
            CC[Auto-approve + activate<br/>no marketer action needed]
        end

        PA --> PB --> PC
        MB --> MC --> MD
        PT --> PU --> PV
        CA --> CB --> CC
    end

    R[Push Notification<br/>Member App]
    S[Queue for Later<br/>next 8am window]
    U[Activation Log<br/>ScoutAuditService]

    PC --> R
    MD -->|activated| R
    MD -->|queued| S
    PV --> H
    CC --> H

    R --> U
    H --> MB

    style A fill:#e1f5ff
    style H fill:#fff4e1
    style PA fill:#e8f5e8
    style MB fill:#e8f5e8
    style PT fill:#e8f5e8
    style CA fill:#e8f5e8
    style R fill:#f0e8ff
```

---

## End-to-End Flow

```mermaid
sequenceDiagram
    actor Marketer
    participant Designer as Designer UI
    participant Claude as Claude API (Sonnet)
    participant FraudScan as Fraud Detection
    participant Hub as The Hub
    participant Scout as Scout Engine
    participant Phone as Mobile Phone Preview
    actor Customer

    Marketer->>Designer: Enter business objective
    Designer->>Claude: Generate OfferBrief prompt
    Claude->>Designer: Structured OfferBrief (Segment, Construct, Channels, KPIs, PaymentSplit)

    Designer->>FraudScan: Validate risk patterns
    FraudScan->>Designer: Risk report (severity: low/medium/critical)

    Marketer->>Designer: Approve offer
    Designer->>Hub: Save offer (status: approved → active)
    Hub->>Hub: Append audit log entry

    Note over Scout: Flow B — Hub Match

    Customer->>Scout: POST /scout/match (purchase context + GPS)
    Scout->>Hub: GET active offers
    Hub->>Scout: Return active offers
    Scout->>Scout: AI scoring — Location, Weather, Time, Behavior
    Note over Scout: Score 85/100 > threshold 60

    Scout->>Scout: DeliveryConstraintService
    Scout->>Phone: Lock screen notification<br/>"Windshield Wipers (pair) at 22% off —<br/>use up to $14.62 in Triangle Rewards. Pay just $4.87."

    Note over Phone,Customer: Customer taps "View Offer →"

    Phone->>Phone: Offer Details screen<br/>Personalized message + price breakdown<br/>Rewards (max 75%) · You pay (min 25%)
    Customer->>Phone: Tap "Avail Offer"
    Phone->>Hub: POST /offers/{id}/customer-accept
    Hub->>Hub: Auto-approve + activate offer
    Phone->>Customer: "Offer Active!" confirmation<br/>"Back to main screen"

    Scout->>Hub: Log activation (member_id, offer_id, score)
```

---

## Customer Phone Preview — 3-Screen Flow

The Scout page includes a realistic iPhone lock-screen mockup. After Run Match Scoring or Trigger Partner Cross-Sell, the phone simulates exactly what the customer sees.

```mermaid
stateDiagram-v2
    [*] --> LockScreen : Match scoring completes

    LockScreen --> OfferDetail : Customer taps "View Offer →"
    OfferDetail --> Loading : Customer taps "Avail Offer"
    Loading --> OfferActive : POST /customer-accept succeeds
    Loading --> Error : Request fails
    OfferActive --> LockScreen : Customer taps "Back to main screen"
    OfferDetail --> LockScreen : Customer taps "← Back"
    Error --> LockScreen : Customer taps "Back"

    note right of LockScreen
        Short rewards-focused body:
        "{item} at {pct}% off — use up to
        ${rewards} in Triangle Rewards.
        Pay just ${youPay}."
    end note

    note right of OfferDetail
        Full personalized message +
        price breakdown table:
        Original → Offer price →
        Rewards max 75% → You pay min 25%
    end note

    note right of OfferActive
        "Offer Active!" + green checkmark
        Hub status: active
        "Back to main screen" link
    end note
```

### Screen Content

| Screen | Title | Body |
|--------|-------|------|
| **Lock screen notification** | e.g. `Exclusive offer for you, Alice!` | Short: `Windshield Wipers (pair) at 22% off — use up to $14.62 in Triangle Rewards. Pay just $4.87.` |
| **Offer Details** | `Offer Details` | Personalized: *"Spring is here, Alice! Since you picked up a Motor Oil 5W-30 (5L), your next best offer is Windshield Wipers (pair) at 22% off."* + full price breakdown |
| **Offer Active** | `Offer Active!` | Confirmation with Hub link + "Back to main screen" |

---

## Scout Activation Flows

```mermaid
sequenceDiagram
    participant Partner as Partner System<br/>(Tim Hortons etc.)
    participant Rewards as Triangle Rewards<br/>Webhook
    participant Scout as Scout API
    participant Handler as PurchaseEventHandler
    participant Scorer as ContextScoringService<br/>(deterministic 7-factor)
    participant Constraints as DeliveryConstraintService
    participant Designer as Designer API
    participant Hub as Hub Store
    participant Haiku as Claude Haiku
    participant Notify as NotificationService

    Note over Rewards, Scout: Flow A — Purchase Event (threshold ≥ 70)
    Rewards->>Scout: POST /scout/purchase-event (HMAC)
    Scout->>Handler: Validate feature flag, pilot list, dedup
    Handler->>Scorer: Score 7 factors
    Scorer-->>Handler: Score (e.g. 78)
    Handler->>Constraints: CASL · rate-limit · quiet-hours
    Constraints-->>Handler: can_deliver: true
    Handler->>Designer: POST /designer/generate-purchase (service JWT)
    Designer->>Hub: Save offer (status: active)
    Designer-->>Scout: 201 OfferBrief
    Scout->>Notify: Send push notification
    Scout-->>Rewards: 202 Accepted

    Note over Partner, Scout: Flow C — Partner Trigger (background, with location + time intelligence)
    Partner->>Scout: POST /scout/partner-trigger (HMAC)
    Scout-->>Partner: 202 Accepted (immediate)
    Scout->>Haiku: Classify category + location zone + time type
    Note over Haiku: LocationZone: hill_station / cottage_lakes / highway / urban
    Note over Haiku: TimeType: long_weekend / weekend / weekday
    Haiku-->>Scout: Enriched category (e.g. winter_automotive)
    Scout->>Scout: Build predictive offer with marketplace price comparison
    Scout->>Hub: Save offer (status: active, valid_until: +24h)
```

---

## Component Architecture

```mermaid
graph LR
    subgraph Frontend["Frontend (Next.js 15 · App Router)"]
        A[React 19<br/>TypeScript · Tailwind CSS]
        A --> B[Dashboard /]
        A --> C[Designer /designer<br/>AI Suggestions · Manual Entry]
        A --> D[Hub /hub<br/>Live Polling 5s]
        A --> E[Scout /scout<br/>Purchase Simulator]
        A --> F[Next.js API Route<br/>/api/hub-offers proxy]
    end

    subgraph Backend["Backend (FastAPI · Python 3.11)"]
        G[FastAPI App<br/>main.py]
        G --> H[/api/designer<br/>generate · approve · suggestions · live-deals]
        G --> I[/api/hub<br/>CRUD · status · redeem · customer-accept]
        G --> J[/api/scout<br/>match · purchase-event · partner-trigger]
        G --> K[/api/auth/demo-token<br/>/health]
    end

    subgraph Services["Backend Services"]
        L[ClaudeApiService<br/>Sonnet · 3-retry · 5min cache]
        M[ClaudeContextScoringService<br/>Haiku · 3s timeout · fallback]
        N[ContextScoringService<br/>Deterministic 7-factor]
        O[FraudCheckService]
        P[HubStore<br/>InMemory / Redis]
        Q[HubAuditService<br/>SQLite append-only]
        R[DeliveryConstraintService<br/>CASL · rate-limit · dedup]
        S[PartnerTriggerService<br/>Haiku + LocationZone + TimeType]
        T[InventoryService<br/>CSV overstock · project-root path]
        U[DealScraperService<br/>CTC website · 15min cache]
        V[ScoutAuditService<br/>activation records]
        W2[ScoutMatchService<br/>per-member smart matching]
        X2[LocationZoneService<br/>hill_station / cottage_lakes / highway / urban]
        Y2[CanadianHolidayService<br/>long_weekend / weekend / weekday]
    end

    subgraph External["External Services"]
        W[Claude API<br/>claude-sonnet-4-6<br/>claude-haiku-4-5-20251001]
        X[Weather API<br/>OpenWeatherMap]
    end

    subgraph Data["Data Layer"]
        Y[(Redis<br/>Hub State<br/>offer:{id} keys)]
        Z[(SQLite<br/>Audit Logs)]
    end

    C <-->|HTTP/JSON| H
    D <-->|HTTP/JSON| I
    E <-->|HTTP/JSON| J
    F <-->|proxy| I

    H --> L
    H --> O
    J --> M
    J --> N
    J --> R
    J --> S
    J --> W2
    H --> T
    H --> U
    I --> P
    I --> Q
    J --> V
    S --> X2
    S --> Y2

    L --> W
    M --> W
    S --> W
    J --> X

    P --> Y
    Q --> Z
    V --> Z

    style A fill:#61dafb
    style G fill:#009688
    style W fill:#e07c3e
    style Y fill:#dc382d
```

---

## Data Flow: OfferBrief Schema

```mermaid
classDiagram
    class OfferBrief {
        +string offer_id (UUID v4)
        +string objective
        +OfferStatus status
        +TriggerType trigger_type
        +Segment segment
        +Construct construct
        +Channel[] channels
        +KPIs kpis
        +RiskFlags risk_flags
        +datetime created_at
        +datetime valid_until (required for auto-triggered)
        +string source_deal_id (dedup key)
    }

    class OfferStatus {
        <<enumeration>>
        draft
        approved
        active
        expired
    }

    class TriggerType {
        <<enumeration>>
        marketer_initiated
        purchase_triggered
        partner_triggered
    }

    class Segment {
        +string name
        +string definition
        +int estimated_size
        +string[] criteria
        +string[] exclusions
    }

    class Construct {
        +string type
        +float value
        +string description
        +datetime valid_from
        +datetime valid_until
        +PaymentSplit payment_split
    }

    class PaymentSplit {
        +int points_max_pct (default 75)
        +int cash_min_pct (default 25)
        +validate() points+cash == 100
    }

    class Channel {
        +ChannelType channel_type
        +int priority
        +string[] delivery_rules
    }

    class KPIs {
        +float expected_redemption_rate
        +float expected_uplift_pct
        +float estimated_cost_per_redemption
        +float roi_projection
        +int target_reach
    }

    class RiskFlags {
        +bool over_discounting (>30% → critical)
        +bool cannibalization
        +bool frequency_abuse
        +bool offer_stacking (>5 active → critical)
        +string[] warnings
        +RiskSeverity severity
    }

    OfferBrief --> OfferStatus
    OfferBrief --> TriggerType
    OfferBrief --> Segment
    OfferBrief --> Construct
    Construct --> PaymentSplit
    OfferBrief --> Channel
    OfferBrief --> KPIs
    OfferBrief --> RiskFlags

    note for OfferBrief "Single source of truth in src/shared/types/offer-brief.ts\nValidated: Zod (frontend) + Pydantic v2 (backend)\nPaymentSplit enforces Triangle 75/25 rule"
    note for TriggerType "purchase_triggered and partner_triggered offers\nrequire valid_until. marketer_initiated offers\nfollow draft→approved→active manually."
```

---

## Hub State Machine

```mermaid
stateDiagram-v2
    [*] --> draft : Designer generates offer\n(marketer_initiated)
    [*] --> active : Auto-triggered offer saved\n(purchase_triggered / partner_triggered)

    draft --> approved : Marketer approves\nPOST /designer/approve/{id}
    approved --> active : Marketer or system activates\nPUT /hub/offers/{id}/status
    active --> active : Customer taps "Avail Offer"\nPOST /hub/offers/{id}/customer-accept\n(auto-approve + activate if needed)
    active --> expired : Background expiry sweep\n(valid_until < now, every 300s)
    active --> expired : Member redeems\nPOST /hub/offers/{id}/redeem
    draft --> [*] : Rejected\nDELETE /hub/offers/{id}

    note right of draft : Only draft offers\nallow construct patches
    note right of active : Fraud-critical offers\nblocked before reaching active
    note right of active : customer-accept bypasses\nmarketer approval for demo flow
```

---

## Context Matching Algorithm

### Flow B — Hub Match (Claude AI Primary, Deterministic Fallback)

```mermaid
flowchart TD
    A[Purchase Context Received] --> B[Concurrent Enrichment]
    B --> B1[Member Profile\nMockMemberProfileStore]
    B --> B2[Nearby CTC Stores\nCTCStoreFixtures]
    B --> B3[Weather Conditions\nOpenWeatherMap / override]
    B --> B4[Active Hub Offers\nHubApiClient]

    B1 --> C[ScoutMatchService\nper-member smart ranking]
    B2 --> C
    B3 --> C
    B4 --> C

    C --> D[Score Each with ClaudeContextScoringService\n3s timeout · SHA-256 cache · 3h bucket]
    D -->|timeout/error| E[Fallback: ContextScoringService\n7-factor deterministic]
    D --> F[Select Best Score]
    E --> F

    F --> G{Score > 60?}
    G -->|No| H[NoMatchResponse\nno notification sent]
    G -->|Yes| I[DeliveryConstraintService]

    I --> J{CASL opt-out?}
    J -->|Yes| K[Blocked: casl_optout]
    J -->|No| L{Rate limited?\n6h per member}
    L -->|Yes| M[rate_limited — offer still shown\nView Offer → available]
    L -->|No| N{Duplicate offer\n24h window?}
    N -->|Yes| O[Blocked: duplicate]
    N -->|No| P{Quiet hours?\n10pm–8am}
    P -->|Yes| Q[Queued: next 8am]
    P -->|No| R[Activated: send notification]

    R --> S[ScoutAuditService\nmember_id · offer_id · score · rationale]
    Q --> S
    M --> T[Phone preview shows offer\nwith View Offer button]

    style A fill:#e1f5ff
    style R fill:#c8e6c9
    style Q fill:#ffecb3
    style K fill:#ffcccc
    style M fill:#fff3cd
    style O fill:#ffcccc
```

**Note on `rate_limited`:** Even when rate-limited (notification already sent recently), the phone preview still shows the offer with "View Offer →" so the customer can view details and avail it.

### Flow A — Purchase Event (Deterministic, 7-Factor)

```mermaid
flowchart TD
    A[Purchase Event Webhook\nHMAC signature verified] --> B{Feature flag enabled?\nPilot member?}
    B -->|No| Z[Skip: 202 Accepted]
    B -->|Yes| C{Dedup window?}
    C -->|Duplicate| Z
    C -->|New| D[ContextScoringService — 7 Factors]

    D --> D1[Purchase Value: max 20pts\n≥$100 → 20, ≥$50 → 12, ≥$20 → 6]
    D --> D2[Proximity to CTC Store: max 25pts\n<500m → 25, <1km → 18, <2km → 10]
    D --> D3[Purchase Frequency: max 15pts\n≥5/month → 15, ≥2 → 8]
    D --> D4[Category Affinity: max 20pts\nmatches preferred_categories]
    D --> D5[Partner Cross-sell: max 15pts\nknown partner → 15]
    D --> D6[Weather Match: max 10pts\ncondition aligns with offer]
    D --> D7[Time Alignment: max 5pts\nbusiness hours bonus]

    D1 --> E[Total Score / 110 → clamped to 100]
    D2 --> E
    D3 --> E
    D4 --> E
    D5 --> E
    D6 --> E
    D7 --> E

    E --> F{Score ≥ 70?}
    F -->|No| G[scored_below_threshold\n202 Accepted]
    F -->|Yes| H[DeliveryConstraintService]
    H --> I{Can deliver?}
    I -->|No| J[blocked / queued]
    I -->|Yes| K[POST /designer/generate-purchase\nservice JWT · internal call]
    K --> L[Hub saves offer: active\ntrigger_type: purchase_triggered]
    L --> M[Push notification sent]

    style A fill:#e1f5ff
    style M fill:#c8e6c9
    style G fill:#ffecb3
    style J fill:#ffcccc
```

### Flow C — Partner Trigger (Location + Time Intelligence)

```mermaid
flowchart TD
    A[POST /scout/partner-trigger\nHMAC-signed] --> B[202 Accepted immediately]
    B --> C[Background: classify_and_generate]

    C --> D[LocationZoneService\nclassify GPS coordinates]
    D --> D1[hill_station\ne.g. Blue Mountain → winter_automotive]
    D --> D2[cottage_lakes\ne.g. Muskoka → marine_fishing]
    D --> D3[highway\ne.g. Hwy 400 → automotive_accessories]
    D --> D4[urban\ne.g. Toronto → automotive_cleaning]

    C --> E[CanadianHolidayService\nclassify timestamp]
    E --> E1[long_weekend → urgency copy]
    E --> E2[weekend → weekend copy]
    E --> E3[weekday → exclusive pricing copy]

    D --> F[Claude Haiku\nclassify purchase → CTC category]
    E --> F
    F -->|failure| G[Fallback: _PARTNER_FALLBACK_CATEGORIES\npartner_id + LocationZone key]
    F --> H[_generate_offer\nbuild OfferBrief inline]
    G --> H

    H --> I[Predictive objective + push message\nmarketplace price comparison\n~X% cheaper than Amazon]
    I --> J[FraudCheckService\nblock if severity=critical]
    J --> K[Hub save: status=active\nvalid_until=now+24h]

    style A fill:#e1f5ff
    style K fill:#c8e6c9
    style G fill:#ffecb3
```

---

## API Reference

### Designer (`/api/designer`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/generate` | marketing | Generate OfferBrief from objective via Claude Sonnet. Auto-saves to Hub as draft. |
| `POST` | `/generate-purchase` | system | Purchase-triggered offer generation. Saves to Hub as active. |
| `POST` | `/approve/{offer_id}` | marketing | Transition draft → approved. |
| `GET` | `/suggestions` | **public** | Top-N inventory overstock suggestions (excludes already-offered products). |
| `GET` | `/live-deals` | marketing | Scraped Canadian Tire deals (15-min cache, 20-item demo fallback). |

### Hub (`/api/hub`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/offers` | marketing/system | Save offer. Rejects active status for marketer-initiated offers. |
| `GET` | `/offers/{offer_id}` | **public** | Get offer by ID. |
| `GET` | `/offers` | **public** | List offers. Filters: status, trigger_type, since, member_id. Deduplicates by objective. |
| `PUT` | `/offers/{offer_id}/status` | marketing | Status transition. Enforces VALID_TRANSITIONS state machine. |
| `PATCH` | `/offers/{offer_id}/construct` | marketing | Update construct value (draft only). |
| `DELETE` | `/offers/{offer_id}` | marketing | Reject (delete) a draft offer. |
| `POST` | `/offers/{offer_id}/redeem` | any | Validate Triangle 75/25 payment split. |
| `POST` | `/offers/{offer_id}/customer-accept` | marketing | **New.** Customer taps "Avail Offer" — auto-approves + activates without marketer action. Used by phone preview demo. |
| `DELETE` | `/admin/reset` | — | Dev only: clear all Hub offers. |

### Scout (`/api/scout`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/purchase-event` | HMAC | Purchase event webhook (Flow A). Returns 202. |
| `POST` | `/match` | any | Score Hub offers against purchase context (Flow B). Returns `MatchResponse` or `NoMatchResponse`. |
| `GET` | `/activation-log/{member_id}` | any | Recent activation records for a member. |
| `POST` | `/partner-trigger` | HMAC | Partner purchase webhook (Flow C). Returns 202. Background classification + offer generation. |

### System

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/demo-token` | Short-lived demo JWT for Swagger or E2E testing. `?role=marketing` for marketer token. |
| `GET` | `/health` | Health check including Redis status (`redis: ok/degraded`). |

**Auth note:** Read-only GET endpoints (`/hub/offers`, `/hub/offers/{id}`, `/designer/suggestions`) are public — no JWT required. This enables cross-machine demo without `.env.local` setup affecting read operations.

---

## Hub Store Implementation

```mermaid
graph TD
    A{HUB_REDIS_ENABLED?} -->|False: dev/test| B[InMemoryHubStore\ndict-based]
    A -->|True: prod| C[RedisHubStore\nSCAN-based]

    B --> D[save: OfferAlreadyExistsError\non dup offer_id or source_deal_id]
    C --> E[save: atomic SET NX\nrollback deal index on failure]

    C --> F[list: SCAN offer:* cursor\nmget batch fetch\n_apply_filters]
    C --> G[Secondary index\nhub:deal:{source_deal_id} → offer_id\nfor cross-offer dedup]

    H[Background Expiry Sweep\nasyncio task · every 300s] --> I[hub_store.list active offers\ncheck valid_until < now\nhub_store.update → expired]

    style B fill:#e8f5e8
    style C fill:#dc382d,color:#fff
    style H fill:#fff4e1
```

**Key behaviours:**
- Both stores reject `save()` if an offer with the same `source_deal_id` already exists in draft/approved/active — prevents the same live deal being offered twice.
- `RedisHubStore` uses `SCAN` (not `KEYS`) to avoid blocking the Redis event loop.
- Redis `maxmemory-policy` must be `noeviction`; startup validates this and logs CRITICAL if misconfigured.

---

## Delivery Constraint Enforcement

```
DeliveryConstraintService (in-memory dev) / RedisDeliveryConstraintService (prod)

For every potential notification:
  1. CASL opt-out check        → blocked: casl_optout
  2. Rate limit: 6h per member → rate_limited (offer still shown in phone preview with View Offer →)
  3. 24h dedup (same offer)    → blocked: duplicate
     ↳ bypassed if purchase_value > $100
  4. Quiet hours 10pm–8am      → queued: next 8am window

Redis keys:
  scout:rate:{member_id}  TTL 6h
  scout:dedup:{member_id}:{offer_id}  TTL 24h
  scout:morning:{member_id}  TTL until 8am next day
```

---

## Frontend Structure

```
src/frontend/
├── app/                          # Next.js 15 App Router
│   ├── layout.tsx               # Root layout — sidebar shell, Public Sans font
│   ├── page.tsx                 # Dashboard: KPI cards, recent offers, activation trend
│   ├── designer/
│   │   ├── page.tsx             # Server Component — fetches suggestions server-side
│   │   └── actions.ts           # Server Actions
│   ├── hub/
│   │   ├── page.tsx             # Server Component — initial offers + live polling
│   │   └── actions.ts           # Server Actions
│   ├── scout/
│   │   └── page.tsx             # Scout context simulator
│   └── api/hub-offers/
│       └── route.ts             # Next.js API Route — Hub proxy for client polling
├── components/
│   ├── Designer/
│   │   ├── ModeSelectorTabs.tsx  # AI Suggestions / Manual Entry tab switcher (10s Hub sync)
│   │   ├── AISuggestionsPanel.tsx
│   │   ├── ManualEntryForm.tsx
│   │   ├── OfferBriefCard.tsx
│   │   ├── RiskFlagBadge.tsx
│   │   └── ApproveButton.tsx
│   ├── Hub/
│   │   ├── LiveHubContent.tsx   # Client — polls every 5s, client-side filter
│   │   ├── OfferList.tsx
│   │   ├── OfferCard.tsx
│   │   ├── StatusBadge.tsx
│   │   └── StatusActionButtons.tsx
│   ├── Scout/
│   │   ├── ContextDashboard.tsx # Purchase simulator — 19 store fixtures, member/item/weather controls
│   │   │                        # predictNextBestItem() — per-member AI next-best-item recommendation
│   │   │                        # generatePersonalizedMessage() — seasonal + occasion-aware copy
│   │   │                        # startPartnerOfferPoll() — polls /api/hub-offers every 2s up to 30s
│   │   ├── MobileNotificationPreview.tsx  # iPhone lock-screen mockup — 3-screen flow:
│   │   │                                  #   1. Lock screen (short rewards body)
│   │   │                                  #   2. Offer Details (personalized msg + price breakdown)
│   │   │                                  #   3. Offer Active (confirmation + back to main)
│   │   └── ActivationFeed.tsx   # Score, outcome, rationale, notification text
│   └── Shell/
│       ├── SidebarNav.tsx
│       └── Breadcrumb.tsx
├── services/
│   ├── designer-api.ts
│   └── hub-api.ts
└── lib/
    ├── scout-api.ts             # callScoutMatch · callPartnerTrigger · customerAcceptOffer
    └── config.ts
```

---

## Partner Trigger Intelligence

The `PartnerTriggerService` classifies purchases using two context dimensions:

### Location Zones (`LocationZoneService`)

| Zone | Example | Default CTC Category |
|------|---------|---------------------|
| `hill_station` | Blue Mountain (lat 44.50, lon -80.31) | `winter_automotive` |
| `cottage_lakes` | Muskoka region | `marine_fishing` |
| `highway` | Hwy 400 corridor | `automotive_accessories` |
| `urban` | Toronto city centre | `automotive_cleaning` |

### Time Types (`CanadianHolidayService`)

| Type | Trigger | Push copy |
|------|---------|-----------|
| `long_weekend` | Stat holiday period | *"before the long weekend crowds hit"* |
| `weekend` | Saturday / Sunday | *"this weekend — great time to stock up"* |
| `weekday` | Mon–Fri | *"today — exclusive weekday pricing"* |

### Marketplace Price Comparison

Each category has a `_MARKETPLACE_PREMIUM` multiplier (e.g. `ski_accessories: 1.22` = ~22% cheaper than Amazon). This is embedded in the push message to drive urgency.

### Supported Partners

| Partner | Zones | Haiku prompt |
|---------|-------|-------------|
| `tim_hortons` | all 4 | coffee at resort → winter_automotive, drive-through → automotive_cleaning |
| `westjet` | all 4 | domestic → luggage, family → outdoor_camping |
| `sport_chek` | all 4 | hill/lakes → outdoor_camping, urban → fitness |

---

## Cross-Machine Setup

Since `.env` and `src/frontend/.env.local` are gitignored, each developer must set them up once:

```
1. cp .env.example .env
   → fill in CLAUDE_API_KEY, confirm JWT_SECRET=dev-secret-change-in-prod

2. uvicorn src.backend.main:app --reload --port 8000

3. curl -s -X POST "http://localhost:8000/api/auth/demo-token?role=marketing"
   → copy access_token

4. cp src/frontend/.env.local.example src/frontend/.env.local
   → replace REPLACE_WITH_YOUR_TOKEN with the token

5. cd src/frontend && npm run dev
```

**Token lifetime:** 100 hours (`SERVICE_JWT_EXPIRY_HOURS=100`). Regenerate if you get 401 errors on write operations.

**Public endpoints (no token needed):** `GET /api/hub/offers`, `GET /api/hub/offers/{id}`, `GET /api/designer/suggestions` — Hub and Designer read views work without a token.

---

## Technology Stack

### Frontend
- **Framework:** Next.js 15 (App Router, Server Components)
- **Language:** TypeScript 5.x (strict mode)
- **Styling:** Tailwind CSS
- **State Management:** React Context + `useOptimistic`
- **Data Fetching:** React.use() with Suspense; polling via `setInterval`
- **Forms:** React Server Actions
- **Validation:** Zod (mirrors Python Pydantic models)
- **Testing:** Jest + React Testing Library, Playwright (E2E)

### Backend
- **Framework:** FastAPI 0.115+
- **Language:** Python 3.11+
- **Validation:** Pydantic v2
- **Async Runtime:** asyncio + uvicorn
- **Database:** SQLite via aiosqlite (dev audit log)
- **Cache/Store:** Redis 7.x (prod Hub store + delivery constraints)
- **HTTP Client:** httpx (async, internal service calls)
- **Auth:** PyJWT (HS256), HMAC webhook verification
- **Testing:** Pytest + httpx AsyncClient
- **Logging:** loguru (structured JSON)

### AI Services
| Model | Used For |
|-------|----------|
| `claude-sonnet-4-6` | OfferBrief generation from marketer objectives and purchase context |
| `claude-haiku-4-5-20251001` | Context scoring (3s timeout, fallback); partner purchase classification with location + time context |

### Infrastructure
- **Cloud:** Microsoft Azure
- **Compute:** App Service (frontend), Azure Functions (backend)
- **Data:** Azure Redis Cache, Azure SQL Database
- **Monitoring:** Application Insights
- **Secrets:** Azure Key Vault
- **CI/CD:** GitHub Actions

---

## Security Architecture

### Authentication & Authorization

| Role | Token Source | Access |
|------|-------------|--------|
| `marketing` | Demo JWT via `/api/auth/demo-token?role=marketing` | Designer generate/approve, Hub writes, customer-accept |
| `system` | Service JWT via `ScoutServiceAuth` | Scout → Designer internal calls |
| Webhook callers | HMAC-SHA256 signature header | `/scout/purchase-event`, `/scout/partner-trigger` |
| Public | No token | GET `/hub/offers`, GET `/designer/suggestions` |

### Data Flow Security
- **In Transit:** TLS 1.3 for all HTTP traffic
- **At Rest:** Azure Storage encryption (256-bit AES)
- **Secrets:** Azure Key Vault with managed identities
- **PII Handling:** Log `member_id` only — no names, emails, addresses, or GPS coordinates in logs
- **Rate Limiting:** 100 requests/min per IP (API Management layer)
- **Webhooks:** HMAC-SHA256 — bypassed only in `ENVIRONMENT=development`
- **Prompt injection:** Partner purchase fields capped at 100 chars before Haiku classification

---

## Performance Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| API Response Time (p95) | <200ms | loguru WARNING if exceeded (`hub_latency_exceeded`) |
| Frontend Page Load | <2s (FCP) | Lighthouse CI |
| Claude Scoring Latency | <3s (timeout + fallback) | Custom timer |
| Partner Trigger Background SLA | <2s | Background task measurement |
| Cache Hit Rate (Hub) | >80% | Redis INFO stats |
| Offer Generation Time | <5s | Claude API latency |
| Expiry Sweep Interval | 300s | Background task config |
| Partner offer poll (frontend) | 2s interval · 30s max | `setInterval` in ContextDashboard |

---

## Scalability Considerations

### Current Scale (Hackathon Demo)
- **Users:** ~100 concurrent demo users
- **Offers:** ~1,000 active offers in Hub
- **Context Signals:** ~10 signals/sec
- **Notifications:** ~5 notifications/sec

### Production Scale (Future)
- **Users:** 10M+ Triangle members
- **Offers:** 100K+ active offers
- **Context Signals:** 10K signals/sec
- **Notifications:** 1K notifications/sec

### Scaling Strategy
1. **Horizontal Scaling:** Azure Functions auto-scale based on queue depth
2. **Caching:** Redis cluster with read replicas; `ClaudeContextScoringService` uses in-process LRU cache (max 200 entries, 3-hour bucket key)
3. **Database:** Sharding by `member_id` (10M members = 10 shards)
4. **CDN:** Azure CDN for static assets
5. **Async Processing:** Purchase events queued via HMAC webhook, processed in background

---

## Monitoring & Observability

### Metrics to Track
1. **Business Metrics:**
   - Offer generation rate (offers/hour, by trigger_type)
   - Activation rate (notifications/hour)
   - Redemption rate (redeemed/activated)
   - Score distribution (activated vs queued vs blocked)
   - Customer self-activation rate (customer-accept calls)

2. **Technical Metrics:**
   - API latency (p50, p95, p99) — WARNING logged if >200ms
   - Error rate (5xx responses)
   - Claude scoring cache hit rate
   - Redis Hub store SCAN latency
   - Partner trigger background task success rate

3. **User Experience:**
   - Frontend page load time
   - Hub live-poll latency (target <5s)
   - Notification delivery success rate
   - Phone preview offer-to-avail conversion

---

## Future Enhancements

### Phase 2 (Post-Hackathon)
- **ML Scoring:** Replace deterministic 7-factor scorer with trained model on activation history
- **A/B Testing:** Experimentation framework for offer variants
- **Multi-Language:** French language support for Quebec members
- **Partner Integration:** WestJet, Sport Chek real-time inventory sync
- **Real Push Notifications:** Replace phone preview mockup with FCM/APNs integration

### Phase 3 (Production)
- **Mobile Apps:** Native iOS/Android with offline support
- **Redis Streams:** Replace polling with push-based Hub event streaming to frontend
- **AI Agents:** Multi-agent orchestration for complex multi-touchpoint campaigns
- **Compliance:** Immutable audit trail for CTC regulatory requirements

---

**Document Version:** 3.0
**Generated:** 2026-04-05
**Maintainers:** TriStar Hackathon Team
