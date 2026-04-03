#!/bin/bash
# TriStar Hackathon Demo Script
# Exercises Designer → Hub → Scout pipeline end-to-end.
#
# Usage:
#   bash scripts/demo.sh                        # Uses http://localhost:8000
#   bash scripts/demo.sh http://my-server:8000  # Custom base URL
#
# Prerequisites:
#   - Backend running: uvicorn src.backend.main:app --reload --port 8000
#   - pip install PyJWT (for token generation)
#   - jq installed for JSON formatting (optional but recommended)

set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

# ── Helpers ────────────────────────────────────────────────────────────────────

_bold() { printf '\033[1m%s\033[0m\n' "$*"; }
_step() { echo; _bold "▶ $*"; }
_ok()   { echo "  ✓ $*"; }

_json() {
  if command -v jq &>/dev/null; then
    echo "$1" | jq .
  else
    echo "$1"
  fi
}

# Generate a signed system JWT using the dev secret
JWT=$(python3 -c "
import sys
try:
    import jwt
    token = jwt.encode(
        {'sub': 'demo-user', 'role': 'system'},
        'dev-secret-change-in-prod',
        algorithm='HS256'
    )
    print(token)
except ImportError:
    print('ERROR: PyJWT not installed. Run: pip install PyJWT', file=sys.stderr)
    sys.exit(1)
")

AUTH="-H \"Authorization: Bearer $JWT\""

echo
_bold "================================================"
_bold "  TriStar Demo — $(date '+%Y-%m-%d %H:%M')"
_bold "  API: $BASE_URL"
_bold "================================================"

# ── Step 1: Designer — generate OfferBrief via Claude AI ──────────────────────

_step "Step 1 — Designer: Generate OfferBrief from business objective"

OFFER_JSON=$(curl -s -X POST "$BASE_URL/api/designer/generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "objective": "Reactivate lapsed outdoor enthusiasts with a targeted gear promotion",
    "segment_criteria": ["high_value", "lapsed_90_days", "outdoor"]
  }')

_ok "Response:"
_json "$OFFER_JSON"

OFFER_ID=$(echo "$OFFER_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('offer_id',''))" 2>/dev/null || echo "")

# ── Step 2: Hub — save, approve, and activate the offer ───────────────────────

_step "Step 2 — Hub: Save, approve, and activate the generated offer"

if [ -z "$OFFER_ID" ]; then
  echo "  (Designer step skipped or failed — using fixture offer for Hub demo)"
  OFFER_ID="550e8400-e29b-41d4-a716-446655$(date +%s | tail -c 6)"
  OFFER_BODY="{
    \"offer_id\": \"$OFFER_ID\",
    \"objective\": \"Reactivate lapsed outdoor enthusiasts with a targeted gear promotion\",
    \"segment\": {\"name\": \"lapsed_outdoor\", \"definition\": \"High-value outdoor buyers inactive 90 days\", \"estimated_size\": 8000, \"criteria\": [\"high_value\", \"lapsed_90_days\"]},
    \"construct\": {\"type\": \"points_multiplier\", \"value\": 3, \"description\": \"3x points on outdoor gear\"},
    \"channels\": [{\"channel_type\": \"push\", \"priority\": 1}],
    \"kpis\": {\"expected_redemption_rate\": 0.18, \"expected_uplift_pct\": 30.0},
    \"risk_flags\": {\"over_discounting\": false, \"cannibalization\": false, \"frequency_abuse\": false, \"offer_stacking\": false, \"severity\": \"low\", \"warnings\": []},
    \"status\": \"draft\",
    \"trigger_type\": \"marketer_initiated\"
  }"
  curl -s -X POST "$BASE_URL/api/hub/offers" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $JWT" \
    -d "$OFFER_BODY" | python3 -c "import sys,json; d=json.load(sys.stdin); print('  Saved offer:', d.get('offer_id'))"
fi

# Approve
echo "  → Approving offer $OFFER_ID..."
curl -s -X PUT "$BASE_URL/api/hub/offers/$OFFER_ID/status?new_status=approved" \
  -H "Authorization: Bearer $JWT" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('  Status:', d.get('status'))"

# Activate
echo "  → Activating offer $OFFER_ID..."
curl -s -X PUT "$BASE_URL/api/hub/offers/$OFFER_ID/status?new_status=active" \
  -H "Authorization: Bearer $JWT" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('  Status:', d.get('status'))"

_ok "Offer is now ACTIVE in Hub"

# ── Step 3: Scout — outdoor enthusiast near CTC store (expect activation) ──────

_step "Step 3 — Scout: demo-001 (outdoor/gold) near Canadian Tire — expect ACTIVATION"

MATCH1=$(curl -s -X POST "$BASE_URL/api/scout/match" \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": "demo-001",
    "purchase_location": {"lat": 43.649, "lon": -79.398},
    "purchase_category": "sporting_goods",
    "rewards_earned": 150,
    "day_context": "weekday",
    "weather_condition": "clear"
  }')

echo "  Member: demo-001 — Outdoor/Gold"
_json "$MATCH1"

OUTCOME1=$(echo "$MATCH1" | python3 -c "import sys,json; print(json.load(sys.stdin).get('outcome', 'no_match'))" 2>/dev/null || echo "unknown")
_ok "Outcome: $OUTCOME1"

# ── Step 4: Scout — auto buyer (expect no match / low score) ─────────────────

_step "Step 4 — Scout: demo-005 (auto parts/standard) — expect NO MATCH"

MATCH2=$(curl -s -X POST "$BASE_URL/api/scout/match" \
  -H "Content-Type: application/json" \
  -d '{
    "member_id": "demo-005",
    "purchase_location": {"lat": 43.649, "lon": -79.398},
    "purchase_category": "automotive",
    "rewards_earned": 30,
    "day_context": "weekday",
    "weather_condition": "clear"
  }')

echo "  Member: demo-005 — Auto Parts/Standard"
_json "$MATCH2"

OUTCOME2=$(echo "$MATCH2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('outcome', d.get('message','no_match')))" 2>/dev/null || echo "unknown")
_ok "Outcome: $OUTCOME2"

# ── Step 5: Scout — activation log for demo-001 ───────────────────────────────

_step "Step 5 — Scout: Activation log for demo-001"

LOG=$(curl -s "$BASE_URL/api/scout/activation-log/demo-001")
_json "$LOG"

ENTRY_COUNT=$(echo "$LOG" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?")
_ok "$ENTRY_COUNT activation record(s) in log"

# ── Summary ───────────────────────────────────────────────────────────────────

echo
_bold "================================================"
_bold "  Demo complete!"
_bold "  Swagger docs: $BASE_URL/docs"
_bold "================================================"
echo
