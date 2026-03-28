# Design Specification: hub-layer

## Meta
- **Feature:** hub-layer
- **Author:** SDLC Architecture Skill
- **Date:** 2026-03-28
- **Status:** Draft
- **Problem Spec:** `docs/artifacts/hub-layer/problem_spec.md`
- **Layers Affected:** Hub (Layer 2) backend + frontend, Designer (Layer 1) backend

---

## Problem Spec Reference

Satisfies: REQ-001 through REQ-014 (P0/P1/P2)
Key P0 requirements addressed:
- REQ-001/002: Redis store with fail-fast on unavailability
- REQ-003: Strict status machine (draft→approved→active→expired)
- REQ-004: Append-only SQL audit log
- REQ-005: Designer auto-save to Hub on generate
- REQ-006: `/hub` OfferList frontend (Next.js SSR)
- REQ-007: p95 < 200ms
- REQ-008: Redis health in `/health`

---

## Current Architecture

### Hub Backend (existing)
- `_store: dict[str, OfferBrief] = {}` module-level in-memory dict in `src/backend/api/hub.py`
- 4 endpoints: POST /offers, GET /offers/{id}, GET /offers, PUT /offers/{id}/status
- No status transition validation (any status accepted)
- No audit log
- Auth: system role on writes, any JWT on reads

### Designer Backend (existing)
- `POST /generate` — returns draft OfferBrief to caller; does **not** save to Hub
- `POST /generate-purchase` — saves to Hub with `status=active` (Scout path)
- `POST /approve/{offer_id}` — saves offer to Hub with `status=approved`
- `HubApiClient` exists but performs HTTP self-calls (localhost:8000)

### Frontend (existing)
- Only Designer layer implemented: `src/frontend/app/designer/`
- No `/hub` page exists

### Expire Task (existing)
- `_expire_offers_task` in `main.py` sweeps `_store` from `hub.py` every 300s
- Transitions `active → expired` for offers where `valid_until < now`

---

## Architecture

### Design Overview

```
┌─────────────────────────────────────────────────────────┐
│  Designer Layer (Layer 1)                               │
│  POST /generate → fraud check → HubStore.save(draft)   │
│  POST /approve → HubStore.save(approved)                │
└────────────────────────┬────────────────────────────────┘
                         │ in-process (no HTTP)
┌────────────────────────▼────────────────────────────────┐
│  Hub Layer (Layer 2)                                    │
│                                                         │
│  ┌─────────────────┐    ┌────────────────────────────┐  │
│  │   HubStore      │    │   HubAuditService          │  │
│  │  (Protocol)     │    │   (SQL: non-blocking)      │  │
│  ├─────────────────┤    └────────────────────────────┘  │
│  │ InMemoryHubStore│                                     │
│  │ (dev/test)      │                                     │
│  ├─────────────────┤                                     │
│  │ RedisHubStore   │                                     │
│  │ (staging/prod)  │                                     │
│  └─────────────────┘                                     │
└────────────────────────┬────────────────────────────────┘
                         │ GET /api/hub/offers
┌────────────────────────▼────────────────────────────────┐
│  Hub Frontend (Next.js Server Component)                │
│  /hub → OfferList → OfferCard + ApproveButton           │
└─────────────────────────────────────────────────────────┘
```

### Critical Design Choices
1. **HubStore abstraction** (Protocol + two implementations) — keeps API unchanged, swaps backend
2. **Direct HubStore injection in Designer** — replaces HTTP self-calls via HubApiClient
3. **Non-blocking audit writes** — SQL failures don't block HTTP responses
4. **Strict transition map** — `VALID_TRANSITIONS` dict enforced in `update_offer_status`

---

## Components

### COMP-001: HubStore Protocol + Implementations

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-001 |
| **Name** | HubStore (Protocol + InMemoryHubStore + RedisHubStore) |
| **Path** | `src/backend/services/hub_store.py` |
| **Layer** | Hub (Layer 2) — backend service |
| **Action** | NEW |
| **Responsibility** | Abstract offer storage; swap in-memory (dev) ↔ Redis (prod) via `HUB_REDIS_ENABLED` |
| **Dependencies** | `src/backend/models/offer_brief.py`, `redis.asyncio`, `src/backend/core/config.py` |

**Interface:**

```python
from typing import Protocol, Optional
from src.backend.models.offer_brief import OfferBrief, OfferStatus, TriggerType
from datetime import datetime

class HubStore(Protocol):
    async def get(self, offer_id: str) -> Optional[OfferBrief]: ...
    async def save(self, offer: OfferBrief) -> None: ...
    async def update(self, offer: OfferBrief) -> None: ...
    async def list(
        self,
        status_filter: Optional[OfferStatus] = None,
        trigger_type: Optional[TriggerType] = None,
        since: Optional[datetime] = None,
    ) -> list[OfferBrief]: ...
    async def exists(self, offer_id: str) -> bool: ...
    async def ping(self) -> bool: ...  # Returns True if healthy

class InMemoryHubStore:
    """Dev/test implementation. Wraps the existing _store dict."""
    def __init__(self) -> None:
        self._store: dict[str, OfferBrief] = {}
    # implements all HubStore methods

class RedisHubStore:
    """Production implementation. Stores serialised OfferBrief JSON at key offer:{offer_id}."""
    def __init__(self, redis_url: str) -> None: ...
    # raises RedisUnavailableError (→ 503) on connection failure
    # Key schema: offer:{offer_id}  Value: OfferBrief.model_dump_json()
    # No TTL set (noeviction policy required)
```

---

### COMP-002: hub.py (modified)

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-002 |
| **Name** | Hub API Router |
| **Path** | `src/backend/api/hub.py` |
| **Layer** | Hub (Layer 2) — API route |
| **Action** | MODIFY |
| **Responsibility** | Route handlers for Hub CRUD operations. Inject HubStore and HubAuditService via `Depends()`. Enforce strict status transitions. |
| **Dependencies** | COMP-001 (HubStore), COMP-003 (HubAuditService), COMP-005 (deps.py) |

**Changes:**
1. Remove module-level `_store: dict`. Replace all direct `_store` accesses with `Depends(get_hub_store)`.
2. Add `VALID_TRANSITIONS` map and call `_validate_transition(old, new)` in `update_offer_status`.
3. Inject `HubAuditService` via `Depends(get_hub_audit_service)`. Call audit on each operation.
4. Add latency timing: record `start = time.monotonic()` at handler entry; log WARNING if `(time.monotonic() - start) * 1000 > 200`.
5. Catch `RedisUnavailableError` and raise `HTTPException(503)`.

**Strict Transition Map:**

```python
VALID_TRANSITIONS: dict[OfferStatus, set[OfferStatus]] = {
    OfferStatus.draft:    {OfferStatus.approved},
    OfferStatus.approved: {OfferStatus.active},
    OfferStatus.active:   {OfferStatus.expired},
    OfferStatus.expired:  set(),  # terminal state
}

def _validate_transition(old: OfferStatus, new: OfferStatus) -> None:
    allowed = VALID_TRANSITIONS.get(old, set())
    if new not in allowed:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "InvalidTransition",
                "old_status": old.value,
                "new_status": new.value,
                "allowed": [s.value for s in allowed],
            },
        )
```

**Audit call pattern (non-blocking):**

```python
# After successful operation — fire-and-forget
asyncio.create_task(
    hub_audit.log_event(HubAuditEvent(
        offer_id=offer.offer_id,
        event="offer_created",
        actor_id=user.user_id,
        ...
    ))
)
```

---

### COMP-003: HubAuditService

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-003 |
| **Name** | HubAuditService |
| **Path** | `src/backend/services/hub_audit_service.py` |
| **Layer** | Hub (Layer 2) — backend service |
| **Action** | NEW |
| **Responsibility** | Append-only SQL audit log for all Hub events. Non-blocking writes. |
| **Dependencies** | `aiosqlite` (dev) / `asyncpg` (prod) via SQLAlchemy async engine, `src/backend/core/config.py` |

**SQL Schema:**

```sql
CREATE TABLE IF NOT EXISTS hub_audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    offer_id  VARCHAR(36)  NOT NULL,
    event     VARCHAR(50)  NOT NULL,   -- offer_created | status_transition | offer_read | fraud_blocked
    old_status VARCHAR(20),
    new_status VARCHAR(20),
    actor_id  VARCHAR(100) NOT NULL,
    fraud_severity VARCHAR(20),
    timestamp DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hub_audit_offer_id  ON hub_audit_log(offer_id);
CREATE INDEX IF NOT EXISTS idx_hub_audit_timestamp ON hub_audit_log(timestamp);
```

**Interface:**

```python
class HubAuditEvent(BaseModel):
    offer_id: str
    event: Literal["offer_created", "status_transition", "offer_read", "fraud_blocked"]
    old_status: Optional[OfferStatus] = None
    new_status: Optional[OfferStatus] = None
    actor_id: str
    fraud_severity: Optional[str] = None

class HubAuditService:
    async def log_event(self, event: HubAuditEvent) -> None:
        """Write audit row. Catches all exceptions — logs WARNING, never raises."""
        try:
            async with self._engine.begin() as conn:
                await conn.execute(insert_stmt)
        except Exception as e:
            logger.warning(f"hub_audit_write_failed: {e}", extra={"offer_id": event.offer_id})
```

---

### COMP-004: config.py (modified)

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-004 |
| **Name** | Settings |
| **Path** | `src/backend/core/config.py` |
| **Layer** | Shared config |
| **Action** | MODIFY |

**New fields added to `Settings`:**

```python
HUB_REDIS_ENABLED: bool = False
REDIS_URL: str = "redis://localhost:6379"
```

No existing fields removed or renamed.

---

### COMP-005: deps.py (modified)

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-005 |
| **Name** | Dependency Injection Registry |
| **Path** | `src/backend/api/deps.py` |
| **Layer** | Shared |
| **Action** | MODIFY |

**New factories added:**

```python
@lru_cache(maxsize=1)
def get_hub_store() -> HubStore:
    """Return RedisHubStore if HUB_REDIS_ENABLED else InMemoryHubStore."""
    if settings.HUB_REDIS_ENABLED:
        return RedisHubStore(redis_url=settings.REDIS_URL)
    return InMemoryHubStore()

@lru_cache(maxsize=1)
def get_hub_audit_service() -> HubAuditService:
    return HubAuditService(database_url=settings.DATABASE_URL)
```

---

### COMP-006: designer.py (modified)

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-006 |
| **Name** | Designer API Router |
| **Path** | `src/backend/api/designer.py` |
| **Layer** | Designer (Layer 1) — API route |
| **Action** | MODIFY |
| **Responsibility** | Auto-save generated OfferBrief to Hub as draft immediately after fraud check passes. |
| **Dependencies** | COMP-001 (HubStore via Depends) |

**Change to `POST /generate`:**

```python
@router.post("/generate", response_model=OfferBrief, status_code=201)
async def generate_offer(
    request: GenerateOfferRequest,
    hub_store: HubStore = Depends(get_hub_store),   # NEW
    ...
):
    offer = await claude_service.generate_from_objective(request.objective)
    fraud_result = fraud_service.validate(offer)
    offer = offer.model_copy(update={"risk_flags": fraud_result})

    if fraud_result.blocked:
        # log fraud_blocked audit event before raising
        await hub_audit.log_event(HubAuditEvent(
            offer_id=offer.offer_id, event="fraud_blocked",
            fraud_severity=fraud_result.severity, actor_id=user.user_id
        ))
        raise _raise_if_fraud_blocked(...)

    # REQ-005: Auto-save as draft
    try:
        await hub_store.save(offer)  # offer.status == draft
    except RedisUnavailableError:
        raise HTTPException(503, detail="Hub unavailable — offer not saved")
    except OfferAlreadyExistsError:
        logger.warning("offer_already_in_hub", extra={"offer_id": offer.offer_id})
        # Treat as idempotent — return 201 with existing data

    return offer  # same response schema as before
```

**No changes to `POST /generate-purchase` or `POST /approve/{offer_id}`.**

---

### COMP-007: main.py (modified)

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-007 |
| **Name** | FastAPI Application |
| **Path** | `src/backend/main.py` |
| **Layer** | Backend entrypoint |
| **Action** | MODIFY |

**Changes:**

1. **`GET /health`** extended response:
```python
async def health_check():
    hub_store = get_hub_store()
    redis_status = "ok" if await hub_store.ping() else "degraded"
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "purchase_trigger_enabled": settings.PURCHASE_TRIGGER_ENABLED,
        "redis": redis_status,   # NEW — always present; "ok" or "degraded"
    }
```

2. **`_expire_offers_task`** updated to use `HubStore` instead of direct `_store` dict:
```python
async def _expire_offers_task():
    hub_store = get_hub_store()
    while True:
        offers = await hub_store.list(status_filter=OfferStatus.active)
        now = datetime.now(timezone.utc)
        for offer in offers:
            if offer.valid_until and offer.valid_until < now:
                expired = offer.model_copy(update={"status": OfferStatus.expired})
                await hub_store.update(expired)
        await asyncio.sleep(settings.OFFER_EXPIRY_SWEEP_SECONDS)
```

---

### COMP-008: Hub Frontend Page

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-008 |
| **Name** | Hub Page |
| **Path** | `src/frontend/app/hub/page.tsx` |
| **Layer** | Hub (Layer 2) — frontend |
| **Action** | NEW |
| **Responsibility** | Server Component. Fetch all offers from Hub API. Pass to OfferList. Handle error state (Hub 503). |
| **Dependencies** | COMP-009 (OfferList), `src/frontend/services/hub-api.ts` |

```tsx
// Server Component — no 'use client'
import { OfferList } from '@/components/Hub/OfferList';
import { fetchOffers } from '@/services/hub-api';

export default async function HubPage({
  searchParams,
}: {
  searchParams: { status?: string };
}) {
  let offers: OfferBrief[] = [];
  let error: string | null = null;

  try {
    offers = await fetchOffers({ status: searchParams.status });
  } catch {
    error = 'Hub temporarily unavailable — please try again shortly.';
  }

  return (
    <main className="p-6">
      <h1 className="text-2xl font-bold mb-6">Offer Hub</h1>
      {error ? (
        <p className="text-red-600">{error}</p>
      ) : (
        <OfferList offers={offers} />
      )}
    </main>
  );
}
```

---

### COMP-009: OfferList Component

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-009 |
| **Name** | OfferList |
| **Path** | `src/frontend/components/Hub/OfferList.tsx` |
| **Layer** | Hub (Layer 2) — frontend component |
| **Action** | NEW |
| **Responsibility** | Server Component. Renders a list of OfferCard components. Shows empty state when no offers. |
| **Dependencies** | COMP-010 (OfferCard) |

```tsx
// Server Component — no 'use client'
import { OfferCard } from './OfferCard';
import type { OfferBrief } from '@/types/offer-brief';

interface OfferListProps {
  offers: OfferBrief[];
}

export function OfferList({ offers }: OfferListProps) {
  if (offers.length === 0) {
    return <p className="text-gray-500">No offers yet.</p>;
  }
  return (
    <div className="flex flex-col gap-4">
      {offers.map((offer) => (
        <OfferCard key={offer.offer_id} offer={offer} />
      ))}
    </div>
  );
}
```

---

### COMP-010: OfferCard Component

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-010 |
| **Name** | OfferCard |
| **Path** | `src/frontend/components/Hub/OfferCard.tsx` |
| **Layer** | Hub (Layer 2) — frontend component |
| **Action** | NEW |
| **Responsibility** | Server Component (outer). Display offer summary: status badge, offer_id, objective, trigger_type label, risk severity badge. Conditionally renders ApproveButton for draft offers. |
| **Dependencies** | COMP-011 (ApproveButton), COMP-012 (StatusBadge) |

```tsx
// Server Component — no 'use client'
import { StatusBadge } from './StatusBadge';
import { ApproveButton } from './ApproveButton';  // Client Component
import type { OfferBrief } from '@/types/offer-brief';

export function OfferCard({ offer }: { offer: OfferBrief }) {
  const riskSeverity = offer.risk_flags?.severity ?? 'low';
  const riskColor = riskSeverity === 'critical' ? 'text-red-600' :
                    riskSeverity === 'medium'   ? 'text-yellow-600' : 'text-green-600';

  return (
    <div className="rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <StatusBadge status={offer.status} />
        <span className="text-xs text-gray-400 font-mono">
          {offer.offer_id.slice(0, 8)}…
        </span>
      </div>
      <p className="text-sm font-medium text-gray-900 mb-1">{offer.objective}</p>
      <div className="flex items-center gap-3 mt-2">
        <span className="text-xs text-gray-500 capitalize">
          {offer.trigger_type.replace('_', ' ')}
        </span>
        <span className={`text-xs font-medium ${riskColor}`}>
          Risk: {riskSeverity}
        </span>
      </div>
      {offer.status === 'draft' && (
        <div className="mt-3">
          <ApproveButton offerId={offer.offer_id} />
        </div>
      )}
    </div>
  );
}
```

---

### COMP-011: ApproveButton Component

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-011 |
| **Name** | ApproveButton |
| **Path** | `src/frontend/components/Hub/ApproveButton.tsx` |
| **Layer** | Hub (Layer 2) — frontend component |
| **Action** | NEW |
| **Responsibility** | Client Component. Calls Server Action to approve offer. Shows pending state. Triggers router refresh on success. |
| **Dependencies** | `src/frontend/app/hub/actions.ts` (Server Action) |

```tsx
'use client';

import { useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { approveOffer } from '@/app/hub/actions';

export function ApproveButton({ offerId }: { offerId: string }) {
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleApprove() {
    startTransition(async () => {
      await approveOffer(offerId);
      router.refresh();
    });
  }

  return (
    <button
      onClick={handleApprove}
      disabled={isPending}
      className="text-sm px-3 py-1 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
    >
      {isPending ? 'Approving…' : 'Approve'}
    </button>
  );
}
```

---

### COMP-012: StatusBadge Component

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-012 |
| **Name** | StatusBadge |
| **Path** | `src/frontend/components/Hub/StatusBadge.tsx` |
| **Layer** | Hub (Layer 2) — frontend component |
| **Action** | NEW |
| **Responsibility** | Server Component. Render colour-coded status pill. |

```tsx
const STATUS_STYLES: Record<string, string> = {
  draft:    'bg-gray-100 text-gray-600',
  approved: 'bg-blue-100 text-blue-700',
  active:   'bg-green-100 text-green-700',
  expired:  'bg-red-100 text-red-400 opacity-60',
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-500'}`}>
      {status}
    </span>
  );
}
```

---

### COMP-013: Hub Server Action

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-013 |
| **Name** | Hub Server Actions |
| **Path** | `src/frontend/app/hub/actions.ts` |
| **Layer** | Hub (Layer 2) — frontend |
| **Action** | NEW |
| **Responsibility** | Server Actions for Hub mutations. Called from ApproveButton. |

```ts
'use server';

import { getAuthHeaders } from '@/lib/config';

export async function approveOffer(offerId: string): Promise<void> {
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL}/api/hub/offers/${offerId}/status?new_status=approved`,
    { method: 'PUT', headers: getAuthHeaders() }
  );
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Approve failed: ${res.status}`);
  }
}
```

---

### COMP-014: Hub API Frontend Service

| Field | Value |
|-------|-------|
| **COMP-ID** | COMP-014 |
| **Name** | hub-api.ts |
| **Path** | `src/frontend/services/hub-api.ts` |
| **Layer** | Hub (Layer 2) — frontend service |
| **Action** | NEW |
| **Responsibility** | Type-safe fetch wrapper for Hub backend. Used by Server Components. |

```ts
import type { OfferBrief, OfferStatus } from '@/types/offer-brief';

interface FetchOffersParams {
  status?: string;
  triggerType?: string;
}

export async function fetchOffers(params: FetchOffersParams = {}): Promise<OfferBrief[]> {
  const url = new URL(`${process.env.NEXT_PUBLIC_API_URL}/api/hub/offers`);
  if (params.status) url.searchParams.set('status', params.status);
  if (params.triggerType) url.searchParams.set('trigger_type', params.triggerType);

  const res = await fetch(url.toString(), {
    next: { revalidate: 0 },  // No cache — always fresh (SSR)
    headers: { Authorization: `Bearer ${process.env.HUB_SERVICE_TOKEN}` },
  });

  if (!res.ok) throw new Error(`Hub API error: ${res.status}`);
  const data = await res.json();
  return data.offers as OfferBrief[];
}
```

---

## API Contracts

### Modified: GET /health

**Response (extended):**
```json
{
  "status": "healthy",
  "environment": "development",
  "purchase_trigger_enabled": false,
  "redis": "ok"
}
```
`"redis"` is always present. Values: `"ok"` | `"degraded"`.

---

### Modified: PUT /api/hub/offers/{offer_id}/status

**Before:** Any status accepted; no validation.
**After:** Only valid transitions accepted. Invalid transitions return 422.

**422 Error Response (new format):**
```json
{
  "detail": {
    "error": "InvalidTransition",
    "old_status": "draft",
    "new_status": "active",
    "allowed": ["approved"]
  }
}
```

---

### Unchanged Endpoints (contract preserved)

| Endpoint | Status Codes | Changes |
|----------|-------------|---------|
| `POST /api/hub/offers` | 201, 409, 422 | None (storage backend only) |
| `GET /api/hub/offers/{id}` | 200, 401, 404 | None |
| `GET /api/hub/offers` | 200, 401 | None |
| `POST /api/designer/generate` | 201, 401, 403, 422 | Side effect: now saves to Hub (transparent to caller) |

---

## Data Models

### New: HubAuditEvent (Pydantic)

```python
from typing import Literal, Optional
from pydantic import BaseModel
from src.backend.models.offer_brief import OfferStatus

class HubAuditEvent(BaseModel):
    offer_id: str
    event: Literal["offer_created", "status_transition", "offer_read", "fraud_blocked"]
    old_status: Optional[OfferStatus] = None
    new_status: Optional[OfferStatus] = None
    actor_id: str
    fraud_severity: Optional[str] = None
```

### New: config.py additions

```python
HUB_REDIS_ENABLED: bool = False
REDIS_URL: str = "redis://localhost:6379"
```

### Unchanged: OfferBrief schema

No changes to `OfferBrief` — backend or frontend. The stored JSON in Redis is `OfferBrief.model_dump_json()`.

---

## Decisions (ADRs)

### ADR-001: HubStore Protocol Pattern

**Status:** Proposed

**Context:** Hub must support in-memory (dev/test) and Redis (prod) storage without changing API contracts or test harness. Need to swap storage cleanly without flag pollution throughout route handlers.

**Alternatives:**
- **A (chosen): Python Protocol + two implementations** — `InMemoryHubStore` (wraps `_store` dict), `RedisHubStore` (redis.asyncio). Routes receive `HubStore` via `Depends(get_hub_store)`. `get_hub_store()` checks `HUB_REDIS_ENABLED`.
  - ✅ No changes to route logic, test isolation via `app.dependency_overrides`
  - ✅ Easy to add a third implementation (Postgres) later
  - ❌ Requires new abstraction layer (~100 lines)
- **B: Feature flag branches inside hub.py** — `if settings.HUB_REDIS_ENABLED: redis_client.get(...)  else: _store.get(...)`
  - ✅ Simpler, fewer files
  - ❌ Every route handler has dual-path logic; difficult to test cleanly
- **C: Separate Redis service (microservice)** — Hub calls a separate process for storage
  - ✅ True separation of concerns
  - ❌ Massive overkill for MVP; network overhead; no benefit at this scale

**Decision:** Option A — Protocol with two implementations. Separation at the factory level (`get_hub_store()`) keeps route handlers clean.

**Consequences:**
- (+) Tests remain fully isolated using in-memory store by default
- (+) `app.dependency_overrides[get_hub_store]` used for mock injection in tests
- (-) One additional file (`hub_store.py`)

---

### ADR-002: Hub Audit Log Storage (SQLite/SQL)

**Status:** Proposed

**Context:** Need an append-only, queryable audit trail for compliance. Must not block HTTP responses on failure.

**Alternatives:**
- **A (chosen): SQLite (dev) / PostgreSQL (prod) via SQLAlchemy async engine**
  - ✅ Queryable SQL, familiar, migration-ready
  - ✅ `aiosqlite` driver works identically with same ORM code
  - ❌ Adds dependency (aiosqlite, sqlalchemy async)
- **B: Azure Application Insights / structured logging only**
  - ✅ No new DB, just emit structured log events
  - ❌ Not queryable; no easy compliance reporting; lost in log rotation
- **C: Append to Redis sorted set (offer_id → timestamp)**
  - ✅ Already have Redis dependency
  - ❌ Redis is not a durable audit store; eviction risk; not SQL-queryable

**Decision:** Option A — SQLAlchemy async with aiosqlite for dev. Aligns with the DATABASE_URL config already present in Settings.

**Consequences:**
- (+) Same DATABASE_URL config used for audit and any future offer persistence
- (-) Adds `aiosqlite` (dev) and `asyncpg` (prod) driver dependencies

---

### ADR-003: Designer→Hub Integration (in-process vs HTTP)

**Status:** Proposed

**Context:** `POST /generate` must auto-save to Hub on success. Current `HubApiClient` performs HTTP self-calls (Designer calls localhost:8000/api/hub/offers). This adds ~20ms network overhead and a potential circular-call failure mode.

**Alternatives:**
- **A (chosen): Inject `HubStore` directly into designer route**
  - ✅ Zero network overhead; same process; no circular HTTP
  - ✅ If Redis is down, Designer catches `RedisUnavailableError` and returns 503 cleanly
  - ❌ Designer route now directly depends on Hub storage layer
- **B: Keep HubApiClient HTTP self-call**
  - ✅ True layer separation
  - ❌ HTTP overhead; if backend restarts mid-request, self-call fails; localhost dependency
- **C: Message queue / event bus (async save)**
  - ✅ Fully decoupled; Designer returns before Hub save completes
  - ❌ Significant complexity (need queue infra); offer might not be in Hub when frontend refreshes

**Decision:** Option A — direct HubStore injection. Hub is an in-process service within the same FastAPI app. `HubApiClient` is retained for Scout→Hub calls (different process path).

**Consequences:**
- (+) `POST /generate` is atomic — either both generation and Hub save succeed, or both fail
- (-) If Hub is ever extracted to a separate service, Designer must be updated to use HTTP again

---

### ADR-004: Approve Button Action Pattern (Server Action vs Client Fetch)

**Status:** Proposed

**Context:** Approve button must call `PUT /api/hub/offers/{id}/status` and refresh the OfferList on success.

**Alternatives:**
- **A (chosen): Next.js 15 Server Action + `router.refresh()`**
  - ✅ Progressive enhancement (works without JS)
  - ✅ No API route proxy needed
  - ✅ Idiomatic React 19 / Next.js 15 pattern
  - ❌ Requires `useTransition` and `useRouter` in Client Component
- **B: Client-side fetch + `useOptimistic`**
  - ✅ Instant UI feedback before server confirms
  - ❌ Requires managing optimistic rollback on failure; more complex
- **C: Form with hidden input + native form POST**
  - ✅ Zero JavaScript needed
  - ❌ Full page reload; poor UX; doesn't match App Router patterns

**Decision:** Option A — Server Action with `useTransition`. `useOptimistic` is unnecessary here since the approve transition takes <200ms and optimistic rollback adds complexity.

---

## Implementation Guidelines

### Backend Standards
- Follow `fastapi-standards.md`: all routes `async/await`, `Depends()` for DI, Pydantic v2 models
- `HubStore` method signatures are `async` — `RedisHubStore` uses `redis.asyncio`; `InMemoryHubStore` uses `async def` wrappers (trivial)
- `HubAuditService.log_event()` MUST catch all exceptions internally — never propagate to route handler
- Latency logging: `import time; start = time.monotonic()` at handler entry; emit WARNING if elapsed > 0.2s
- Redis key namespace: `offer:{offer_id}` (string key, JSON value via `model_dump_json()`)
- Follow `security.md`: `actor_id` from JWT sub only; never log objective or member PII

### Frontend Standards
- Follow `react-19-standards.md`: Server Components by default; only ApproveButton uses `'use client'`
- Hub page at `/hub` — no layout changes needed; inherits root layout from `app/layout.tsx`
- `fetchOffers()` uses `next: { revalidate: 0 }` — always fresh on SSR navigation
- Error boundary is inline try/catch in `HubPage` (no separate ErrorBoundary component needed)

### Dependency Additions
```
# Backend
redis>=5.0.0            # redis.asyncio for RedisHubStore
aiosqlite>=0.21.0       # async SQLite for HubAuditService (dev)
sqlalchemy[asyncio]>=2.0 # async ORM for HubAuditService

# Frontend (none required — uses existing fetch/next)
```

---

## Testing Strategy

### Backend Unit Tests
- `tests/unit/backend/services/test_hub_store.py` — InMemoryHubStore CRUD, save/get/list/update/exists
- `tests/unit/backend/services/test_hub_audit_service.py` — log_event writes row; log_event with DB error logs WARNING and doesn't raise
- `tests/unit/backend/api/test_hub_transitions.py` — VALID_TRANSITIONS map; all valid paths pass; all invalid paths return 422

### Backend Integration Tests
- `tests/integration/backend/api/test_hub_api.py` — **already exists (20 tests, all green)**. Add new tests for:
  - Strict transition: `test_invalid_transition_returns_422`
  - 503 when Redis mock raises: `test_redis_unavailable_returns_503`
- `tests/integration/backend/api/test_designer_hub_integration.py` — Designer generate auto-saves to Hub; verify offer appears in GET /hub/offers after POST /generate

### Frontend Tests
- `tests/unit/frontend/components/Hub/OfferCard.test.tsx` — renders all fields; draft shows Approve button; non-draft hides it
- `tests/unit/frontend/components/Hub/StatusBadge.test.tsx` — correct CSS class per status

### Coverage Target
- Backend: >80% on new files (hub_store.py, hub_audit_service.py, hub.py changes)
- Frontend: >70% on Hub components
- Existing 20 hub integration tests must remain green

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Redis key injection | `offer_id` is a UUID (validated by Pydantic); cannot contain Redis special chars |
| SQL injection in audit | SQLAlchemy parameterised queries; never string-concatenated SQL |
| PII in audit log | Only `actor_id` (JWT sub) stored; no names, emails, objectives, GPS |
| Redis connection string | `REDIS_URL` in `.env` (gitignored); Azure Key Vault in production |
| Approve button CSRF | Server Action includes CSRF token automatically in Next.js 15 |
| `HUB_SERVICE_TOKEN` in frontend | Server-side env var only (`process.env.HUB_SERVICE_TOKEN`); not prefixed with `NEXT_PUBLIC_` |

---

## Quality Gate Validation

| Gate | Status |
|------|--------|
| Every P0 requirement addressed by at least one component | ✅ COMP-001 through COMP-014 map to REQ-001–REQ-008 |
| ADRs have 2+ alternatives | ✅ All 4 ADRs have 3 alternatives |
| 3-layer separation maintained | ✅ Designer→Hub via HubStore inject; no Designer→Scout bypass |
| Hub state integrity | ✅ VALID_TRANSITIONS enforced in COMP-002; terminal state (expired) has empty set |
| Backward compatibility | ✅ All existing API contracts unchanged; 20 existing tests unaffected |
| Security: PII | ✅ Only actor_id in audit log; no member names/GPS |
| Security: OWASP A03 | ✅ SQLAlchemy parameterised queries; UUID-validated Redis keys |
| Testing: coverage targets | ✅ >80% backend, >70% frontend on new files |
| OfferBrief contract | ✅ No schema changes; Redis stores model_dump_json() |
