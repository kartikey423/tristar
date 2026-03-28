# Design Review: hub-layer

## Review Summary
- **Date:** 2026-03-28
- **Review Mode:** Initial Review
- **Score:** 57/100
- **Decision:** APPROVE_WITH_CONCERNS

---

## Findings

### Dimension A: Codebase Validation

- **[MINOR] F-005:** `@/types/offer-brief` import path in COMP-009/010/014 is wrong. `src/shared/types/offer-brief.ts` exists, but the codebase pattern (confirmed in `designer-api.ts` and `designer/page.tsx`) is `@/../../shared/types/offer-brief` — not `@/types/offer-brief`. If implementation uses the path in the design spec as-is, TypeScript builds will fail.

- **[MAJOR] F-002:** `getAuthHeaders()` referenced in COMP-013 (`actions.ts`) does not exist in `src/frontend/lib/config.ts`. That file exports only `SERVER_API_BASE`. No `getAuthHeaders()` helper exists anywhere in the codebase. Implementation will fail at import resolution.

- **[MAJOR] F-003:** COMP-014 (`hub-api.ts`) references `process.env.HUB_SERVICE_TOKEN` as the frontend→Hub auth mechanism. This does not exist in `Settings` and contradicts the existing codebase pattern: `src/frontend/app/designer/page.tsx` uses `process.env.MARKETER_JWT` for server-side API auth. A new env var name invents a third token pattern alongside `MARKETER_JWT` and `scout_auth`. Hub page should use `MARKETER_JWT` (already present) for consistency.

- **[MINOR] F-007:** `src/shared/types/offer-brief.ts` exists ✅. Hub state machine (`draft/approved/active/expired`) and `OfferBrief` fields are already defined there. No new shared types are needed — existing type can be imported directly.

---

### Dimension B: Architectural Review

- **[CRITICAL] F-001:** **Approve endpoint conflict with auto-save.** The design specifies that `POST /generate` auto-saves the OfferBrief to Hub as `status=draft` (COMP-006). However, the existing `POST /approve/{offer_id}` in `designer.py` currently does a fresh `hub_store.save(offer)` — a POST to Hub that would return 409 Conflict because the offer was already saved on generate. The design must specify that after auto-save is introduced, `POST /approve/{offer_id}` transitions status (`hub_store.update()` with `status=approved`) rather than re-saving. This is a breaking internal change not addressed in COMP-006 or the approve endpoint's modification scope.

- **[MINOR] F-006:** `_expire_offers_task` performs `hub_store.list(status_filter=active)` on every sweep. With Redis and thousands of active offers, this is an O(n) full-scan every 300s. Acceptable for MVP but should be noted as a known limitation.

- **No bypass of 3-layer separation** ✅ — Designer→Hub via HubStore inject; no Designer→Scout path.
- **State machine VALID_TRANSITIONS** ✅ — All four transitions covered, terminal state correctly has empty set.
- **ADRs have genuine alternatives** ✅ — All four ADRs have three non-strawman alternatives.
- **No circular dependencies** ✅ — HubApiClient retained for Scout path; HubStore used for Designer-internal path.

---

### Dimension C: Assumption Challenges

- **[MAJOR] F-004:** **SQL audit table is never initialized.** A-001 assumes SQLite is used for dev. `HubAuditService` issues `INSERT INTO hub_audit_log`. But nowhere in the design is there a startup hook (lifespan event or `CREATE TABLE IF NOT EXISTS`) to create the table before the first write. On a fresh environment, the first audit write will raise `OperationalError: no such table: hub_audit_log`. The design must specify that `HubAuditService.__init__()` or the `lifespan()` function runs the CREATE TABLE DDL.

- **[MINOR] F-006 (repeated):** A-005 says "CRITICAL log if Redis maxmemory-policy != noeviction, detect at startup." COMP-001 exposes only a `ping()` method. A Redis `CONFIG GET maxmemory-policy` call is needed for this validation, but no method or startup hook is described. Implementation will silently skip this check unless explicitly added.

- **A-006 accepted:** Direct HubStore injection in Designer — acknowledged trade-off if Hub is extracted to separate service. Documented. ✅

- **A-002 accepted:** Redis availability is an infra concern; HUB_REDIS_ENABLED=false for dev is the correct mitigation. ✅

---

### Dimension D: Complexity Concerns

- **[MINOR] F-005 (secondary):** COMP-012 (`StatusBadge`) is a ~10-line functional component. While a separate file is clean, it adds a file for trivial logic. Acceptable — reuse from Scout frontend justifies the file.

- **14 components** for Hub layer is proportional to scope (Redis service + audit service + 4 frontend components + modifications to 4 existing files). Not over-engineered.

- **HubStore Protocol abstraction** earns its complexity cost: it enables test isolation via `app.dependency_overrides` and a clean Redis/in-memory swap. ✅

- **HubAuditService** — adding SQLAlchemy async + aiosqlite is weighty for an audit log, but the problem spec explicitly requires "queryable SQL audit trail." Justified. ✅

---

### Dimension E: Alternative Approaches

- All four ADRs contain 3 genuine alternatives with honest pro/con analysis. ✅
- ADR-003 (Designer→Hub integration) correctly identifies the HTTP self-call anti-pattern and chooses direct injection. ✅
- ADR-004 (Approve button) correctly chooses Server Action over `useOptimistic` (no rollback complexity needed for <200ms operations). ✅
- No findings in this dimension. ✅

---

### Dimension F: Missing Considerations

- **F-004 (same as Dimension C):** SQL table migration / initialization not specified. See above.

- **[MINOR] F-008:** `process.env.MARKETER_JWT` referenced in `designer/page.tsx` is a hardcoded test JWT. The design doesn't address how this scales to a real auth system where the user's actual session token should flow into server-side fetches. This is a pre-existing limitation, not introduced by hub-layer — tracked here as a minor observation.

- **Structured logging (loguru):** COMP-002 specifies `logger.warning(...)` for slow queries and Redis failures. ✅
- **PII:** Only `actor_id` (JWT sub) in audit log. No objectives, member names, GPS. ✅
- **Rate limiting:** Correctly out-of-scope for Hub (enforced at Scout layer). ✅
- **Fraud detection:** Runs before Hub save in Designer; COMP-006 correctly places fraud block audit event before raising 422. ✅
- **Feature flags:** `HUB_REDIS_ENABLED` defined in COMP-004. ✅
- **Backward compatibility:** All existing Hub API contracts unchanged. 20 existing integration tests unaffected. ✅
- **Coverage targets:** >80% backend, >70% frontend on new files. ✅

---

## Score Breakdown

| Category | Count | Points |
|----------|-------|--------|
| Critical | 1 | -15 |
| Major | 3 | -24 |
| Minor | 4 | -12 |
| Clean Dimensions (E only) | 1 | +8 |
| **Total** | | **57/100** |

---

## Gate Decision

**APPROVE_WITH_CONCERNS:** The architectural foundations are solid — HubStore Protocol abstraction is correct, 3-layer separation maintained, all 4 ADRs have genuine alternatives, backward compatibility preserved for all 20 existing Hub integration tests. The score of 57 reflects concrete implementation gaps, not architectural flaws.

**All 4 concerns MUST be resolved during implementation (Phase 5), not deferred:**

| Finding | Impact | Required Action |
|---------|--------|-----------------|
| **F-001** CRITICAL: Approve endpoint 409 conflict | Will break Designer flow | `POST /approve/{offer_id}` must call `hub_store.update()` + transition, not re-save |
| **F-002** MAJOR: `getAuthHeaders()` missing | TypeScript build failure | Add `getAuthHeaders()` to `lib/config.ts` or inline auth header in `actions.ts` |
| **F-003** MAJOR: `HUB_SERVICE_TOKEN` wrong pattern | Missing env var, auth breakage | Use `MARKETER_JWT` (existing) in `hub-api.ts` Server Component fetches |
| **F-004** MAJOR: SQL table never initialized | Runtime crash on first audit write | Add `CREATE TABLE IF NOT EXISTS` in `HubAuditService.__init__()` or lifespan |

---

## Recommendations

1. **F-001 fix:** In `POST /approve/{offer_id}`, replace `hub_client.save_offer(offer)` with `hub_store.update(offer.model_copy(update={"status": OfferStatus.approved}))`. Add a call to `_validate_transition(OfferStatus.draft, OfferStatus.approved)` before the update. This correctly transitions rather than re-saves.

2. **F-002 fix:** In `src/frontend/lib/config.ts`, add:
   ```ts
   export function getAuthHeaders(): Record<string, string> {
     const token = process.env.MARKETER_JWT;
     if (!token) return {};
     return { Authorization: `Bearer ${token}` };
   }
   ```
   This extends the existing config file without introducing a new module.

3. **F-003 fix:** In COMP-014 (`hub-api.ts`), replace `process.env.HUB_SERVICE_TOKEN` with `process.env.MARKETER_JWT` — the same server-side token already used by `designer/page.tsx` for Hub API reads.

4. **F-004 fix:** In `HubAuditService.__init__()`, run `CREATE TABLE IF NOT EXISTS hub_audit_log (...)` synchronously using a synchronous SQLite connection, or add a `await hub_audit.initialize()` call to the `lifespan()` startup section in `main.py`.

5. **F-005 fix (minor):** Replace `@/types/offer-brief` with `@/../../shared/types/offer-brief` in all Hub frontend component imports, matching the established pattern from `designer-api.ts` and `designer/page.tsx`.

6. **F-006 (accepted):** Document the O(n) expire-task scan as a known MVP limitation in `main.py` comments. Add a TODO for Redis `ZADD` sorted-set pattern for efficient TTL scanning in production.
