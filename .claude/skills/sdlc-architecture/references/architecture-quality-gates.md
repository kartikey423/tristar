# Architecture Quality Gates

Validation criteria that must pass before saving the design_spec.md. All gates must be satisfied.

---

## Gate 1: Completeness

- [ ] Every P0 requirement from problem_spec.md is addressed by at least one component (COMP-ID)
- [ ] Every P1 requirement is addressed or explicitly deferred with rationale
- [ ] Every component has a unique COMP-ID
- [ ] Every component has an exact file path in the `src/` directory structure
- [ ] Every component has a single responsibility (one sentence description)
- [ ] Every component's public interface is defined (function signatures, props, or endpoints)
- [ ] Every acceptance criterion maps to at least one component interaction
- [ ] No requirement is addressed by an undefined component

**Verification:** Create a requirements traceability matrix:
```
REQ-001 -> COMP-001, COMP-003
REQ-002 -> COMP-002, COMP-004
...
```

---

## Gate 2: Architecture Quality

- [ ] All ADRs have at least 2 alternatives with pros and cons
- [ ] No source code or pseudocode appears in the design spec (design only)
- [ ] 3-layer separation is maintained (Designer, Hub, Scout)
- [ ] No direct Designer->Scout communication (everything flows through Hub)
- [ ] No component has more than 5 dependencies (if it does, consider decomposition)
- [ ] No circular dependencies between components
- [ ] Every external dependency (Claude API, Weather API, Redis) has a failure handling strategy
- [ ] Data flows are documented for happy path, error path, and at least 1 edge case

**Verification:** Review component dependency graph for cycles and excessive coupling.

---

## Gate 3: Backward Compatibility

- [ ] Breaking changes section exists with clear verdict
- [ ] If breaking: blast radius is estimated (which consumers affected)
- [ ] If breaking: migration strategy is documented
- [ ] If breaking: rollback plan is documented
- [ ] Existing Hub state data is not corrupted by the changes
- [ ] Existing API consumers are not broken (or migration path provided)
- [ ] Existing OfferBrief data remains valid after schema changes

**Verification:** Trace every existing data format and API contract that could be affected.

---

## Gate 4: Hub State Integrity

- [ ] All state transitions are explicitly defined (from -> to with guards)
- [ ] No orphan states exist (every non-terminal state has at least one outgoing transition)
- [ ] No unreachable states exist (every state has at least one incoming transition, except initial)
- [ ] Terminal states are clearly marked (expired is terminal)
- [ ] Invalid transitions are explicitly listed and rejected
- [ ] Concurrency handling is addressed (atomic transitions, no race conditions)
- [ ] State machine changes are backward compatible with existing offers in Hub

**Verification:** Draw the complete state machine and verify every state is reachable and every non-terminal state has exits.

---

## Gate 5: Security

- [ ] PII handling is addressed (member_id only in logs, no names/emails/addresses)
- [ ] Input validation approach defined (Zod frontend, Pydantic backend)
- [ ] Authentication requirements specified for each endpoint
- [ ] OWASP Top 10 risks mapped to mitigations
- [ ] Azure Key Vault used for all secrets (no hardcoded credentials)
- [ ] Claude API key handling reviewed (never in client code, never logged)
- [ ] Rate limiting configured for all public endpoints
- [ ] CORS configuration specified

**Verification:** Cross-reference with `.claude/rules/security.md` requirements.

---

## Gate 6: Testing Strategy

- [ ] Coverage target set (minimum 80% for new code)
- [ ] Test strategy defined for each layer:
  - Frontend: Jest + React Testing Library
  - Backend: pytest + httpx + AsyncClient
  - E2E: Playwright (critical paths)
- [ ] Mock strategy defined for external dependencies (Claude API, Weather API, Redis)
- [ ] Integration test scenarios defined (component interaction verification)
- [ ] Edge case test scenarios mapped to edge cases from problem spec
- [ ] Performance test targets defined (latency thresholds)

**Verification:** Each acceptance criterion should map to at least one test scenario.

---

## Gate 7: OfferBrief Contract

- [ ] If OfferBrief schema changes: both Zod (frontend) and Pydantic (backend) schemas are specified
- [ ] Shared type in `src/shared/types/offer-brief.ts` is the source of truth
- [ ] Pydantic model in `src/backend/models/offer_brief.py` mirrors the shared type exactly
- [ ] Field validators are consistent between Zod and Pydantic
- [ ] Schema change is additive (backward compatible) or migration plan exists
- [ ] If no schema changes: explicitly stated as "No OfferBrief changes"

**Verification:** Compare Zod and Pydantic field definitions for consistency.

---

## Validation Procedure

1. Run through all 7 gates sequentially
2. For each gate, check every item
3. If ANY item fails, note it and fix the design
4. Re-validate the fixed gate
5. Only save design_spec.md when ALL 7 gates pass
6. Include a "Quality Gate Results" section at the bottom of design_spec.md:

```markdown
## Quality Gate Results

| Gate | Status | Notes |
|------|--------|-------|
| 1. Completeness | PASS | All 5 requirements traced to components |
| 2. Architecture Quality | PASS | 2 ADRs with 2+ alternatives each |
| 3. Backward Compatibility | PASS | Additive schema change only |
| 4. Hub State Integrity | PASS | No state machine changes |
| 5. Security | PASS | PII verified, OWASP mapped |
| 6. Testing | PASS | 80% coverage target, all layers covered |
| 7. OfferBrief Contract | PASS | Zod + Pydantic schemas aligned |
```
