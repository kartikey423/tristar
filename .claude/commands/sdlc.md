Run the full SDLC pipeline from requirements through PR creation.

Arguments: $ARGUMENTS

**IMPORTANT:** Do NOT attempt to read or locate skill files. Instead, use the `Skill` tool to invoke skills by name.

To run the pipeline, invoke the `sdlc-pipeline` skill using the Skill tool:

```
Skill: sdlc-pipeline
Args: $ARGUMENTS
```

The `sdlc-pipeline` skill accepts these arguments:
- `--feature=<name>` — Feature name for artifact naming (e.g., `designer-ui`, `hub-state-management`)
- `--resume` — Reload the last checkpoint for the given feature
- `--from=<phase>` — Start from a specific phase (requirements, architecture, design-review, impl-planning, implementation, simplify, review, verification, risk, pr)
- `--waves=<n>` — Max implementation waves (default: 5)

The pipeline always runs in gated mode. Users should omit `--mode`.

Example: `--feature=designer-ui`

The pipeline executes 10 phases in order:
1. Requirements Analysis
2. Architecture Design
3. Design Review (quality gate)
4. Implementation Planning
5. Implementation Execution
6. Simplify (code cleanup)
7. Code Review (auto-detects TypeScript vs Python)
8. Verification (engineering + loyalty-fraud-detection + semantic-context-matching)
9. Risk Assessment
10. PR Creation

Invoke the skill now with the arguments provided above.
