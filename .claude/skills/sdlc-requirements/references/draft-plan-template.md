# Draft Plan Template

Use this template to present the draft plan to the user for approval before writing the final problem_spec.md.

---

```markdown
# Draft Plan: <feature-name>

## What We're Building
<2-3 sentence summary of the feature. Focus on user value and business impact.>

## Layers Affected
- [ ] Designer (Layer 1) - <brief description of changes if checked>
- [ ] Hub (Layer 2) - <brief description of changes if checked>
- [ ] Scout (Layer 3) - <brief description of changes if checked>

## Requirements

### P0 (Must Have)
- REQ-001 (P0): <description>
  - AC-001: Given <context>, When <action>, Then <result>
  - AC-002: Given <context>, When <action>, Then <result>
- REQ-002 (P0): <description>
  - AC-003: Given <context>, When <action>, Then <result>

### P1 (Should Have)
- REQ-003 (P1): <description>
  - AC-004: Given <context>, When <action>, Then <result>

### P2 (Nice to Have)
- REQ-004 (P2): <description>
  - AC-005: Given <context>, When <action>, Then <result>

## Non-Goals
- NG-001: <what we are NOT doing> - Rationale: <why>
- NG-002: <what we are NOT doing> - Rationale: <why>

## Assumptions
- ASM-001: <assumption> (risk_if_wrong: high|medium|low)
- ASM-002: <assumption> (risk_if_wrong: high|medium|low)

## Edge Cases
- EC-001: <scenario> -> <expected behavior>
- EC-002: <scenario> -> <expected behavior>
- EC-003: <scenario> -> <expected behavior>

## TriStar Domain Constraints
- Rate Limiting: <how this feature respects 1/hr/member, 24h dedup, quiet hours>
- Fraud Detection: <which risk flags are relevant>
- Channel Priority: <notification delivery order if applicable>
- OfferBrief Impact: <which fields are read/written/modified>
- Hub State: <which transitions are involved>

---

Reply 'approved' to proceed with the full problem_spec.md, or describe what you'd like changed.
```

---

## Presentation Rules

1. Present the draft plan exactly as formatted above
2. Fill in all sections - do not leave placeholders unfilled
3. Check all applicable layer boxes
4. Include at least 1 P0 requirement
5. Include at least 2 non-goals with rationale
6. Include at least 3 edge cases
7. Every P0 requirement must have at least 1 acceptance criterion
8. All assumptions must have risk_if_wrong levels
9. Wait for explicit user approval before proceeding
10. If user requests changes, incorporate and re-present the full draft
