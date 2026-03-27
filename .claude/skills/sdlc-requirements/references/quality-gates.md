# Quality Gates

Validation criteria that must pass before saving the final problem_spec.md. Every gate must be satisfied.

---

## Gate 1: Mandatory Category Coverage

Every mandatory category must be addressed in the problem specification:

- [ ] **Scope & Layers** - Which of Designer/Hub/Scout are affected is explicitly stated
- [ ] **Error States & Handling** - At least 2 error scenarios documented with expected behavior
- [ ] **Security & Compliance** - PII handling confirmed (member_id only), input validation approach stated
- [ ] **Performance & Constraints** - Latency targets defined, caching strategy addressed
- [ ] **Feature Flags & Rollout** - Rollout strategy defined (even if "deploy to all")
- [ ] **Backward Compatibility** - Impact on existing data/APIs stated with verdict (compatible / breaking / N/A)

**Failure:** If any mandatory category is missing, do not save. Go back and address it.

---

## Gate 2: P0 Requirements Defined

At least 1 P0 (Must Have) requirement must be defined. P0 requirements represent the minimum viable scope - without them, the feature has no clear deliverable.

- [ ] At least 1 requirement marked as P0
- [ ] Each P0 requirement has a clear, measurable description
- [ ] P0 requirements together form a coherent minimum viable feature

**Failure:** If no P0 requirements exist, the feature scope is undefined. Return to interrogation.

---

## Gate 3: Non-Goals Defined

At least 2 non-goals must be defined with rationale. Non-goals prevent scope creep and set clear boundaries for what the feature does NOT include.

- [ ] At least 2 non-goals present
- [ ] Each non-goal has a rationale explaining why it is excluded
- [ ] Non-goals are specific and actionable (not vague like "performance optimization")

**Failure:** If fewer than 2 non-goals, add more based on interrogation responses. Common non-goals: alternative approaches discussed but rejected, future enhancements deferred, adjacent features explicitly excluded.

---

## Gate 4: Edge Cases Defined

At least 3 edge cases must be defined with expected behavior. Edge cases catch scenarios that the happy path misses.

- [ ] At least 3 edge cases present
- [ ] Each edge case has a scenario description AND expected behavior
- [ ] Edge cases cover at least 2 different categories (e.g., error handling + boundary values)

**Failure:** If fewer than 3 edge cases, consider these common TriStar edge cases:
- What happens at exactly the score threshold (score = 60)?
- What happens at exactly the discount threshold (discount = 30%)?
- What happens during quiet hours boundary (exactly 10pm or 8am)?
- What happens when Hub has concurrent state transitions?
- What happens when all context signals are unavailable?
- What happens when member has exactly hit the rate limit?

---

## Gate 5: Acceptance Criteria for P0 Requirements

Every P0 requirement must have at least 1 acceptance criterion in Given/When/Then format.

- [ ] Every P0 requirement has >= 1 acceptance criterion
- [ ] Acceptance criteria use Given/When/Then format
- [ ] Acceptance criteria are specific and testable (no vague language like "should work correctly")

**Failure:** Add acceptance criteria to any P0 requirement missing them. Each AC must be independently verifiable.

---

## Gate 6: Backward Compatibility Section Present

A backward compatibility section must be present with a clear verdict.

- [ ] Backward compatibility section exists
- [ ] Verdict is one of: "Fully compatible", "Breaking change (describe)", "Not applicable (new feature)"
- [ ] If breaking: migration path described
- [ ] If breaking: blast radius estimated (which existing data/APIs/users affected)

**Failure:** Add backward compatibility section. Default assumption should be "Fully compatible" unless evidence suggests otherwise.

---

## Gate 7: No Implementation Details

Requirements describe WHAT the system should do, not HOW it should be implemented. Implementation details belong in the design spec.

- [ ] No specific technology choices in requirements (e.g., "use Redis" belongs in design, not requirements)
- [ ] No code snippets or pseudocode
- [ ] No file paths or class names
- [ ] No database schema details
- [ ] Requirements are testable without knowing implementation

**Exceptions:** Constraints that ARE requirements (e.g., "must use async processing" for performance reasons) are acceptable if the constraint is driven by a requirement, not an implementation preference.

**Failure:** Remove implementation details and rephrase as behavioral requirements.

---

## Gate 8: Assumptions Have Risk Levels

All assumptions must have a risk_if_wrong level assigned (high, medium, low).

- [ ] Every assumption has risk_if_wrong: high | medium | low
- [ ] High-risk assumptions have mitigation strategies noted
- [ ] No assumption contradicts a confirmed requirement

**Risk Level Definitions:**
- **high**: If wrong, feature cannot ship or requires major rework
- **medium**: If wrong, feature needs significant adjustments but core value is preserved
- **low**: If wrong, minor adjustments needed, no impact on core functionality

**Failure:** Assign risk levels to all assumptions. If unable to assess risk, the assumption needs further interrogation.

---

## Validation Procedure

Before saving problem_spec.md, run through all 8 gates sequentially:

1. Check each gate's checklist items
2. If ANY gate fails, note the failure and fix it
3. Re-validate the fixed gate
4. Only save when ALL 8 gates pass
5. Include a "Quality Gate Results" section at the bottom of problem_spec.md showing pass/fail for each gate
