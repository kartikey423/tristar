# Design Review: designer-layer

## Meta

| Field | Value |
|-------|-------|
| **Feature** | designer-layer |
| **Date** | 2026-03-27 |
| **Review Mode** | Initial Review |
| **Artifacts Reviewed** | `problem_spec.md` (v1.0), `design_spec.md` (v1.0) |
| **Score** | 50/100 |
| **Decision** | APPROVE_WITH_CONCERNS |

---

## Review Summary

The design is architecturally coherent. It correctly implements the 3-layer separation, produces honest ADRs with genuine alternatives, and decomposes responsibilities into focused components. The Scout→Designer purchase-triggered flow is well-justified in ADR-001 and does not bypass Hub's role as the state authority.

However, **4 major gaps** were found — not architectural flaws, but missing specifications that implementers will hit immediately:

1. The cache can return a shared `offer_id` to different users, causing Hub collisions
2. `DeliveryConstraintService` depends on a Hub query endpoint that is never defined
3. Hub's enforcement of the new `draft→active` shortcut is acknowledged but unspecified
4. The time-based `active→expired` transition for purchase-triggered offers has no owner

These are resolvable by adding targeted specifications to the design before implementation begins. No redesign is required.

---

## Findings

### Dimension A: Codebase Validation

**[MINOR] F-006: COMP-013 incorrectly mapped to REQ-005 in requirements table**

The Problem Spec Reference table maps REQ-005 (JWT Auth + RBAC) to `COMP-003, COMP-013`. COMP-013 is `OfferBriefCard` — a display component with no authentication responsibility. REQ-005 is correctly addressed by COMP-003 (JWT Auth Middleware) and COMP-016 (Designer API Service, which attaches auth headers). COMP-013 should be removed from the REQ-005 mapping row.

_Impact: Minor documentation error, no implementation risk._

---

**[MINOR] F-010: `InventorySuggestionCard` referenced in topology diagram but absent from Component Catalogue**

The system topology diagram shows:
```
AISuggestionsPanel (Server Component)
  └── InventorySuggestionCard (Server Component)
```

No `InventorySuggestionCard` entry exists in the Component Catalogue. The component is orphaned — its path, responsibility, and interface are undefined. Implementers will need to invent it.

_Impact: Minor implementation ambiguity. Easily resolved by adding COMP-024: InventorySuggestionCard to the catalogue._

---

**No Critical or Major findings in Dimension A.** Paths follow the CLAUDE.md-defined structure correctly. React 19 patterns are applied appropriately (Server Components by default; `use client` only on ManualEntryForm, ModeSelectorTabs, ApproveButton). FastAPI async patterns and Pydantic v2 usage are correctly specified. OfferBrief shared type location is correct.

---

### Dimension B: Architectural Review

**[MAJOR] F-003: Hub enforcement of `draft→active` shortcut transition is acknowledged but unspecified**

The design introduces a new valid Hub state transition:
```
draft → active  (purchase-triggered only, gated on trigger_type=purchase_triggered)
```

The design states: _"Hub must validate `trigger_type` before allowing this transition."_

However, the Hub component design (COMP-007 `HubApiClient`) simply POSTs to `/api/hub/offers` with `status=active` in the payload. If Hub accepts any `status` value in the POST body without validation, **any caller with a valid JWT** (including a compromised Scout service or misconfigured client) could create an `active` offer with `trigger_type=marketer_initiated` — bypassing the fraud check and approval workflow entirely.

The design specifies that this validation must exist in Hub, but does not define:
- Which Hub component enforces the rule
- What the Hub API response is when the rule is violated
- Whether Designer or Hub is responsible for the `trigger_type` assertion

_Impact: Security gap. If Hub doesn't enforce this, the approval workflow can be bypassed. Must be resolved before implementation._

_Recommendation: Add to Hub API contract: `POST /api/hub/offers` returns `422 Unprocessable Entity` if `status=active` AND `trigger_type != purchase_triggered`. Document that Designer sets `status` in the payload; Hub validates the combination._

---

**[MINOR] F-008: Context enrichment in COMP-018 not specified as concurrent**

`PurchaseEventHandler._enrich_with_member_history`, `_find_nearby_ctc_stores`, and `_get_weather` are three independent external calls. The interface definition lists them as sequential private methods. If implemented serially, worst-case enrichment time is ~600ms–2s. If parallel (`asyncio.gather`), it's ~200ms.

For the 2-minute SLA this is not critical, but at peak load (multiple simultaneous purchase events) serial enrichment could become a bottleneck.

_Recommendation: Add to COMP-018 implementation guidelines: "Enrich concurrently using `asyncio.gather(fetch_member_history, find_nearby_stores, get_weather)`."_

---

**No Critical findings in Dimension B.** The 3-layer separation is maintained — Scout→Designer is justified by ADR-001 and does not bypass Hub as state authority. Fraud detection runs before Hub save. Rate limiting is at the Scout layer (COMP-020). No circular dependencies.

---

### Dimension C: Assumption Challenges

**[MAJOR] F-001: Objective cache returns shared `offer_id` — collision risk when multiple marketers approve the same cached offer**

ADR-004 specifies the cache key as `SHA-256(lowercased objective)`. The cache stores and returns the full `OfferBrief`, including the `offer_id` UUID. If two marketers submit the identical objective within the 5-minute TTL window:

1. Marketer A submits objective "Clear winter inventory"
2. Claude API generates OfferBrief with `offer_id = "uuid-111"`
3. Result cached under `SHA256("clear winter inventory") → offer_id uuid-111`
4. Marketer B submits same objective within 5 minutes
5. Cache returns the same OfferBrief with `offer_id = "uuid-111"`
6. Marketer A approves → Hub saves `offer_id uuid-111` ✓
7. Marketer B approves → Hub receives duplicate `offer_id uuid-111` → **409 Conflict**
8. Marketer B sees a confusing error with no clear recovery path

The collision is unlikely in normal operation but plausible in a team setting during peak usage, and the error presented to the user would be opaque.

_Recommendation: On cache hit, generate a fresh `offer_id` (UUID4) before returning the cached OfferBrief. The offer content is reused but each marketer gets a unique identifier. Add this to COMP-004's cache retrieval logic._

---

**[MINOR] F-007: GPS/lat-lon coordinates not addressed in PII handling**

The `PurchaseEventPayload` contains `location: {lat: float, lon: float}`. The AuditLogService._scrub_pii() specification addresses scrubbing emails and names from objective text, but **does not mention GPS coordinates**.

In many jurisdictions, precise GPS location data is considered PII (GDPR, PIPEDA). If purchase events are logged with lat/lon in plaintext, this could violate TriStar's "no PII in logs" policy.

_Recommendation: Extend `_scrub_pii()` specification to either (a) exclude `location` from audit logs entirely, logging only `store_id` and `store_name`, or (b) round coordinates to 2 decimal places (~1km precision) before logging._

---

**No Critical findings in Dimension C.** The 2-minute SLA is achievable (total flow ~5–8s worst case, well within 120s window). The `trigger_type` field distinction is sound. Claude API retry strategy (3× exponential backoff) is correctly specified.

---

### Dimension D: Complexity Concerns

**[MINOR] F-009: Feature flag / phased rollout mechanism absent from architecture**

The problem specification (ASM-006) confirms a phased rollout: "pilot with 2-3 pilot marketers." The requirements (REQ-006) support dual-mode creation. However, the architecture has no mechanism to restrict access to the purchase-triggered feature to pilot users.

Currently, once deployed, ALL marketers and ALL purchase events would trigger the full flow. There is no:
- `PURCHASE_TRIGGER_ENABLED: bool` flag in Settings (COMP-023)
- `PILOT_MARKETER_IDS: list[str]` allowlist
- Environment-based toggle for gradual rollout

_Recommendation: Add `PURCHASE_TRIGGER_ENABLED: bool = False` and `PURCHASE_TRIGGER_PILOT_MEMBERS: str = ""` (comma-separated member IDs) to Settings (COMP-023). PurchaseEventHandler checks this flag before scoring. This costs 3 lines of code and enables safe phased rollout._

---

**[MINOR] F-005: Scout service JWT lifecycle has no owner component**

ADR-003 decides: "Service JWT with role='system', generated at Scout startup, 24-hour expiry." The ADR consequence notes: "requires Scout to manage token refresh (24h expiry)."

However, **no component is defined to own this responsibility**. There is no `ScoutAuthManager` or equivalent in the component catalogue. COMP-017 (PurchaseEventRouter) and COMP-018 (PurchaseEventHandler) both implicitly need the token for the Scout→Designer call, but neither owns its lifecycle.

_Recommendation: Add COMP-024: ScoutServiceAuth to the Scout backend layer. Responsibility: generate service JWT at startup, store in memory, refresh proactively when 80% of TTL has elapsed. Inject into COMP-018 via Depends()._

---

**Overall complexity assessment:** 23 components is high but justified. The feature spans full-stack (8 frontend, 9 backend, 5 Scout, 1 shared) and implements two distinct flows. The components are small and focused — no component has more than 5 dependencies. The complexity is essential, not accidental.

---

### Dimension E: Alternative Approaches

**No Major or Critical findings in Dimension E.**

All 4 ADRs present genuine alternatives with honest trade-offs:
- ADR-001: Hub-as-broker and event queue are real alternatives, correctly rejected for MVP
- ADR-002: SQLite is a real alternative to CSV, correctly identified as over-engineered for mock data
- ADR-003: API key and mTLS are real alternatives to service JWT
- ADR-004: Redis cache is correctly identified as over-engineered for single-instance MVP

One observation: **ADR-004 does not address the cache collision risk** identified in F-001. The ADR should be updated to document the mitigation (fresh UUID on cache hit) as a design decision.

---

### Dimension F: Missing Considerations

**[MAJOR] F-002: Hub API endpoint for querying member's recent offers is undefined**

`DeliveryConstraintService` (COMP-020) needs to enforce:
- Max 1 purchase-triggered offer per member per 6 hours
- No duplicate offers within 24h (unless purchase > $100)

To enforce these rules, COMP-020 must query Hub for the member's recent offer history:
_"Has this member received a purchase-triggered offer in the last 6 hours?"_

The API contracts section defines Hub endpoints for creating and retrieving offers by ID, but **no endpoint exists for querying offers by member_id and recency**. COMP-020 has an undefined external dependency.

Without this endpoint, the rate limiting logic in COMP-020 cannot be implemented.

_Recommendation: Add to Hub API contracts:_
```
GET /api/hub/offers?member_id={id}&trigger_type=purchase_triggered&since={iso_timestamp}
Response: { offers: OfferBrief[], count: int }
```
_This is a Hub design concern but must be coordinated before implementing COMP-020._

---

**[MAJOR] F-004: `valid_until` expiry enforcement for purchase-triggered offers has no defined mechanism**

The design specifies that purchase-triggered offers should have `valid_until = now + 4 hours` (from the problem spec: "Valid for 4 hours only" urgency indicator). The OfferBrief schema includes an optional `valid_until` field.

However, **no component is responsible for the `active → expired` transition** when `valid_until` is reached. The Hub state machine requires this transition but the design does not define:
- A background scheduler / TTL mechanism in Hub
- A polling job that expires offers past their `valid_until`
- Whether this is Redis TTL, a cron job, or a Hub-side check on read

Without this mechanism, purchase-triggered offers remain `active` indefinitely, accumulating stale offers that Scout would continue matching against.

_Recommendation: Add to Hub design: offers with `valid_until` set should be checked on read. If `valid_until < now`, Hub returns the offer with `status=expired` and persists the transition. Alternatively, use Redis TTL (if using Redis) or a background task with `apscheduler` to sweep expired offers every 5 minutes._

---

**Checklist Summary (Dimension F):**

| Item | Status |
|------|--------|
| Claude API failure handling (retry + backoff) | ✅ Covered (COMP-004, 3×backoff) |
| Fraud detection all 4 flags checked | ✅ Covered (COMP-006) |
| Rate limiting (1/hr, 24h dedup, quiet hours) | ✅ Covered (COMP-020) |
| PII — member_id only in logs | ✅ Covered (COMP-022) |
| PII — GPS coords in logs | ❌ Gap (F-007) |
| Hub query for member recent offers | ❌ Gap (F-002) |
| offer valid_until expiry enforcement | ❌ Gap (F-004) |
| Feature flag / pilot rollout | ❌ Gap (F-009) |
| Audit trail (all generation events) | ✅ Covered (COMP-022) |
| Testing strategy (>80%, mock Claude) | ✅ Covered |
| Scout service JWT lifecycle | ⚠️ Partial (ADR-003 decides, no owner component) |
| Error handling — custom exception classes | ✅ Covered (FraudBlockedError, etc.) |

---

## Score Breakdown

| Category | Findings | Points |
|----------|----------|--------|
| Critical | 0 | 0 |
| Major | 4 (F-001, F-002, F-003, F-004) | −32 |
| Minor | 6 (F-005, F-006, F-007, F-008, F-009, F-010) | −18 |
| Clean Dimensions | 0 | 0 |
| **Total** | | **50 / 100** |

---

## Gate Decision

**APPROVE_WITH_CONCERNS** (score = 50)

### Rationale

The design is structurally sound and implementable as written. The 3-layer architecture is maintained correctly. ADRs are honest and defensible. Component responsibilities are well-scoped. The purchase-triggered flow is architecturally clean.

The 4 major findings are **specification gaps, not design flaws**. They do not require redesigning components or changing architectural decisions — they require adding missing endpoint definitions and lifecycle owners. Implementation can proceed with these tracked as must-resolve items.

**Condition for implementation to begin:** The 4 major findings (F-001, F-002, F-003, F-004) must be resolved either by updating the design_spec.md or by documenting resolution decisions in impl_manifest.md before writing the affected components.

---

## Sign-Off

### Findings Summary

| ID | Severity | Dimension | Title | Status |
|----|----------|-----------|-------|--------|
| F-001 | Major | C | Cache collision — shared offer_id on cache hit | Open |
| F-002 | Major | F | Hub member offer query endpoint undefined | Open |
| F-003 | Major | B | Hub draft→active enforcement unspecified | Open |
| F-004 | Major | F | valid_until expiry mechanism undefined | Open |
| F-005 | Minor | D | Scout JWT lifecycle has no owner component | Open |
| F-006 | Minor | A | COMP-013 incorrectly mapped to REQ-005 | Open |
| F-007 | Minor | F | GPS coordinates not in PII scrubbing spec | Open |
| F-008 | Minor | C | Context enrichment concurrency unspecified | Open |
| F-009 | Minor | D | Feature flag / phased rollout absent | Open |
| F-010 | Minor | A | InventorySuggestionCard not in catalogue | Open |

### Recommendations (Priority Order)

1. **(F-003 — Security)** Specify in Hub API contract that `status=active` in POST /api/hub/offers is only accepted when `trigger_type=purchase_triggered`. Return 422 otherwise.
2. **(F-002 — Blocking)** Add Hub API endpoint `GET /api/hub/offers?member_id=&trigger_type=&since=` to support DeliveryConstraintService rate limit checks.
3. **(F-001 — Correctness)** Update COMP-004 cache specification: on cache hit, generate fresh UUID for `offer_id` before returning.
4. **(F-004 — Completeness)** Define expiry mechanism for `valid_until` in Hub — recommend on-read check with status update + background sweep every 5 minutes.
5. **(F-005 — Implementation)** Add COMP-024: ScoutServiceAuth to catalogue with JWT generation + proactive refresh logic.
6. **(F-009 — Rollout)** Add `PURCHASE_TRIGGER_ENABLED: bool = False` to Settings (COMP-023) for safe phased rollout.
7. **(F-007 — PII)** Extend AuditLogService to exclude or round GPS coordinates before logging.
8. **(F-008 — Performance)** Add `asyncio.gather` requirement to COMP-018 implementation guidelines.
9. **(F-010 — Completeness)** Add COMP-024: InventorySuggestionCard to component catalogue with path and interface.
10. **(F-006 — Documentation)** Correct REQ-005 mapping row: replace COMP-013 with COMP-016.
