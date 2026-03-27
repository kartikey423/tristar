# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Project:** TriStar — Triangle Smart Targeting and Real-Time Activation
**Status:** Planning phase (architecture complete, no source code yet)
**Tech Stack:** React 19 + Next.js 15, FastAPI + Pydantic v2, Claude API, Azure

---

## Project Architecture

Three-layer loyalty offer system. Full details in `docs/ARCHITECTURE.md`.

**Designer (Layer 1):** Marketer copilot that takes a business objective and generates a structured OfferBrief via Claude API. Includes fraud detection before approval.

**Hub (Layer 2):** Shared state store managing offer lifecycle. Dev: in-memory dict. Prod: Redis. Status flow: `draft → approved → active → expired`.

**Scout (Layer 3):** Real-time activation engine. Scores context signals (location, time, weather, behavior) against approved offers. Activates when score > 60.

### Key Domain Concepts

- **OfferBrief:** Core schema containing offer_id, objective, segment, construct, channels, kpis, risk_flags. Must be validated with Zod (frontend) and Pydantic (backend) before any state transition.
- **Context Signals:** GPS proximity (<2km), time/day, weather conditions, member purchase behavior.
- **Risk Flags:** over_discounting, cannibalization, frequency_abuse, offer_stacking. Block activation if severity === 'critical'.
- **Rate Limits:** 1 notification per member per hour. No duplicate offers within 24h. Quiet hours: 10pm-8am.

---

## Planned Directory Structure

```
src/
├── frontend/           # React 19 + Next.js 15 (App Router)
│   ├── app/            # Pages (designer/, hub/, scout/)
│   ├── components/     # Reusable UI components
│   ├── hooks/          # Custom React hooks
│   └── services/       # API clients
├── backend/            # FastAPI
│   ├── api/            # Route handlers (designer.py, scout.py, hub.py)
│   ├── models/         # Pydantic v2 models
│   ├── services/       # Business logic
│   └── core/           # Config, deps, security
├── shared/
│   └── types/          # offer-brief.ts (single source of truth)
tests/
├── unit/               # Jest (frontend), pytest (backend)
├── integration/        # httpx TestClient
└── e2e/                # Playwright
```

---

## Commands

### Setup (not yet initialized)
```bash
# Frontend
npm install                    # Install React 19, Next.js 15, Tailwind, Zod
npm run dev                    # Start dev server (localhost:3000)

# Backend
pip install -r requirements.txt  # FastAPI, Pydantic v2, loguru, httpx
uvicorn src.backend.main:app --reload --port 8000

# Or with pyproject.toml
pip install -e ".[dev]"
```

### Testing
```bash
# Frontend
npm test                       # Jest + React Testing Library
npm run test:e2e               # Playwright E2E tests

# Backend
pytest tests/unit/             # Unit tests
pytest tests/integration/ -m integration  # Integration tests
pytest --cov=src/backend --cov-report=term-missing  # Coverage report
```

### Linting & Formatting
```bash
# Frontend
npx eslint src/frontend/       # ESLint (TypeScript)
npx prettier --write src/      # Prettier formatting

# Backend
black src/backend/              # Black formatter (line-length=100)
isort src/backend/              # Import sorting
ruff check src/backend/         # Linting
```

### Scripts
```bash
bash scripts/security-scan.sh   # npm audit + pip-audit + secret scanning
bash scripts/code-review.sh     # ESLint + Ruff + subagent review
```

### API Docs (when backend is running)
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## Critical Guardrails

**NEVER:**
- Commit .env files, API keys, or secrets
- Skip OfferBrief schema validation before activation
- Deploy real-time triggers without isolation testing
- Modify files in `All Demo Files-20260325T171750Z-3-001/` (reference only)

**ALWAYS:**
- Validate OfferBrief schema before any Hub state transition
- Use async/await for all FastAPI routes
- Log member_id only (no PII — no names, emails, addresses in logs)
- Run `loyalty-fraud-detection` skill before offer approval
- Run `semantic-context-matching` skill for activation scoring
- Test coverage >80% for new code

---

## Git Workflow

- Branch: `main` (protected), `feature/<desc>`, `bugfix/<issue>`
- Commits: Conventional Commits — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- PRs require security scan pass and code review

---

## Environment Variables

```bash
# Required for development (.env, gitignored)
CLAUDE_API_KEY=sk-ant-...
WEATHER_API_KEY=...
DATABASE_URL=sqlite:///tristar.db
REDIS_URL=redis://localhost:6379
JWT_SECRET=dev-secret-change-in-prod
LOG_LEVEL=DEBUG
ENVIRONMENT=development
```

Production secrets go in Azure Key Vault.

---

## Claude API Integration

- Model: claude-sonnet-4-6
- Purpose: Business objective → structured OfferBrief
- Retry: 3 attempts with exponential backoff
- Cache: 5 min TTL for identical objectives

---

## Scoped Rules (auto-loaded)

Detailed standards are in `.claude/rules/` — do not duplicate here:
- `code-style.md` — Naming, formatting, linting config
- `testing.md` — Test structure, coverage, mocking patterns
- `security.md` — Input validation, secrets, OWASP compliance
- `react-19-standards.md` — Server Components, React.use(), actions, useOptimistic
- `fastapi-standards.md` — Route structure, Pydantic models, async patterns, dependency injection
