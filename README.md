# TriStar — Triangle Smart Targeting and Real-Time Activation

AI-powered loyalty offer system for Canadian Tire Corporation (CTC). Generates personalised offers via Claude AI, manages offer lifecycle through a shared Hub, and activates them in real time based on member context (location, time, weather, purchase behaviour).

---

## Branch Guide

| Branch | Status | Use this for |
|--------|--------|--------------|
| `develop` | **Latest working code** | Running the app locally, demos, code review |
| `feat/partner-triggers-and-rewards` | Feature branch | In-progress feature work |
| `main` | Older baseline | Do **not** use — not up to date |

> **Use `develop` branch to run the app.**

---

## Architecture Overview

```
Designer (Layer 1)   →   Hub (Layer 2)   →   Scout (Layer 3)
Marketer copilot         Shared state         Real-time activation
Claude AI generates      draft→approved       Location + time scoring
OfferBrief               →active→expired      Partner cross-sell
```

- **Designer** — Marketer enters a business objective → Claude generates a structured `OfferBrief` → Fraud check → Hub save
- **Hub** — Offer lifecycle store (in-memory for dev, Redis for prod). Strict status transitions enforced
- **Scout** — Scores context signals (GPS, time, weather, purchase behaviour). Sends push notification when score > 60

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | **3.11+** | 3.14 also works |
| Node.js | **18+** | 20 LTS recommended |
| npm | 9+ | Comes with Node |
| Git | any | — |

Optional (not required for dev):
- Redis — only needed if `HUB_REDIS_ENABLED=True` (default is off; in-memory store is used)
- Anthropic API key — only needed for real AI generation; app falls back to deterministic mock offers without it

---

## Quick Start (5 minutes)

### 1. Clone and switch to `develop`

```bash
git clone https://github.com/kartikey423/tristar.git
cd tristar
git checkout develop
```

### 2. Backend setup

```bash
# Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# Install all dependencies (including dev tools)
pip install -e ".[dev]"
```

### 3. Create your `.env` file

Create a file called `.env` in the project root (same folder as `pyproject.toml`):

```bash
# Minimum required for local dev — copy this block exactly
CLAUDE_API_KEY=             # Leave blank to use mock offers (no API key needed)
WEATHER_API_KEY=            # Leave blank — weather falls back to clear/mild
ENVIRONMENT=development
LOG_LEVEL=DEBUG
JWT_SECRET=dev-secret-change-in-prod
SCOUT_WEBHOOK_SECRET=dev-webhook-secret

# These defaults already match config.py — only set if you want to override
# HUB_API_URL=http://localhost:8000/api/hub
# DESIGNER_API_URL=http://localhost:8000
# DATABASE_URL=sqlite+aiosqlite:///tristar.db
# PURCHASE_TRIGGER_ENABLED=False
```

> **No API key? No problem.** The backend automatically falls back to deterministic mock offers when `CLAUDE_API_KEY` is blank. All features work end-to-end.

### 4. Start the backend

```bash
uvicorn src.backend.main:app --reload --port 8000
```

Expected output:
```
INFO  | TriStar API starting (environment=development)
INFO  | Demo seeder: 3 active offer(s) loaded into Hub
INFO  | Offer expiry task started (sweep every 300s)
INFO  | Application startup complete.
```

API docs available at: http://localhost:8000/docs

### 5. Frontend setup (separate terminal)

```bash
npm install
npm run dev
```

Frontend available at: http://localhost:3000

---

## Running Tests

```bash
# All unit + integration tests
pytest tests/ --ignore=tests/e2e -q

# Unit tests only (fast, ~5s)
pytest tests/unit/ -q

# Integration tests only
pytest tests/integration/ -q

# With coverage report
pytest tests/ --ignore=tests/e2e --cov=src/backend --cov-report=term-missing

# Specific test file
pytest tests/integration/backend/test_location_aware_partner_trigger.py -v
```

> Target coverage: **≥80%** (enforced in CI). E2E tests (`tests/e2e/`) require the full stack running and are run separately.

---

## Common Issues & Fixes

### Backend won't start — `ModuleNotFoundError`

```bash
# Make sure you installed in editable mode from the project root
pip install -e ".[dev]"
```

### Frontend won't start — `npm install` errors

```bash
# Delete node_modules and reinstall
rm -rf node_modules
npm install
```

### `sqlite3.OperationalError: unable to open database`

The SQLite audit DB is auto-created at `tristar.db` in the project root on first run. Make sure you start the backend **from the project root directory** (where `pyproject.toml` is), not from a subdirectory.

### `422 Fraud check blocked` when generating offers

This was a known bug — fixed in `develop`. The fraud stacking threshold is now **5** (raised from 3). If you still see it, make sure you're on the `develop` branch and have restarted the backend.

### Offers showing as duplicates in Hub

Fixed in `develop`. The Hub list endpoint deduplicates by objective text. A browser refresh after restarting the backend will show clean data. To wipe the in-memory store without restarting:

```bash
curl -X DELETE http://localhost:8000/api/hub/admin/reset
# Or use the Hub UI "Reset Hub" button
```

### Tim Hortons stores not visible in Scout dropdown

Fixed in `develop`. All Tim Hortons locations (including Blue Mountain and Whistler Village) are now grouped under a **Tim Hortons** optgroup in the store selector.

### Partner trigger shows no offer after firing

The partner trigger returns **HTTP 202** immediately — the offer is generated in the background (within ~2s). Switch to the **Hub** tab and refresh to see the newly created active offer.

### `CLAUDE_API_KEY` errors in logs

Expected if you left the key blank. The app logs a warning and uses mock offers. This is safe for development and demos.

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_API_KEY` | `""` | Anthropic API key. Leave blank to use mock offers |
| `WEATHER_API_KEY` | `""` | OpenWeatherMap key. Leave blank for mock weather |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `JWT_SECRET` | `dev-secret-change-in-prod` | **Change in production** |
| `SCOUT_WEBHOOK_SECRET` | `dev-webhook-secret` | HMAC secret for Scout webhooks |
| `PURCHASE_TRIGGER_ENABLED` | `False` | Enable real-time purchase trigger flow |
| `HUB_REDIS_ENABLED` | `False` | Use Redis instead of in-memory Hub store |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection (only if `HUB_REDIS_ENABLED=True`) |
| `DATABASE_URL` | `sqlite+aiosqlite:///tristar.db` | Audit log database |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose output |
| `QUIET_HOURS_START` | `22` | No notifications after 10pm |
| `QUIET_HOURS_END` | `8` | No notifications before 8am |

---

## Project Structure

```
tristar/
├── src/
│   ├── backend/
│   │   ├── api/          # FastAPI routes (designer.py, hub.py, scout.py)
│   │   ├── core/         # Config, security, dependencies
│   │   ├── models/       # Pydantic v2 models (offer_brief.py, etc.)
│   │   └── services/     # Business logic (claude_api, fraud_check, etc.)
│   └── frontend/
│       ├── app/          # Next.js 15 App Router pages
│       ├── components/   # React components (Designer/, Hub/, Scout/)
│       ├── lib/          # API clients (scout-api.ts, hub-api.ts)
│       └── services/     # Additional frontend services
├── tests/
│   ├── unit/             # Fast unit tests (no network/DB)
│   ├── integration/      # API + service integration tests
│   └── e2e/              # Playwright end-to-end (needs full stack)
├── docs/                 # Architecture docs
├── data/                 # inventory.csv
├── .env                  # Your local secrets (gitignored — create manually)
├── pyproject.toml        # Python deps + tool config
└── package.json          # Frontend deps
```

---

## Key API Endpoints

Once the backend is running, visit http://localhost:8000/docs for the full interactive API reference. Key endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/designer/generate` | Generate OfferBrief from objective |
| `POST` | `/api/designer/approve/{id}` | Approve a draft offer |
| `GET` | `/api/designer/suggestions` | AI inventory suggestions |
| `GET` | `/api/designer/live-deals` | Live Canadian Tire deals |
| `GET` | `/api/hub/offers` | List all Hub offers |
| `PUT` | `/api/hub/offers/{id}/status` | Update offer status |
| `POST` | `/api/hub/offers/{id}/redeem` | Validate 75/25 Triangle Rewards split |
| `POST` | `/api/scout/match` | Score context against active offers |
| `POST` | `/api/scout/partner-trigger` | Tim Hortons / partner cross-sell trigger |
| `POST` | `/api/auth/demo-token` | Get a demo JWT for Swagger testing |
| `GET` | `/health` | Health check |

### Getting a demo JWT for Swagger

```bash
curl -X POST "http://localhost:8000/api/auth/demo-token?role=marketing"
# Copy the access_token value → paste into Swagger "Authorize" as: Bearer <token>
```

---

## Triangle Rewards 75/25 Rule

Offers enforce that **Triangle points can cover at most 75%** of a transaction value. The remaining 25%+ must be paid via credit/debit card.

To validate a redemption:

```bash
curl -X POST http://localhost:8000/api/hub/offers/{offer_id}/redeem \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"offer_id": "...", "points_pct": 75, "cash_pct": 25}'
```

Attempting `points_pct: 100` returns HTTP 422 with a clear error message.

---

## Notes for Reviewers / New Contributors

- **No external services required** to run locally — everything falls back gracefully (mock Claude, mock weather, in-memory Hub, SQLite audit log)
- **Authentication** uses simple JWT with `dev-secret-change-in-prod` as the default secret — use `/api/auth/demo-token` to get a token
- **Branch to use:** `develop` — contains all fixes and features; `main` is an older baseline
- Tests use `pytest-asyncio` in `auto` mode — no `@pytest.mark.asyncio` decorator needed on new tests
- The frontend uses Next.js 15 App Router with React 19 Server Components — most pages are server-rendered; only interactive parts use `'use client'`
