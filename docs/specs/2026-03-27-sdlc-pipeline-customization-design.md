# SDLC Pipeline Customization for TriStar

**Date:** 2026-03-27
**Status:** Approved
**Scope:** Copy and customize SDLC pipeline skills from claude-master-plugin into TriStar repo

---

## Overview

Adapt the 10-phase SDLC pipeline from `/Users/Riyaj_Shaikh/epam_development/rbi/claude-master-plugin` for the TriStar project. The pipeline becomes a first-class project asset — no plugin framework, no external dependencies.

**Source:** `claude-master-plugin` v2.2.0 (19 skills, 7 hooks, 2 agents)
**What we take:** 12 skills + 1 command + 8 schemas
**What we skip:** Hooks, agents, evals, knowledge layer, setup.py, plugin manifests

---

## Decisions

| # | Decision | Choice |
|---|----------|--------|
| 1 | Installation approach | Direct copy into `.claude/` (Approach A) |
| 2 | SDLC pipeline scope | All 10 phases + orchestrator + checkpoint |
| 3 | Delegate skills included | code-review, security-scan, generate-tests, create-pr |
| 4 | Requirements customization | Blended — generic engineering Qs + TriStar domain context injected per category (Option C) |
| 5 | Code review strategy | Auto-detect file type — TS/React checklist vs Python/FastAPI checklist (Option A) |
| 6 | Verification integration | Chains sdlc-verify → security-scan → loyalty-fraud-detection → semantic-context-matching (Option A) |
| 7 | Security focus | Azure replaces AWS; TriStar PII rules (member_id only) added |
| 8 | PR format | Conventional commits (`feat:`, `fix:`), no Jira dependency |
| 9 | Entry point | `/sdlc` slash command |

---

## File Structure

```
.claude/
├── commands/
│   └── sdlc.md                          # /sdlc entry point
├── skills/
│   ├── sdlc-pipeline/
│   │   ├── SKILL.md                     # 10-phase orchestrator
│   │   ├── references/
│   │   │   ├── execution-flow.md        # Per-phase instructions
│   │   │   ├── pipeline-state-schema.md # Checkpoint state schema
│   │   │   └── artifact-digest.md       # Artifact summary template
│   │   └── appendix/
│   │       └── subagent-prompts.md      # Wave execution dispatch templates
│   ├── sdlc-requirements/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── interrogation-questions.md  # Generic + TriStar domain Qs
│   │       ├── interrogation-rules.md
│   │       ├── draft-plan-template.md
│   │       └── quality-gates.md
│   ├── sdlc-architecture/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── architecture-process.md
│   │       ├── architecture-quality-gates.md
│   │       └── tristar-patterns.md         # TriStar 3-layer + tech stack patterns
│   ├── sdlc-design-review/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── review-dimensions.md
│   ├── sdlc-impl-planning/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── tristar-dependencies.md     # Layer dependency ordering
│   ├── sdlc-checkpoint/
│   │   └── SKILL.md
│   ├── sdlc-verify/
│   │   ├── SKILL.md                        # Integrates domain skill invocation
│   │   └── references/
│   │       ├── verification-steps.md
│   │       └── verification-checklist.md
│   ├── sdlc-risk/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── risk-process.md
│   │       └── tristar-risk-catalog.md     # Loyalty fraud, PII, rate limiting risks
│   ├── code-review/
│   │   ├── SKILL.md                        # Auto-detect TS vs Python
│   │   └── references/
│   │       ├── frontend-checklist.md       # React 19 / TypeScript / Next.js 15
│   │       └── backend-checklist.md        # FastAPI / Pydantic v2 / Python
│   ├── security-scan/
│   │   ├── SKILL.md                        # Azure + TriStar PII rules
│   │   └── references/
│   │       ├── owasp-top10.md
│   │       └── azure-security-checklist.md # Replaces AWS checklist
│   ├── generate-tests/
│   │   ├── SKILL.md                        # Jest + pytest dual-stack
│   │   └── templates/
│   │       ├── jest-unit.md                # React Testing Library patterns
│   │       └── pytest-unit.md              # FastAPI + httpx patterns
│   └── create-pr/
│       ├── SKILL.md                        # Conventional commits, no Jira
│       └── templates/
│           └── pr-description.md
└── schemas/
    ├── problem_spec.schema.json
    ├── design_spec.schema.json
    ├── design_review.schema.json
    ├── risk_assessment.schema.json
    ├── verification_report.schema.json
    ├── implementation_manifest.schema.json
    ├── impl_state.schema.json
    └── clarification_questions.schema.json
```

**Artifacts output directory:** `docs/artifacts/`

---

## Customizations by Skill

### sdlc-pipeline (Orchestrator)

**Source:** `claude-master-plugin/skills/sdlc-pipeline/SKILL.md`

Changes:
- Remove all `{{ORG_NAME}}`, `{{JIRA_PREFIX}}`, `{{ORG_SHORT}}` placeholders
- Replace `--ticket` argument with `--feature` (TriStar uses feature names)
- Update phase 7 to invoke `code-review` with auto-detect mode
- Update phase 8 to chain: `sdlc-verify` → `security-scan` → `loyalty-fraud-detection` → `semantic-context-matching`
- Update phase 10 to use conventional commits format
- Artifact storage: `docs/artifacts/`
- Schema validation: `.claude/schemas/`

### sdlc-requirements (Phase 1)

**Source:** `claude-master-plugin/skills/sdlc-requirements/SKILL.md`

Changes:
- Keep all 12 generic engineering question categories
- Inject TriStar domain context into each:
  - **Data Model** → OfferBrief schema (offer_id, objective, segment, construct, channels, kpis, risk_flags), Hub state transitions (draft → approved → active → expired)
  - **Security** → PII rules (member_id only in logs), rate limiting (1 notification/member/hour), quiet hours (10pm-8am)
  - **Error States** → Claude API failures (3 retries, exponential backoff), weather API downtime, context signal unavailability, fraud detection blocks
  - **Performance** → <200ms API p95, <500ms activation, <2s FCP
  - **Integration** → Designer→Hub→Scout pipeline, Claude API (claude-sonnet-4-6), Weather API, Redis (prod Hub state)
- Add new category: **Loyalty Domain** — offer lifecycle, discount thresholds, channel priority (Push > SMS > Email), cannibalization rules, segment definitions

### sdlc-architecture (Phase 2)

**Source:** `claude-master-plugin/skills/sdlc-architecture/SKILL.md`

Changes:
- Replace AWS patterns with Azure equivalents:
  - Lambda → Azure Functions
  - ECS → Azure App Service
  - DynamoDB → Azure SQL Database
  - S3 → Azure Blob Storage
  - CloudFront → Azure CDN
  - CDK/SAM → Bicep/ARM templates
  - Parameter Store → Azure Key Vault
- Replace Node.js/Turborepo with:
  - Frontend: React 19 + Next.js 15 (App Router, Server Components)
  - Backend: FastAPI + Pydantic v2 (async, dependency injection)
  - Shared: TypeScript types as source of truth, mirrored in Pydantic models
- Add TriStar 3-layer architecture as baseline pattern in `tristar-patterns.md`
- Reference existing `docs/ARCHITECTURE.md` (6 Mermaid diagrams, 582 lines)

### sdlc-design-review (Phase 3)

**Source:** `claude-master-plugin/skills/sdlc-design-review/SKILL.md`

Changes:
- Keep all 6 review dimensions
- Add TriStar-specific checks within each:
  - **Codebase validation** → verify React 19 patterns (Server Components default, React.use()), FastAPI async patterns
  - **Architectural** → verify 3-layer separation, Hub state transition validity, no direct Designer→Scout bypass
  - **Assumptions** → challenge context signal availability, offer targeting accuracy, weather API reliability
- Scoring stays 0-100, same gate rules (approve / approve_with_concerns / reject)

### sdlc-impl-planning (Phase 4)

**Source:** `claude-master-plugin/skills/sdlc-impl-planning/SKILL.md`

Changes:
- Wave ordering respects TriStar layer dependencies:
  1. `src/shared/types/` — OfferBrief schema (Zod + TypeScript)
  2. `src/backend/models/` — Pydantic v2 models
  3. `src/backend/services/` — Business logic (offer_generator, fraud_detector, context_matcher)
  4. `src/backend/api/` — FastAPI routes (designer, hub, scout)
  5. `src/frontend/services/` — API clients
  6. `src/frontend/components/` — React 19 components
  7. `tests/unit/` + `tests/integration/` — Test coverage
- Reference scoped rules as implementation constraints:
  - `.claude/rules/react-19-standards.md`
  - `.claude/rules/fastapi-standards.md`
  - `.claude/rules/code-style.md`
  - `.claude/rules/testing.md`
  - `.claude/rules/security.md`

### sdlc-checkpoint

**Source:** `claude-master-plugin/skills/sdlc-checkpoint/SKILL.md`

Changes:
- Update artifact path to `docs/artifacts/`
- Update schema path to `.claude/schemas/`
- No other changes (generic save/load/validate mechanics)

### sdlc-verify (Phase 8)

**Source:** `claude-master-plugin/skills/sdlc-verify/SKILL.md`

Changes:
- Keep requirement coverage matrix (60% weight) + test pass rate (40% weight)
- Add domain verification step after engineering checks:
  1. Invoke `loyalty-fraud-detection` skill — check for over-discounting, offer stacking, cannibalization in offer-related code
  2. Invoke `semantic-context-matching` skill — verify context scoring logic, threshold rules (>60), rate limiting (1/hr/member)
- Verification fails if domain skills flag `severity === 'critical'`
- Existing skills stay in their current `.claude/skills/` location — invoked via Skill tool

### sdlc-risk (Phase 9)

**Source:** `claude-master-plugin/skills/sdlc-risk/SKILL.md`

Changes:
- Keep generic risk categories (failure modes, attack scenarios, blind spots, stress tests)
- Add `tristar-risk-catalog.md` with domain-specific risks:
  - **Loyalty fraud:** over-discounting (>30% discount), frequency abuse (>3 offers/day), offer stacking (>2 concurrent), cannibalization
  - **PII exposure:** member names/emails/addresses in logs, GPS coordinates in plaintext, context signals leaking location
  - **Rate limiting failures:** notification spam (>1/hr), duplicate offers within 24h window, quiet hours violation (10pm-8am)
  - **Context signal reliability:** GPS unavailability, weather API downtime (fallback?), stale behavior data (>7 days old)
  - **Hub state corruption:** race conditions on status transitions, orphaned offers (approved but never activated), Redis failover data loss

### code-review (Phase 7 delegate)

**Source:** `claude-master-plugin/skills/code-review/SKILL.md`

Changes:
- Replace single JS/TS checklist with auto-detection:
  - Detect changed file extensions
  - `.ts/.tsx/.js/.jsx` → load `frontend-checklist.md`
  - `.py` → load `backend-checklist.md`
  - Mixed changes → run both
- **Frontend checklist** (React 19 / TypeScript / Next.js 15):
  - Server Components by default (no unnecessary 'use client')
  - React.use() over useEffect for data fetching
  - useOptimistic for instant-feel mutations
  - TypeScript strict mode, no `any`
  - Zod validation at API boundary
  - Tailwind CSS (no inline styles)
  - Accessibility: ARIA labels, semantic HTML, keyboard navigation
- **Backend checklist** (FastAPI / Python):
  - async/await for all routes and I/O
  - Pydantic v2 models with Field validators
  - Dependency injection (Depends())
  - Structured logging with loguru (no print())
  - Type hints on all functions
  - Google-style docstrings on public methods
  - No global mutable state (use Redis/database)

### security-scan (Phase 8 delegate)

**Source:** `claude-master-plugin/skills/security-scan/SKILL.md`

Changes:
- Replace AWS IAM checks with Azure equivalents:
  - Key Vault usage (no hardcoded secrets)
  - App Service CORS configuration (no `allow_origins=["*"]` in prod)
  - Azure AD / JWT token validation
  - HTTPS enforcement via HTTPSRedirectMiddleware
- Keep: OWASP Top 10, secrets scanning, dependency auditing (npm audit + pip-audit)
- Add TriStar-specific:
  - PII check: only `member_id` in logs (grep for email, name, address, phone patterns)
  - .env file exposure check
  - Claude API key handling (never logged, never in client-side code)
  - Rate limiting configuration verification
  - SQL injection in SQLAlchemy queries (parameterized only)

### generate-tests (Implementation delegate)

**Source:** `claude-master-plugin/skills/generate-tests/SKILL.md`

Changes:
- Dual-stack test generation:
  - **Frontend:** Jest + React Testing Library
    - `screen.getByRole` preferred over `getByTestId`
    - `waitFor` for async assertions
    - Mock external APIs (Claude, Weather)
    - Snapshot testing sparingly
  - **Backend:** pytest + httpx AsyncClient
    - `@pytest.mark.asyncio` for async tests
    - Fixtures for database sessions and API clients
    - `freezegun` for time-dependent tests
    - Mock Claude API with `AsyncMock`
  - **E2E:** Playwright
    - Critical path: Designer → Hub → Scout
    - Test file: `tests/e2e/*.spec.ts`
- Coverage target: >80% on business logic
- Test naming: `test_<what>_when_<condition>_then_<expected>`

### create-pr (Phase 10 delegate)

**Source:** `claude-master-plugin/skills/create-pr/SKILL.md`

Changes:
- Remove Jira ticket requirement
- PR title format: `<type>: <description>` (conventional commits)
  - Types: feat, fix, docs, refactor, test, chore
- PR body: Summary + Test Plan + checklist
- Pre-flight: auto-run `bash scripts/security-scan.sh`
- No `Co-Authored-By` line (per user's global CLAUDE.md)
- Branch naming: `feature/<description>` or `bugfix/<description>`

---

## Schemas

All 8 schemas copied unchanged from `claude-master-plugin/.claude/schemas/`:

| Schema | Artifact | Phase |
|--------|----------|-------|
| `clarification_questions.schema.json` | Interrogation questions | 1 |
| `problem_spec.schema.json` | Requirements specification | 1 |
| `design_spec.schema.json` | Architecture document | 2 |
| `design_review.schema.json` | Review gate decision | 3 |
| `implementation_manifest.schema.json` | Wave plan + file mapping | 4 |
| `impl_state.schema.json` | Mid-implementation checkpoint | 5 |
| `verification_report.schema.json` | Verification results | 8 |
| `risk_assessment.schema.json` | Risk analysis + ship decision | 9 |

---

## /sdlc Command

```
Usage: /sdlc [arguments]

Arguments:
  --feature <name>     Feature name for artifact naming (e.g., "designer-ui")
  --resume             Resume from last checkpoint
  --from <phase>       Start from specific phase (1-10)
  --waves <n>          Max implementation waves (default: 5)

Examples:
  /sdlc --feature designer-ui
  /sdlc --resume
  /sdlc --from 5 --feature designer-ui
```

---

## Existing Skill Integration

The SDLC pipeline invokes two existing TriStar skills during Phase 8 (Verification):

1. **`loyalty-fraud-detection`** (existing at `.claude/skills/loyalty-fraud-detection/`)
   - Invoked via: `Skill tool` with skill name
   - Checks: over-discounting, offer stacking, frequency abuse, cannibalization
   - Blocks verification if severity === 'critical'

2. **`semantic-context-matching`** (existing at `.claude/skills/semantic-context-matching/`)
   - Invoked via: `Skill tool` with skill name
   - Checks: context scoring logic, threshold validation (>60), rate limiting (1/hr/member)
   - Blocks verification if scoring rules violated

These skills are NOT copied or modified — they're invoked in-place.

---

## Coexistence with adic-pipeline

The existing `adic-pipeline` skill (8-stage simplified SDLC) remains available. The new `/sdlc` pipeline is more comprehensive:

| Aspect | adic-pipeline | /sdlc pipeline |
|--------|--------------|----------------|
| Phases | 8 | 10 |
| Artifacts | Markdown only | JSON-validated schemas |
| Checkpoints | None | Save/resume support |
| Domain integration | None | Fraud detection + context matching |
| Code review | Generic | Auto-detect TS vs Python |
| Entry point | Auto-trigger | `/sdlc` command |

No conflicts — different skill names, different triggers.

---

## Prompts for Future Sessions

After implementation, these prompts will be available:

```
/sdlc --feature <name>           # Start full pipeline for a feature
/sdlc --resume                   # Resume from last checkpoint
/sdlc --from 5 --feature <name>  # Jump to implementation phase
```

Individual skills can also be invoked directly:
```
"run code review"                 # Triggers code-review skill
"run security scan"               # Triggers security-scan skill
"generate tests for <file>"       # Triggers generate-tests skill
"create PR"                       # Triggers create-pr skill
```
