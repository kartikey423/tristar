# TriStar Architecture

**Project:** Triangle Smart Targeting and Real-Time Activation
**Hackathon:** CTC True North 2026 (March 9-18)
**Last Updated:** 2026-03-26

---

## Executive Summary

TriStar transforms the Triangle loyalty program from a reactive points ledger into a proactive, AI-powered engagement platform. The system combines intelligent offer design (Designer) with real-time contextual activation (Scout), connected through a shared state (Hub).

**Three Core Layers:**
1. **Designer (Marketer Copilot)** - AI-powered offer design generating OfferBriefs from business objectives
2. **The Hub (Shared Context State)** - Central repository for approved offers ready for activation
3. **Scout (Real-Time Activation Engine)** - Context-aware delivery system monitoring GPS, weather, time, and behavior

---

## System Overview

```mermaid
graph TB
    subgraph "Layer 1: Designer (Marketer Copilot)"
        A[Business Objective Input]
        B[Claude API<br/>claude-sonnet-4-6]
        C[Offer Generator]
        D[OfferBrief Output]
        E{Risk Validation<br/>Fraud Detection}
        F[Export to Hub]
        G[Fraud Alert]

        A --> B
        B --> C
        C --> D
        D --> E
        E -->|Pass| F
        E -->|Fail| G
    end

    subgraph "The Hub (Shared Context State)"
        H[(Approved Offers<br/>Redis/In-Memory)]
        I[Status Management<br/>draft → approved → active → expired]
        J[Audit Log<br/>Append-Only]

        F --> H
        H --> I
        I --> J
    end

    subgraph "Layer 2: Scout (Real-Time Activation Engine)"
        K[Context Signals]
        L[Location/GPS<br/>Proximity to Store]
        M[Weather API<br/>Temperature & Conditions]
        N[Time/Day<br/>Hour, Day of Week]
        O[Behavioral History<br/>Recent Purchases]

        P[Context Matcher<br/>Semantic Scoring]
        Q{Score > 60?}
        R[Push Notification]
        S[Queue for Later]

        K --> L
        K --> M
        K --> N
        K --> O

        L --> P
        M --> P
        N --> P
        O --> P

        H --> P
        P --> Q
        Q -->|Yes| R
        Q -->|No| S
    end

    T[Member App]
    U[Activation Log]

    R --> T
    S --> U

    style A fill:#e1f5ff
    style H fill:#fff4e1
    style K fill:#e8f5e8
    style T fill:#f0e8ff
```

---

## End-to-End Flow

```mermaid
sequenceDiagram
    actor Marketer
    participant Designer as Designer UI
    participant Claude as Claude API
    participant FraudScan as Fraud Detection
    participant Hub as The Hub
    participant Scout as Scout Engine
    participant Member as Member App

    Marketer->>Designer: Enter business objective<br/>"Reactivate lapsed high-value members"
    Designer->>Claude: Generate OfferBrief prompt
    Claude->>Designer: Structured OfferBrief<br/>(Segment, Construct, Channels, KPIs)

    Designer->>FraudScan: Validate risk patterns
    FraudScan->>Designer: Risk report (severity: low)

    Marketer->>Designer: Approve offer
    Designer->>Hub: Save offer (status: approved)
    Hub->>Hub: Status transition: approved → active
    Hub->>Scout: Notify: New offer available

    Note over Scout: Monitoring loop (1/sec)

    Member->>Scout: Context signal<br/>(GPS: 500m from store, Weather: cold)
    Scout->>Hub: Fetch active offers
    Hub->>Scout: Return offers (3 active)

    Scout->>Scout: Semantic match scoring<br/>Location: 40pts, Weather: 20pts<br/>Total: 85/100

    Scout->>Member: Push notification<br/>"15% off Outdoor gear at Sport Chek<br/>1 block away. Valid for 2 hours."

    Member->>Scout: Tap notification
    Scout->>Hub: Log activation (offer_id, member_id, timestamp)
    Hub->>Hub: Update audit trail

    Note over Member,Scout: Member redeems at store

    Scout->>Hub: Mark offer redeemed
    Hub->>Hub: Status transition: active → expired
```

---

## Component Architecture

```mermaid
graph LR
    subgraph Frontend
        A[React 19 App<br/>TypeScript]
        A --> B[Designer UI<br/>OfferBriefForm]
        A --> C[Scout UI<br/>ContextDashboard]
        A --> D[Hub UI<br/>OfferList]
    end

    subgraph Backend
        E[FastAPI<br/>Python 3.11+]
        E --> F[Designer API<br/>/api/designer/*]
        E --> G[Scout API<br/>/api/scout/*]
        E --> H[Hub API<br/>/api/hub/*]
    end

    subgraph "External Services"
        I[Claude API<br/>claude-sonnet-4-6]
        J[Weather API<br/>OpenWeatherMap]
        K[Mock Triangle Data<br/>MCP Server]
    end

    subgraph "Data Layer"
        L[(Redis Cache<br/>Hub State)]
        M[(SQLite/PostgreSQL<br/>Audit Log)]
    end

    B <-->|HTTP/JSON| F
    C <-->|HTTP/JSON| G
    D <-->|HTTP/JSON| H

    F <-->|Anthropic SDK| I
    F <-->|MCP Protocol| K

    G <-->|HTTP| J
    G <-->|MCP Protocol| K

    H <-->|Read/Write| L
    H <-->|Append| M

    style A fill:#61dafb
    style E fill:#009688
    style I fill:#e07c3e
    style L fill:#dc382d
```

---

## Data Flow: OfferBrief Schema

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
        +datetime created_at
        +string status
        +validateSchema() boolean
    }

    class Segment {
        +string name
        +string definition
        +number estimated_size
        +string[] criteria
        +string[] exclusions
    }

    class Construct {
        +string type
        +number value
        +string description
        +datetime valid_from
        +datetime valid_until
    }

    class Channel {
        +string channel_type
        +number priority
        +string[] delivery_rules
    }

    class KPIs {
        +number expected_redemption_rate
        +number expected_uplift_pct
        +number estimated_cost_per_redemption
        +number roi_projection
        +number target_reach
    }

    class RiskFlags {
        +boolean over_discounting
        +boolean cannibalization
        +boolean frequency_abuse
        +boolean offer_stacking
        +string[] warnings
        +string severity
    }

    OfferBrief --> Segment
    OfferBrief --> Construct
    OfferBrief --> Channel
    OfferBrief --> KPIs
    OfferBrief --> RiskFlags

    note for OfferBrief "Central data structure\nShared between Designer, Hub, Scout\nValidated with Zod (TS) + Pydantic (Python)"
```

---

## Context Matching Algorithm

```mermaid
flowchart TD
    A[Receive Context Signal] --> B{Location within 2km?}

    B -->|Yes, <0.5km| C[Location: +40 points]
    B -->|Yes, 0.5-1km| D[Location: +30 points]
    B -->|Yes, 1-2km| E[Location: +20 points]
    B -->|No, >2km| F[Location: +0 points]

    C --> G{Time matches preferred hours?}
    D --> G
    E --> G
    F --> G

    G -->|Exact match| H[Time: +30 points]
    G -->|Day match only| I[Time: +20 points]
    G -->|No match| J[Time: +0 points]

    H --> K{Weather trigger match?}
    I --> K
    J --> K

    K -->|Exact match| L[Weather: +20 points]
    K -->|No match| M[Weather: +0 points]

    L --> N{Behavior aligned with recent activity?}
    M --> N

    N -->|Yes| O[Behavior: +10 points]
    N -->|No| P[Behavior: +0 points]

    O --> Q[Calculate Total Score]
    P --> Q

    Q --> R{Total score > 60?}

    R -->|Yes| S[Activate Offer<br/>Send Notification]
    R -->|No| T[Queue for Later<br/>Log Context]

    S --> U[Log to Hub Audit Trail]
    T --> V[Increment Queue Counter]

    style A fill:#e1f5ff
    style S fill:#c8e6c9
    style T fill:#ffecb3
    style R fill:#fff9c4

    note1[Scoring Breakdown<br/>Location: 40pts max<br/>Time: 30pts max<br/>Weather: 20pts max<br/>Behavior: 10pts max<br/>Total: 100pts possible]
```

---

## Deployment Architecture

```mermaid
graph TB
    subgraph "GitHub"
        A[GitHub Repository<br/>tristar-hackathon]
        B[GitHub Actions<br/>CI/CD Pipeline]
    end

    subgraph "Azure Cloud"
        subgraph "Compute"
            C[App Service<br/>React Frontend]
            D[Azure Functions<br/>FastAPI Backend]
        end

        subgraph "Data & Cache"
            E[Azure Redis Cache<br/>Hub State]
            F[Azure SQL Database<br/>Audit Log]
        end

        subgraph "Monitoring & Secrets"
            G[Application Insights<br/>Telemetry & Logs]
            H[Key Vault<br/>Secrets Management]
        end

        subgraph "Networking"
            I[Azure CDN<br/>Static Assets]
            J[API Management<br/>Rate Limiting & Auth]
        end
    end

    K[External APIs]
    L[Claude API]
    M[Weather API]

    A --> B
    B -->|Deploy Frontend| C
    B -->|Deploy Backend| D

    C --> I
    C --> J
    D --> J

    D --> E
    D --> F
    D --> H

    C --> G
    D --> G

    J --> L
    J --> M

    K --> L
    K --> M

    style A fill:#181717
    style C fill:#0078d4
    style D fill:#0078d4
    style E fill:#dc382d
    style F fill:#0078d4
    style G fill:#0078d4
    style H fill:#0078d4

    note1[Development:<br/>- Frontend: localhost:3000<br/>- Backend: localhost:8000<br/>- Redis: localhost:6379]

    note2[Production:<br/>- Frontend: https://tristar.azurewebsites.net<br/>- Backend: https://tristar-api.azurefunctions.net<br/>- Redis: tristar-cache.redis.cache.windows.net]
```

---

## Technology Stack

### Frontend
- **Framework:** React 19 (with Server Components)
- **Language:** TypeScript 5.x (strict mode)
- **Styling:** Tailwind CSS or Styled Components
- **State Management:** React Context + `useOptimistic`
- **Data Fetching:** React.use() with Suspense
- **Forms:** React Server Actions
- **Testing:** Jest + React Testing Library
- **Build Tool:** Vite or Next.js 15+

### Backend
- **Framework:** FastAPI 0.110+
- **Language:** Python 3.11+
- **Validation:** Pydantic v2
- **Async Runtime:** asyncio with uvicorn
- **Database:** SQLite (dev), PostgreSQL (prod)
- **Cache:** Redis 7.x
- **Testing:** Pytest + httpx
- **Logging:** loguru

### AI & External Services
- **LLM:** Claude API (claude-sonnet-4-6)
- **Weather:** OpenWeatherMap API
- **Mock Data:** MCP Server (@tristar/mock-triangle-data)

### Infrastructure
- **Cloud:** Microsoft Azure
- **Compute:** App Service (frontend), Azure Functions (backend)
- **Data:** Azure Redis Cache, Azure SQL Database
- **Monitoring:** Application Insights
- **Secrets:** Azure Key Vault
- **CI/CD:** GitHub Actions
- **IaC:** Terraform

---

## Security Architecture

### Authentication & Authorization
```mermaid
graph LR
    A[User Login] --> B[Azure AD B2C]
    B --> C{Valid Credentials?}
    C -->|Yes| D[Issue JWT Token]
    C -->|No| E[Return 401]

    D --> F[Frontend Stores Token]
    F --> G[API Request with Token]
    G --> H[API Gateway Validates Token]
    H --> I{Token Valid?}
    I -->|Yes| J[Forward to Backend]
    I -->|No| K[Return 401]

    J --> L[Backend Checks Permissions]
    L --> M{Authorized?}
    M -->|Yes| N[Process Request]
    M -->|No| O[Return 403]
```

### Data Flow Security
- **In Transit:** TLS 1.3 for all HTTP traffic
- **At Rest:** Azure Storage encryption (256-bit AES)
- **Secrets:** Azure Key Vault with managed identities
- **PII Handling:** Log member_id only, no names/emails/addresses
- **Rate Limiting:** 100 requests/min per IP (API Management)

---

## Performance Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| API Response Time (p95) | <200ms | Application Insights |
| Frontend Page Load | <2s (FCP) | Lighthouse CI |
| Context Matching Latency | <500ms | Custom timer |
| Cache Hit Rate | >80% | Redis INFO stats |
| Offer Generation Time | <5s | Claude API latency |

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
2. **Caching:** Redis cluster with read replicas
3. **Database:** Sharding by member_id (10M members = 10 shards)
4. **CDN:** Azure CDN for static assets and API responses
5. **Async Processing:** Queue context signals, process in batches

---

## Development Workflow

```mermaid
graph LR
    A[Local Development] --> B[Feature Branch]
    B --> C[Commit with Tests]
    C --> D[Push to GitHub]
    D --> E[CI Pipeline]

    E --> F[Run Linters]
    E --> G[Run Unit Tests]
    E --> H[Run Integration Tests]
    E --> I[Security Scan]

    F --> J{All Checks Pass?}
    G --> J
    H --> J
    I --> J

    J -->|Yes| K[Create Pull Request]
    J -->|No| L[Fix Issues]
    L --> C

    K --> M[Code Review]
    M --> N{Approved?}
    N -->|Yes| O[Merge to Main]
    N -->|No| L

    O --> P[Deploy to Staging]
    P --> Q[E2E Tests on Staging]
    Q --> R{Tests Pass?}
    R -->|Yes| S[Deploy to Production]
    R -->|No| T[Rollback & Debug]
```

---

## Monitoring & Observability

### Metrics to Track
1. **Business Metrics:**
   - Offer generation rate (offers/hour)
   - Activation rate (notifications/hour)
   - Redemption rate (redeemed/activated)
   - ROI per offer (revenue - cost)

2. **Technical Metrics:**
   - API latency (p50, p95, p99)
   - Error rate (5xx responses)
   - Cache hit rate
   - Database query time

3. **User Experience:**
   - Frontend page load time
   - Time to interactive (TTI)
   - Notification delivery success rate

### Dashboards
- **Application Insights:** Real-time telemetry, logs, traces
- **Grafana:** Custom dashboards for business metrics
- **Azure Monitor:** Infrastructure health, resource utilization

---

## Disaster Recovery

### Backup Strategy
- **Redis:** Daily snapshots to Azure Blob Storage
- **SQL Database:** Automated backups (7-day retention)
- **Code:** Git repository (multiple remotes)

### Recovery Time Objectives (RTO)
- **Database Failure:** <15 minutes (restore from backup)
- **Redis Failure:** <5 minutes (failover to replica)
- **Complete Region Failure:** <4 hours (redeploy to new region)

---

## Future Enhancements

### Phase 2 (Post-Hackathon)
- **Machine Learning:** Predictive context matching using historical data
- **A/B Testing:** Experimentation framework for offer variants
- **Multi-Language:** French language support for Quebec members
- **Partner Integration:** Real-time inventory sync with stores

### Phase 3 (Production)
- **Mobile Apps:** Native iOS/Android apps with offline support
- **Voice Activation:** Integration with Alexa/Google Assistant
- **Blockchain:** Immutable audit trail for compliance
- **AI Agents:** Multi-agent orchestration for complex campaigns

---

**Document Version:** 1.0
**Generated:** 2026-03-26
**Maintainers:** TriStar Hackathon Team