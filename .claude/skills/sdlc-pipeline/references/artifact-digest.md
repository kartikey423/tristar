# Artifact Digest

After each phase checkpoint, append a summary section to `docs/artifacts/<feature>/artifact-digest.md` with the key decisions from the just-completed artifact. Format: bullet list, max 10 lines per phase.

## Digest Template

```markdown
# Artifact Digest: <feature-name>

## Requirements (problem_spec.md)

- Summary: <1-line>
- Layers: [Designer|Hub|Scout] affected
- Requirements:
  - REQ-001 (P0): <10-word desc>
    - AC-001: <10-word desc>
  - REQ-002 (P1): <10-word desc>
    - AC-002: <10-word desc>
- Constraints: <key constraints>
- Non-goals: NG-001: <desc>
- Assumptions:
  - ASM-001 (risk_if_wrong: high): <15-word desc>
- Edge cases: EC-001: <desc> | EC-002: <desc>

## Architecture (design_spec.md)

- Pattern: <name> | Components: COMP-001 at <path>, COMP-002 at <path>
- ADRs: ADR-001: <title>
- APIs: <key endpoints>

## Design Review (design_review.md)

- Verdict: <decision> | Score: <N>/100 | Key concerns: <1-2 lines>

## Implementation Plan (implementation_plan.md)

- Steps: <N> files (<M> new, <K> modified)
- Waves: <W> | Execution mode: <inline|waves>
- Key risks: <1-2 line summary>

## Simplification (impl_manifest.md ## Simplification)

- Summary: <what was cleaned up, or "No issues found">

## Verification (verification_report.md)

- Score: <N>/100 | Status: <status> | Blocking: <count>
- Domain checks: fraud-detection <pass/fail> | context-matching <pass/fail>

## Risk (risk_assessment.md)

- Recommendation: <decision> | Key risks: <1-2 lines>
```

Each phase appends its own section. Downstream phases read the digest first, then selectively read full artifacts only when needed.
