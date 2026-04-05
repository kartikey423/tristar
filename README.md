# TriStar — Triangle Smart Targeting and Real-Time Activation

AI-powered loyalty offer system for Canadian Tire Corporation (CTC). Generates personalised offers via Claude AI, manages offer lifecycle through a shared Hub, and activates them in real time based on member context (location, time, weather, purchase behaviour).

---

## Branch Guide

| Branch | Status | Purpose |
|--------|--------|---------|
| `develop` | **Latest working code** | Clone this to run the app |
| `feat/scout-mobile-notification-ui` | Latest feature | iPhone-style push notification UI, auto-approve on tap |
| `feat/scout-smart-offers` | Merged feature | 75/25 payment split, smart multi-offer match, partner store details |
| `main` | Older baseline | Do **not** use for demos |

> **Always use `develop` branch.** It contains all fixes and features merged and tested.

---

## What TriStar Does

```
Designer (Layer 1)   →   Hub (Layer 2)   →   Scout (Layer 3)
Marketer copilot         Shared state         Real-time activation
Claude AI generates      draft→approved       Location + time scoring
OfferBrief               →active→expired      Partner cross-sell
                                              Mobile push notification
```

**Designer** — Marketer enters a business objective → Claude generates a structured `OfferBrief` → Fraud check → Hub save

**Hub** — Offer lifecycle store (in-memory for dev, Redis for prod). Strict status transitions enforced. Member can auto-approve by tapping notification.

**Scout** — Scores context signals (GPS, time, weather, purchase behaviour). Sends push notification when score > 60. Shows realistic iPhone lock-screen notification preview.

### Key features
- Triangle Rewards **75/25 rule** enforced everywhere — max 75% points, min 25% by card
- Partner cross-sell (Tim Hortons → Canadian Tire offer) with store name, distance, and payment breakdown
- Per-member personalised Claude scoring — different members get different notification text
- Smart multi-offer match — CTC-store offers ranked before partner offers
- iPhone-style push notification preview in Scout demo
- **Customer taps "View Offer →" → offer auto-approves and activates instantly** (no marketer required)

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.11+ (3.14 works too) |
| Node.js | 18+ (20 LTS recommended) |
| npm | 9+ |
| Git | any |

Optional: Redis (only if `HUB_REDIS_ENABLED=True`, default off) · Anthropic API key (app works without it — falls back to mock offers)

---

## Quick Start — Clone and Run in 5 Minutes

### 1. Clone the repo and switch to `develop`

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

# Install all dependencies (editable mode, includes dev tools)
pip install -e ".[dev]"
```

### 3. Create your backend `.env` file

Create a file called `.env` in the **project root** (same folder as `pyproject.toml`). Copy this block exactly — no changes needed to run locally:

```bash
CLAUDE_API_KEY=
WEATHER_API_KEY=
ENVIRONMENT=development
LOG_LEVEL=DEBUG
JWT_SECRET=dev-secret-change-in-prod
SCOUT_WEBHOOK_SECRET=dev-webhook-secret
SCOUT_MATCH_ENABLED=True
CORS_ORIGINS=["http://localhost:3000","http://localhost:3001"]
```

> **No API keys needed.** The app falls back to deterministic mock offers and mock weather. All features work end-to-end.

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

API docs: http://localhost:8000/docs

### 5. Generate your frontend JWT token

The frontend needs a JWT to call authenticated Hub endpoints. Run this once (backend must be running):

```bash
curl -s -X POST "http://localhost:8000/api/auth/demo-token?role=marketing" | python3 -m json.tool
```

Copy the `access_token` value from the response.

### 6. Create your frontend `.env.local` file

```bash
cd src/frontend
cp .env.local.example .env.local
```

Open `src/frontend/.env.local` and replace both `REPLACE_WITH_YOUR_TOKEN` placeholders with the token you copied:

```bash
MARKETER_JWT=<paste-token-here>
NEXT_PUBLIC_MARKETER_JWT=<paste-same-token-here>
API_URL=http://localhost:8000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

> **Both `MARKETER_JWT` and `NEXT_PUBLIC_MARKETER_JWT` must be the same token.** `MARKETER_JWT` is used by server-side components; `NEXT_PUBLIC_MARKETER_JWT` is used by browser-side calls (e.g. notification tap auto-approve).

Token is valid for 100 hours. If you get 401 errors, regenerate with the curl command above.

### 7. Start the frontend (new terminal)

```bash
# From the project root
npm install
npm run dev
```

Frontend: http://localhost:3000

---

## Running Tests

```bash
# All unit + integration tests (recommended)
pytest tests/unit/ tests/integration/ -q --ignore=tests/unit/backend/services/test_delivery_constraint_service.py

# Unit tests only (fast, ~10s)
pytest tests/unit/ -q

# Integration tests only
pytest tests/integration/ -q

# With coverage report
pytest tests/unit/ tests/integration/ --cov=src/backend --cov-report=term-missing

# Specific suite
pytest tests/integration/backend/test_scout_offer_personalisation.py -v
```

Target coverage: **≥80%** (enforced in CI). Current: ~227 passing.

---

## Common Issues & Fixes

### Backend won't start — `ModuleNotFoundError`

```bash
# Must install from project root in editable mode
pip install -e ".[dev]"
```

### Frontend 401 / "Unauthorized" errors

Token expired (100h TTL). Regenerate:

```bash
curl -s -X POST "http://localhost:8000/api/auth/demo-token?role=marketing" | python3 -m json.tool
```

Paste the new token into **both** `MARKETER_JWT` and `NEXT_PUBLIC_MARKETER_JWT` in `src/frontend/.env.local`, then restart the frontend (`Ctrl+C` → `npm run dev`).

### Scout "Cannot reach Scout API" error

Backend is not running. Start it first:
```bash
uvicorn src.backend.main:app --reload --port 8000
```

Also confirm `NEXT_PUBLIC_API_URL=http://localhost:8000` is in `src/frontend/.env.local`.

### Designer "Fraud check blocked — member already has 3 active offers"

Fixed in `develop`. The fraud threshold is now **5 offers** (raised from 3). If still occurring, clear stale Python cache:
```bash
find . -name "__pycache__" -type d | xargs rm -rf
```
Then restart the backend.

### Partner trigger shows no offer after firing

The partner trigger returns **HTTP 202** immediately — offer generation runs in the background (~2s). Switch to the **Hub** tab and refresh to see the active offer.

### Notification tap "View Offer →" does nothing

Make sure `NEXT_PUBLIC_MARKETER_JWT` is set in `src/frontend/.env.local` (it's separate from `MARKETER_JWT` — both are needed). Restart the frontend after updating.

### Offers showing as duplicates in Hub

```bash
# Wipe in-memory store without restarting backend
curl -X DELETE http://localhost:8000/api/hub/admin/reset
# Or use the Hub UI "Reset Hub" button
```

### `npm install` peer dependency warnings

```bash
npm install --legacy-peer-deps
```

### Python `pycache` stale bytecode causing unexpected behaviour

```bash
find . -name "__pycache__" -type d | xargs rm -rf
```

---

## Environment Variables Reference

### Backend (`.env` in project root)

| Variable | Default | Description |
|----------|---------|-------------|
| `CLAUDE_API_KEY` | `""` | Anthropic API key. Leave blank for mock offers |
| `WEATHER_API_KEY` | `""` | OpenWeatherMap key. Leave blank for mock weather |
| `ENVIRONMENT` | `development` | `development` or `production` |
| `JWT_SECRET` | `dev-secret-change-in-prod` | **Change in production** |
| `SCOUT_WEBHOOK_SECRET` | `dev-webhook-secret` | HMAC secret for Scout webhooks |
| `SCOUT_MATCH_ENABLED` | `True` | Enable Scout match endpoint |
| `PURCHASE_TRIGGER_ENABLED` | `False` | Enable real-time purchase trigger flow |
| `HUB_REDIS_ENABLED` | `False` | Use Redis instead of in-memory Hub store |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection (only if `HUB_REDIS_ENABLED=True`) |
| `DATABASE_URL` | `sqlite+aiosqlite:///tristar.db` | Audit log database |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose output |
| `QUIET_HOURS_START` | `22` | No notifications after 10pm |
| `QUIET_HOURS_END` | `8` | No notifications before 8am |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed frontend origins |

### Frontend (`src/frontend/.env.local`)

| Variable | Description |
|----------|-------------|
| `MARKETER_JWT` | JWT token for server-side Hub calls (Next.js SSR) |
| `NEXT_PUBLIC_MARKETER_JWT` | Same token — for browser-side calls (notification tap auto-approve) |
| `API_URL` | Backend URL for server-side fetch (default `http://localhost:8000`) |
| `NEXT_PUBLIC_API_URL` | Backend URL for browser-side fetch (default `http://localhost:8000`) |

---

## Key API Endpoints

Full interactive docs at http://localhost:8000/docs

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/designer/generate` | Bearer | Generate OfferBrief from objective via Claude |
| `GET` | `/api/hub/offers` | None | List all Hub offers (with optional filters) |
| `PUT` | `/api/hub/offers/{id}/status` | Bearer | Update offer status (marketer) |
| `POST` | `/api/hub/offers/{id}/customer-accept` | None | **Customer tap: auto-approve + activate** |
| `POST` | `/api/hub/offers/{id}/redeem` | Bearer | Validate 75/25 Triangle Rewards split |
| `POST` | `/api/scout/match` | None | Score context against active offers |
| `POST` | `/api/scout/smart-match` | None | Multi-offer ranked match (CTC first, then partner) |
| `POST` | `/api/scout/partner-trigger` | HMAC | Tim Hortons / partner cross-sell trigger |
| `GET` | `/api/scout/activation-log/{member_id}` | None | Member activation history |
| `POST` | `/api/auth/demo-token` | None | Get a demo JWT for Swagger testing |
| `GET` | `/health` | None | Health check |

### Get a demo JWT for Swagger

```bash
curl -X POST "http://localhost:8000/api/auth/demo-token?role=marketing"
# Paste the access_token into Swagger "Authorize" → Bearer <token>
```

---

## Triangle Rewards 75/25 Rule

Enforced in all Scout notifications and Hub validation. Triangle points can cover **at most 75%** of a transaction. The remaining **25%+ must be paid by card**.

Example breakdown shown in Scout notification:
```
Offer price:          $24.99
Triangle Points (75%): −$18.74
You pay (min 25%):     $6.25
```

Attempting `points_pct: 100` on `/api/hub/offers/{id}/redeem` returns HTTP 422 with a clear error.

---

## Scout — Customer Notification Flow

1. Customer completes a purchase at a CTC or partner store
2. Scout scores context signals — if score > 60, an offer activates
3. An iPhone-style lock-screen notification preview appears in the UI
4. Customer taps **"View Offer →"** on the notification
5. `POST /api/hub/offers/{id}/customer-accept` is called — offer goes `draft → approved → active` automatically
6. Green checkmark confirmation screen appears on the phone mockup
7. The Hub tab immediately shows the offer as `active`

No marketer approval step is needed for customer-triggered activations.

---

## Project Structure

```
tristar/
├── src/
│   ├── backend/
│   │   ├── api/          # FastAPI routes (designer.py, hub.py, scout.py)
│   │   ├── core/         # Config, security, auth, dependencies
│   │   ├── models/       # Pydantic v2 models (offer_brief.py, scout_match.py, etc.)
│   │   └── services/     # Business logic (claude_api, scout_match_service, partner_trigger, etc.)
│   └── frontend/
│       ├── app/          # Next.js 15 App Router pages (designer/, hub/, scout/)
│       ├── components/   # React components (Designer/, Hub/, Scout/)
│       │   └── Scout/
│       │       ├── ContextDashboard.tsx        # Purchase event simulator
│       │       ├── MobileNotificationPreview.tsx  # iPhone-style push notification UI
│       │       └── ActivationFeed.tsx          # Activation history log
│       ├── lib/          # API clients (scout-api.ts — includes customerAcceptOffer)
│       └── services/     # Server-side Hub API (hub-api.ts)
├── tests/
│   ├── unit/             # Fast unit tests (no network/DB)
│   ├── integration/      # API + service integration tests
│   └── e2e/              # Playwright end-to-end (needs full stack)
├── docs/                 # Architecture docs
├── .env                  # Your local backend secrets (gitignored — create manually)
├── src/frontend/.env.local  # Your local frontend secrets (gitignored — create manually)
├── pyproject.toml        # Python deps + tool config
└── package.json          # Frontend deps
```

---

## Notes for New Contributors

- **No external services required** — everything falls back gracefully (mock Claude, mock weather, in-memory Hub, SQLite audit)
- **Authentication** — use `dev-secret-change-in-prod` as `JWT_SECRET` locally; get tokens via `/api/auth/demo-token`
- **Both JWT env vars required** — `MARKETER_JWT` (server-side) and `NEXT_PUBLIC_MARKETER_JWT` (browser-side) must both be set
- **Tests** use `pytest-asyncio` in auto mode — no `@pytest.mark.asyncio` needed on new tests
- **Frontend** uses Next.js 15 App Router with React 19 Server Components — only interactive parts use `'use client'`
- **Scout scoring** threshold is 60 (strictly greater than). Fallback scoring is deterministic when no Claude API key is set
