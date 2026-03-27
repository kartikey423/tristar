# Execution Flow -- Detailed Per-Phase Instructions

Read this file before executing each phase. These are the full [1]-[10] phase instructions for TriStar.

---

## [1] REQUIREMENTS

**REQUIRED SUB-SKILL:** Invoke `sdlc-requirements` via the Skill tool.

MANDATORY: Use the Skill tool to invoke `sdlc-requirements --feature=<feature>`
DO NOT analyze code and write problem_spec.md yourself. The skill handles:
- Interrogation via plain text chat (asks user clarifying questions, waits for replies)
- Draft plan confirmation (presents summary, waits for "approved")
- problem_spec.md generation (only after user approves)

Checkpoint: requirements = completed
Validate: problem_spec.md has all required sections

---

## [2] ARCHITECTURE

**REQUIRED SUB-SKILL:** Invoke `sdlc-architecture` via the Skill tool.

MANDATORY: Use the Skill tool to invoke `sdlc-architecture --feature=<feature>`
Input: problem_spec.md
The skill references TriStar's 3-layer architecture (Designer, Hub, Scout) and Azure stack.
Checkpoint: architecture = completed

---

## [3] DESIGN REVIEW

MANDATORY: Use the Skill tool to invoke `sdlc-design-review --feature=<feature>`
Input: problem_spec.md + design_spec.md
Checkpoint: design-review = completed

Gate logic:
- `approve` -> continue to [4]
- `approve_with_concerns` -> log concerns, continue to [4]
- `reject` -> feed reasons to [2], increment design_review_to_architecture, re-run. If limit reached (3): HALT

---

## [4] IMPLEMENTATION PLANNING

**REQUIRED SUB-SKILL:** Invoke `sdlc-impl-planning` via the Skill tool.

MANDATORY: Use the Skill tool to invoke `sdlc-impl-planning --feature=<feature>`
The skill uses TriStar layer dependencies for wave ordering (shared types -> backend models -> backend services -> backend API -> frontend services -> frontend components -> tests).
Output: implementation_plan.md in `docs/artifacts/<feature>/`
Checkpoint: impl-planning = completed

---

## [5] IMPLEMENTATION EXECUTION

Main agent writes code inline (no skill invocation).
Read implementation_plan.md for ordered steps, wave assignments, and pre-computed dependencies.

### Incremental Testing Protocol (CRITICAL)

- Run the FULL test suite BEFORE making any changes (baseline). Record pass/fail counts.
- After EACH file modification, run tests for that module immediately.
- If new test failures appear, STOP and fix them before modifying the next file.
- Do NOT batch all changes and test at the end.

### TriStar-Specific Implementation Rules

- **Frontend:** Follow React 19 patterns from `.claude/rules/react-19-standards.md` -- Server Components default, React.use() for data fetching, useOptimistic for mutations.
- **Backend:** Follow FastAPI patterns from `.claude/rules/fastapi-standards.md` -- async/await all routes, Pydantic v2 models, dependency injection.
- **Shared types:** TypeScript types in `src/shared/types/` are the source of truth. Pydantic models in `src/backend/models/` must mirror them.
- **Security:** Follow `.claude/rules/security.md` -- member_id only in logs, no PII, validate with Zod (frontend) and Pydantic (backend).

Write impl_manifest.md with: `## Summary`, `## Baseline Test Counts`, `## Final Test Counts`, `## Files Created`, `## Files Modified`, `## Test Files`

### Wave-Based Execution (when triggered)

Waves are PRE-COMPUTED in implementation_plan.md. Execute waves sequentially. Within each wave, dispatch files as parallel Task tool subagents. After each wave: run tests, update impl_state.json checkpoint.

### Manifest Validation

After impl_manifest.md is written but BEFORE proceeding to Phase 6:
1. For each file in `## Files Created`: verify it exists on disk AND is non-empty.
2. For each file in `## Files Modified`: verify it exists on disk AND is non-empty.
3. If any file is missing or empty: HALT. Set implementation = failed.

Checkpoint: implementation = completed

---

## [6] SIMPLIFY

**REQUIRED SUB-SKILL:** Invoke `simplify` via the Skill tool.

After simplify returns, the pipeline orchestrator appends a `## Simplification` section to impl_manifest.md.
Checkpoint: simplify = completed

---

## [7] REVIEW

**Launch code-review skill with auto-detect mode.** The skill automatically detects file types:
- `.ts/.tsx/.js/.jsx` files -> React 19 / TypeScript checklist
- `.py` files -> FastAPI / Python checklist
- Mixed changes -> both checklists run

Also launch `generate-tests` and `security-scan` skills in parallel.

### Spec Compliance Gate (HARD BLOCKER)

If spec-reviewer returns `spec_compliant: false`:
1. Log gaps. Increment `spec_review_to_implementation`.
2. If < 2 attempts: loop back to Phase 5. If >= 2: HALT pipeline.

Checkpoint: review = completed

---

## [8] VERIFICATION (TriStar Enhanced)

**Step 1 - Engineering Verification:**
Invoke `sdlc-verify --feature=<feature>` via Skill tool. Produces verification_report.md with requirement coverage matrix (60% weight) and test pass rate (40% weight).

**Step 2 - Security Scan:**
Invoke `security-scan` skill. Checks OWASP Top 10, Azure security, secrets, dependencies, TriStar PII rules.

**Step 3 - Domain Verification (TriStar-specific):**
For offer-related code changes:
- Invoke `loyalty-fraud-detection` skill -- checks for over-discounting, offer stacking, cannibalization, frequency abuse patterns.
- Invoke `semantic-context-matching` skill -- verifies context scoring logic, threshold rules (>60), rate limiting (1/hr/member), quiet hours (10pm-8am).

**Domain gate:** If either domain skill flags `severity === 'critical'`, verification FAILS regardless of engineering score.

Checkpoint: verification = completed

---

## [9] RISK ASSESSMENT

Launch via Task tool subagent: invoke `sdlc-risk --feature=<feature>`.
The skill includes TriStar-specific risk categories (loyalty fraud, PII exposure, rate limiting, Hub state corruption).

Gate logic:
- `ship` -> continue to [10]
- `ship_with_monitoring` -> log monitoring reqs, continue to [10]
- `fix_first` -> feed fix reqs to [5], increment risk_to_implementation, re-run [5]-[8]. If limit (3): HALT
- `redesign` -> feed feedback to [2], increment risk_to_architecture, re-run [2]-[8]. If limit (2): HALT

Checkpoint: risk = completed

---

## [10] PR CREATION

**REQUIRED SUB-SKILL:** Invoke `create-pr` via the Skill tool.

DO NOT skip this phase. The pipeline output is a PR URL, not a risk score.

The create-pr skill will:
- Use conventional commits format for PR title (`feat:`, `fix:`, etc.)
- Run `bash scripts/security-scan.sh` as pre-flight
- Include verification score, risk summary, and monitoring reqs in PR description
- Target the `planning` branch (or `main` when available)

Checkpoint: pr = completed. Output: PR URL.
Pipeline complete. Display the PR URL prominently.
