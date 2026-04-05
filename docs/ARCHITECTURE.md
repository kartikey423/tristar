# TriStar Architecture

**Project:** Triangle Smart Targeting and Real-Time Activation
**Hackathon:** CTC True North 2026 (March 9-18)
**Last Updated:** 2026-04-05

---

## Executive Summary

TriStar transforms the Triangle loyalty program from a reactive points ledger into a proactive, AI-powered engagement platform. The system combines intelligent offer design (Designer) with real-time contextual activation (Scout), connected through a shared state (Hub).

**Three Core Layers:**
1. **Designer (Marketer Copilot)** - AI-powered offer design generating OfferBriefs from business objectives
2. **The Hub (Shared Context State)** - Central repository for approved offers ready for activation
3. **Scout (Real-Time Activation Engine)** - Context-aware delivery system monitoring GPS, weather, time, and behavior

**Three Offer Trigger Types:**
- `marketer_initiated` — Marketer creates via Designer UI (draft → approved → active flow)
- `purchase_triggered` — Auto-generated when a Triangle purchase webhook arrives at Scout
- `partner_triggered` — Auto-generated when a partner purchase event (e.g. Tim Hortons) arrives

---

## System Overview

```mermaid
graph TB
    subgraph "Layer 1: Designer (Marketer Copilot)"
        A[Business Objective Input]
        B[Claude API<br/>claude-sonnet-4-6]
        C[Offer Generator]
        D[OfferBrief Output]
        E{Fraud Detection<br/>Risk Validation}
        F[Export to Hub]
        G[Fraud Alert]
        DS[Deal Scraper<br/>Weekly Deals / Flyer]
        INV[Inventory Suggestions]

        A --> B
        B --> C
        C --> D
        DS --> C
        INV --> C
        D --> E
        E -->|Pass| F
        E -->|Fail| G
    end

    subgraph "Layer 2: The Hub (Shared Context State)"
        H[(Approved Offers<br/>In-Memory Store)]
        I[Status Management<br/>draft → approved → active → expired]
        J[Audit Log<br/>Append-Only]

        F --> H
        H --> I
        I --> J
    end

    subgraph "Layer 3: Scout (Real-Time Activation Engine)"
        K[Purchase Event Webhook<br/>POST /api/scout/purchase-event]
        P2[Partner Event Webhook<br/>POST /api/scout/partner-trigger]
        SM[POST /api/scout/match<br/>POST /api/scout/smart-match]

        P[Claude AI Context Scoring<br/>+ Deterministic Fallback]
        Q{Score > 60?}
        R[Push Notification]
        S[Queue for Later<br/>or Rate-Limited]

        K --> SM
        P2 --> PA[Partner Trigger Service<br/>Haiku classify + Sonnet generate]
        SM --> P
        H --> P
        P --> Q
        Q -->|Yes| R
        Q -->|No| S
        PA --> H
    end

    DC[Delivery Constraints<br/>CASL, Rate-Limit, Dedup, Quiet Hours]
    R --> DC
    DC --> T[Member Notification]
    SA[Scout Audit Log]
    R --> SA

    style A fill:#e1f5ff
    style H fill:#fff4e1
    style K fill:#e8f5e8
    style T fill:#f0e8ff
    style PA fill:#fce4ec
```

---

## End-to-End Flow: Marketer-Initiated Offer

```mermaid
sequenceDiagram
    actor Marketer
    participant Designer as Designer UI
    participant Claude as Claude API (Sonnet)
    participant FraudScan as Fraud Detection
    participant Hub as The Hub
    participant Scout as Scout Engine
    participant Member as Member App

    Marketer->>Designer: Enter business objective<br/>"Reactivate lapsed high-value members"
    Designer->>Claude: Generate OfferBrief prompt
    Claude->>Designer: Structured OfferBrief<br/>(Segment, Construct, Channels, KPIs)

    Designer->>FraudScan: Validate risk patterns
    FraudScan->>Designer: Risk report (severity: low/medium/critical)

    Marketer->>Designer: Approve offer
    Designer->>Hub: Save offer (status: approved)
    Hub->>Hub: Status transition: approved → active
    Hub->>Scout: Offer now visible in active pool

    Note over Scout: Awaiting purchase event

    Member->>Scout: POST /api/scout/match<br/>(member_id, GPS, purchase_category, rewards_earned)
    Scout->>Hub: Fetch active offers (up to 5 candidates)
    Hub->>Scout: Return active offers

    Scout->>Claude: Score context vs offer (3s timeout)
    Claude->>Scout: score: 85, rationale, notification_text

    Scout->>Scout: Check delivery constraints<br/>(CASL, 1/hr rate-limit, 24h dedup, quiet hours)
    Scout->>Member: Push notification<br/>"15% off Outdoor gear at Sport Chek"

    Scout->>Hub: Log activation (offer_id, member_id, outcome)
    Hub->>Hub: Update audit trail
```

---

## End-to-End Flow: Purchase-Triggered Offer

```mermaid
sequenceDiagram
    participant Rewards as Triangle Rewards System
    participant Scout as Scout Engine
    participant Claude as Claude API (Sonnet)
    participant FraudScan as Fraud Detection
    participant Hub as The Hub
    participant Member as Member App

    Rewards->>Scout: POST /api/scout/purchase-event<br/>(member_id, store, category, amount, GPS)
    Scout->>Scout: Verify HMAC webhook signature
    Scout->>Scout: Reject if refund or duplicate event

    Scout->>Claude: Generate OfferBrief for purchase context
    Claude->>Scout: Structured OfferBrief (trigger_type=purchase_triggered)

    Scout->>FraudScan: Validate risk patterns
    FraudScan->>Scout: Risk cleared

    Scout->>Hub: Save offer as status=active (valid_until=now+24h)

    Scout->>Scout: Score context (Claude AI, 3s timeout)
    Note over Scout: Falls back to deterministic scoring on timeout

    alt Score > 60 and constraints pass
        Scout->>Member: Push notification
        Scout->>Hub: Log activation record
    else Score ≤ 60 or constrained
        Scout->>Hub: Log queued/rate_limited outcome
    end
```

---

## End-to-End Flow: Partner-Triggered Offer (Tim Hortons)

```mermaid
sequenceDiagram
    participant Partner as Partner System (Tim Hortons)
    participant Scout as Scout Engine
    participant Haiku as Claude Haiku (classify)
    participant Sonnet as Claude Sonnet (generate)
    participant FraudScan as Fraud Detection
    participant Hub as The Hub
    participant Member as Member App

    Partner->>Scout: POST /api/scout/partner-trigger<br/>(partner_id, member_id, amount, GPS)
    Scout->>Scout: Validate partner auth token

    Scout->>Haiku: Classify purchase context (few-shot)
    alt Haiku success
        Haiku->>Scout: CTC category (e.g. "outdoor")
    else Haiku failure
        Scout->>Scout: Use _PARTNER_FALLBACK_CATEGORIES
    end

    Scout->>Sonnet: Generate OfferBrief (trigger_type=partner_triggered)
    Sonnet->>Scout: OfferBrief with PaymentSplit (75pts / 25cash)

    Scout->>FraudScan: Validate — block if severity=critical
    Scout->>Hub: Save as status=active (valid_until=now+24h)

    Scout->>Scout: Score context
    Scout->>Member: Push notification (async, HTTP 202 returned immediately)
    Scout->>Hub: Log activation record
```

---

## Smart Match — Multi-Offer Response

```mermaid
flowchart TD
    A[POST /api/scout/smart-match] --> B[Enrich context concurrently:<br/>member profile, nearby stores, weather]
    B --> C[Fetch active Hub offers]
    C --> D[Score each offer with Claude AI<br/>max 5 candidates _CANDIDATE_CAP]
    D --> E{Score > 60?}
    E -->|Yes| F[Check delivery constraints<br/>CASL, rate-limit, dedup, quiet-hours]
    E -->|No| G[Drop from results]
    F -->|Pass| H[Add to results:<br/>CTC offers priority=1<br/>Partner offers priority=2]
    F -->|Fail| I[Mark as queued/rate_limited]
    H --> J[Sort: by priority then score]
    I --> J
    J --> K[Return SmartMatchResponse<br/>list of SmartOfferItem]
```

---

## Context Matching Algorithm (Claude AI + Deterministic Fallback)

```mermaid
flowchart TD
    A[Receive MatchRequest] --> B[Enrich context concurrently]
    B --> B1[Fetch MemberProfile<br/>MockMemberProfileStore]
    B --> B2[Find Nearby CTC Stores<br/>CTCStoreFixtures < 50km]
    B --> B3[Fetch Weather<br/>OpenWeatherMap API]
    B1 & B2 & B3 --> C

    C[Build EnrichedMatchContext] --> D[Check SHA256 cache<br/>offer_id + category + hour_bucket + weather]
    D -->|Cache hit| E[Return cached score<br/>ScoringMethod=cached]
    D -->|Cache miss| F[Call Claude Sonnet<br/>asyncio.wait_for timeout=3s]

    F -->|Success| G[Parse JSON response:<br/>score, rationale, notification_text<br/>ScoringMethod=claude]
    F -->|TimeoutError or SDK error| H[Fallback: deterministic formula<br/>ScoringMethod=fallback]

    H --> H1[Location: 0-40pts<br/>< 0.5km=40, < 1km=30, < 2km=20, > 2km=0]
    H --> H2[Time: 0-30pts<br/>exact match=30, day only=20, none=0]
    H --> H3[Weather: 0-20pts<br/>exact match=20, none=0]
    H --> H4[Behavior: 0-10pts<br/>aligned=10, none=0]
    H1 & H2 & H3 & H4 --> I[Sum → deterministic score]

    G --> J{Total score > 60?}
    I --> J

    J -->|Yes| K[Check Delivery Constraints]
    J -->|No| L[NoMatchResponse<br/>or queue]

    K --> K1{CASL consent?}
    K1 -->|No| M[Block — log outcome]
    K1 -->|Yes| K2{Rate limit:<br/>1 notif/member/hr?}
    K2 -->|Exceeded| N[Outcome=rate_limited<br/>retry_after_seconds]
    K2 -->|OK| K3{24h dedup:<br/>same offer sent?}
    K3 -->|Duplicate| N
    K3 -->|OK| K4{Quiet hours:<br/>10pm-8am?}
    K4 -->|Yes| O[Outcome=queued<br/>delivery_time=next 8am]
    K4 -->|No| P[Outcome=activated<br/>Send notification]

    P --> Q[Log ScoutActivationRecord<br/>no GPS — CON-002]

    style E fill:#fff9c4
    style G fill:#c8e6c9
    style H fill:#ffecb3
    style P fill:#c8e6c9
```

---

## Component Architecture

```mermaid
graph LR
    subgraph Frontend["Frontend (React 19 + Next.js 15)"]
        A[Next.js App Router<br/>TypeScript]
        A --> B[Designer UI<br/>OfferBriefForm, FraudPanel]
        A --> C[Scout UI<br/>ContextDashboard, ActivationLog]
        A --> D[Hub UI<br/>OfferList, StatusBadge]
    end

    subgraph Backend["Backend (FastAPI, Python 3.11+)"]
        E[FastAPI App<br/>main.py]
        E --> F[Designer API<br/>/api/designer/*]
        E --> G[Scout API<br/>/api/scout/*]
        E --> H[Hub API<br/>/api/hub/*]

        F --> F1[ClaudeApiService<br/>3x retry, 5min cache]
        F --> F2[FraudCheckService]
        F --> F3[DealScraperService]
        F --> F4[InventoryService]

        G --> G1[ScoutMatchService<br/>match pipeline orchestrator]
        G --> G2[ClaudeContextScoringService<br/>AI scoring + cache]
        G --> G3[ContextScoringService<br/>deterministic fallback]
        G --> G4[DeliveryConstraintService<br/>CASL, rate-limit, dedup, quiet-hrs]
        G --> G5[PartnerTriggerService<br/>Haiku classify + Sonnet generate]
        G --> G6[PurchaseEventHandler<br/>webhook dedup + validation]
        G --> G7[NotificationService]
        G --> G8[ScoutAuditService]

        H --> H1[HubStore<br/>in-memory offer store]
        H --> H2[HubAuditService]
        H --> H3[AuditLogService]
    end

    subgraph External["External Services"]
        I[Claude Sonnet 4-6<br/>offer generation + scoring]
        J[Claude Haiku<br/>partner context classify]
        K[OpenWeatherMap API<br/>weather conditions]
    end

    subgraph Data["Data Layer"]
        L[(In-Memory HubStore<br/>offer lifecycle)]
        M[(In-Memory Audit Log<br/>activation records)]
    end

    subgraph Fixtures["Mock / Fixture Data"]
        N[CTCStoreFixtures<br/>Canadian Tire store locations]
        O[MockMemberProfileStore<br/>member segments + history]
        P[CanadianHolidayService<br/>long weekend detection]
    end

    B <-->|HTTP/JSON| F
    C <-->|HTTP/JSON| G
    D <-->|HTTP/JSON| H

    F1 <-->|Anthropic SDK| I
    G2 <-->|Anthropic SDK| I
    G5 <-->|Anthropic SDK| J
    G5 <-->|Anthropic SDK| I

    G2 --> K

    H1 --> L
    H2 --> M

    G1 --> N
    G1 --> O
    G1 --> P

    style A fill:#61dafb
    style E fill:#009688
    style I fill:#e07c3e
    style J fill:#e07c3e
```

---

## OfferBrief Schema

```mermaid
classDiagram
    class OfferBrief {
        +string offer_id
        +string objective
        +Segment segment
        +Construct construct
        +Channel[] channels
        +KPIs kpis
        +RiskFlags risk_flags
        +OfferStatus status
        +TriggerType trigger_type
        +datetime created_at
        +datetime valid_until
        +string source_deal_id
    }

    class TriggerType {
        <<enumeration>>
        marketer_initiated
        purchase_triggered
        partner_triggered
    }

    class OfferStatus {
        <<enumeration>>
        draft
        approved
        active
        expired
    }

    class Segment {
        +string name
        +string definition
        +int estimated_size
        +string[] criteria
    }

    class PaymentSplit {
        +float points_max_pct = 75.0
        +float cash_min_pct = 25.0
    }

    class Construct {
        +string type
        +float value
        +string description
        +PaymentSplit payment_split
    }

    class Channel {
        +ChannelType channel_type
        +int priority
        +string message_template
    }

    class KPIs {
        +float expected_redemption_rate
        +float expected_uplift_pct
        +int target_segment_size
    }

    class RiskFlags {
        +bool over_discounting
        +bool cannibalization
        +bool frequency_abuse
        +bool offer_stacking
        +RiskSeverity severity
        +string[] warnings
    }

    OfferBrief --> TriggerType
    OfferBrief --> OfferStatus
    OfferBrief --> Segment
    OfferBrief --> Construct
    OfferBrief --> Channel
    OfferBrief --> KPIs
    OfferBrief --> RiskFlags
    Construct --> PaymentSplit

    note for OfferBrief "AUTO_ACTIVE_TRIGGER_TYPES:\npurchase_triggered + partner_triggered\nsave directly to status=active.\nMarketer-initiated: draft → approved → active."
    note for PaymentSplit "Triangle Rewards 75/25 split:\nmax 75% paid in Triangle points\nmin 25% paid cash/card"
```

---

## Hub Offer Lifecycle

```mermaid
stateDiagram-v2
    [*] --> draft : marketer_initiated (Designer saves)
    draft --> approved : Marketer approves in Designer UI
    approved --> active : Hub status transition
    active --> expired : Offer redeemed or valid_until passed

    [*] --> active : purchase_triggered or partner_triggered\n(auto-active, valid_until = now+24h)
    active --> expired

    note right of draft
        Only marketer_initiated offers
        start as draft
    end note
    note right of active
        Scout fetches these for
        context scoring
    end note
```

---

## Scout API Endpoints

```mermaid
graph LR
    subgraph Scout["POST /api/scout/"]
        A[purchase-event<br/>Triangle rewards webhook<br/>HMAC-signed]
        B[match<br/>Score single best offer<br/>Returns MatchResponse]
        C[smart-match<br/>Score all route-relevant offers<br/>Returns SmartMatchResponse]
        D[partner-trigger<br/>Partner purchase event<br/>Haiku+Sonnet pipeline]
        E[activation-log<br/>GET audit trail]
    end

    A -->|async 202| H[PurchaseEventHandler]
    B --> M[ScoutMatchService]
    C --> M
    D -->|async 202| PT[PartnerTriggerService]
    E --> SA[ScoutAuditService]

    H --> M
    M --> CS[ClaudeContextScoringService]
    M --> DC[DeliveryConstraintService]
    PT --> Hub[(Hub Store)]
```

---

## Security Architecture

```mermaid
graph LR
    A[User Login] --> B[Azure AD B2C]
    B --> C{Valid Credentials?}
    C -->|Yes| D[Issue JWT Token<br/>1h expiry, HS256]
    C -->|No| E[Return 401]

    D --> F[Frontend stores token]
    F --> G[API Request with Bearer token]
    G --> H[FastAPI HTTPBearer dep]
    H --> I{Token valid?}
    I -->|Yes| J[Process request]
    I -->|No| K[Return 401]

    L[Scout Webhooks] --> M{ENVIRONMENT != development?}
    M -->|Yes| N[HMAC signature check<br/>SCOUT_WEBHOOK_SECRET]
    M -->|No| O[Skip signature check]
    N -->|Valid| J
    N -->|Invalid| P[Return 401]

    Q[Partner Endpoints] --> R[scout_auth dependency<br/>partner token validation]
    R --> J
```

**Auth Notes:**
- Hub GET endpoints are **public** (no auth required) — read-only offer browsing
- Designer mutation endpoints require JWT
- Scout webhooks use HMAC signature verification (skipped in `development` env)
- Partner trigger endpoints use per-partner token auth via `scout_auth` dependency

---

## Deployment Architecture

```mermaid
graph TB
    subgraph GitHub
        A[GitHub Repository]
        B[GitHub Actions<br/>CI/CD Pipeline]
    end

    subgraph Azure["Azure Cloud"]
        subgraph Compute
            C[App Service<br/>React Frontend]
            D[Azure Functions<br/>FastAPI Backend]
        end

        subgraph Data
            E[Azure Redis Cache<br/>Hub State + Delivery Constraint]
            F[Azure SQL Database<br/>Audit Log]
        end

        subgraph Ops
            G[Application Insights<br/>Telemetry & Logs]
            H[Key Vault<br/>Secrets Management]
        end

        subgraph Network
            I[Azure CDN<br/>Static Assets]
            J[API Management<br/>Rate Limiting & Auth]
        end
    end

    K[Anthropic API<br/>Sonnet + Haiku]
    L[OpenWeatherMap API]

    A --> B
    B -->|Deploy| C
    B -->|Deploy| D

    C --> I
    C --> J
    D --> J

    D --> E
    D --> F
    D --> H
    D --> K
    D --> L

    C --> G
    D --> G
```

---

## Technology Stack

### Frontend
- **Framework:** React 19 + Next.js 15 (App Router)
- **Language:** TypeScript 5.x (strict mode)
- **Styling:** Tailwind CSS
- **State:** React Context + `useOptimistic`
- **Data Fetching:** React.use() with Suspense
- **Forms:** React Server Actions
- **Testing:** Jest + React Testing Library

### Backend
- **Framework:** FastAPI 0.110+
- **Language:** Python 3.11+
- **Validation:** Pydantic v2
- **Async:** asyncio with uvicorn
- **Data Store:** In-memory dict (Hub), dev; Redis (prod)
- **Testing:** Pytest + httpx AsyncClient
- **Logging:** loguru (structured JSON)

### AI & External Services
- **Offer generation:** Claude Sonnet 4-6 (Designer + Scout purchase/partner triggers)
- **Partner classification:** Claude Haiku (fast few-shot classification)
- **Context scoring:** Claude Sonnet 4-6 with 3s timeout + deterministic fallback
- **Weather:** OpenWeatherMap API

---

## Performance Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| API Response Time (p95) | <200ms | Application Insights |
| Frontend Page Load | <2s (FCP) | Lighthouse CI |
| Scout context scoring | <3s | Claude timeout budget |
| Cache Hit Rate | >80% | 3-hour bucket SHA256 cache |
| Offer Generation Time | <5s | Claude Sonnet p95 |

---

## Development Workflow

```mermaid
graph LR
    A[Local Dev] --> B[Feature Branch]
    B --> C[Commit + Tests]
    C --> D[Push to GitHub]
    D --> E[CI Pipeline]

    E --> F[Ruff + Black]
    E --> G[pytest unit]
    E --> H[pytest integration]
    E --> I[Security scan]

    F & G & H & I --> J{Pass?}
    J -->|Yes| K[PR → main]
    J -->|No| L[Fix Issues]
    L --> C

    K --> M[Code Review]
    M --> N{Approved?}
    N -->|Yes| O[Merge to main]
    N -->|No| L

    O --> P[Deploy to Staging]
    P --> Q[E2E Tests]
    Q --> R{Pass?}
    R -->|Yes| S[Deploy to Production]
    R -->|No| T[Rollback & Debug]
```

---

**Document Version:** 2.0
**Generated:** 2026-04-05
**Maintainers:** TriStar Hackathon Team
