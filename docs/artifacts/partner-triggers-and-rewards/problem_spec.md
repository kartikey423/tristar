# Problem Specification — partner-triggers-and-rewards

## Meta

| Field | Value |
|-------|-------|
| Feature | partner-triggers-and-rewards |
| Author | SDLC Requirements Skill |
| Date | 2026-04-03 |
| Status | Approved |
| Branch | feat/partner-triggers-and-rewards |

---

## Problem Statement

TriStar's Scout layer currently handles only direct member-context activations (GPS, weather, time, behavior). Three gaps exist:

1. **No payment-split enforcement:** Triangle Rewards members can theoretically redeem 100% of an offer in points. The business rule requires a minimum 25% cash/credit payment — this is not modelled or enforced anywhere in the stack.

2. **No partner-purchase triggers:** CTC has partnerships with Tim Hortons, WestJet, and Sport Chek. When a member makes a purchase at a partner store, TriStar has no mechanism to cross-sell relevant CTC products in real time.

3. **Designer UI friction:** The deal scraper is artificially capped at 6 items (preventing full clearance visibility), AI suggestions silently override marketer manual edits, and the "Generate Offer" button allows duplicate offer creation for the same inventory item.

---

## Requirements

### R-01 — Payment Split Field
`OfferBrief.construct` must include a `payment_split` sub-object: `{ points_max_pct: 75, cash_min_pct: 25 }`. This field is optional for backward compatibility; when absent, legacy offers are unaffected.

### R-02 — Redemption Enforcement
The Scout redemption service must enforce: if `payment_split` is present, points redemption may not exceed `points_max_pct` (75%) of the offer's total value. Requests exceeding this threshold must be rejected with HTTP 422 and a descriptive error.

### R-03 — Partner Trigger Endpoint
A new `POST /api/scout/partner-trigger` endpoint must accept partner purchase events with fields: `partner_id`, `partner_name`, `purchase_amount`, `purchase_category`, `member_id`, `timestamp`. Authenticated via HMAC `X-Webhook-Signature` header.

### R-04 — Haiku Classification
Upon receiving a partner purchase event, the Scout service must invoke Claude 3.5 Haiku to classify the purchase context and predict the most relevant CTC product category. Examples: coffee purchase → travel mug / car cleaning; camping gear → propane / coolers.

### R-05 — Tim Hortons Launch Partner
Tim Hortons is the only required partner at launch. The `partner_id` field and Haiku classification prompt must be designed for extensibility so additional partners (WestJet, Sport Chek) can be added without architectural changes.

### R-06 — Partner Offer Auto-Save to Hub
Partner-triggered offers must be automatically created and saved to the Hub Store with status `active` and a `valid_until` timestamp of 24 hours from creation. No marketer approval step required.

### R-07 — Haiku Failure Fallback
If Haiku classification fails (timeout, API error, invalid JSON response), the service must fall back to a generic CTC offer template appropriate to the partner category. The purchase event must never be dropped silently — a fallback offer must always be generated.

### R-08 — HMAC Authentication
All partner purchase webhook requests must be authenticated using the existing `SCOUT_WEBHOOK_SECRET` HMAC pattern (X-Webhook-Signature header). Unauthenticated requests return HTTP 401.

### R-09 — Latency SLA
The complete partner-trigger pipeline (event received → Haiku classification → Hub save → offer available) must complete in under 2 seconds at p95.

### R-10 — Scraper No Hard Limit
`DealScraperService` must remove the 6-item hard limit and return all items Haiku can extract from the clearance page. The frontend handles display pagination/infinite scroll.

### R-11 — Marketer Override Dirty Flag
`ManualEntryForm` must track a `marketer_overridden` boolean flag per editable field (specifically `offer_percentage`). Once a marketer manually edits a field, the dirty flag is set to `true` and subsequent AI suggestion updates must not overwrite that field's value.

### R-12 — Disable Duplicate Generate Button
Once an OfferBrief has been generated or approved for a specific inventory item (`product_id`), the "Generate Offer" button for that item must be visually disabled and non-clickable to prevent duplicate offer creation.

---

## Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-01 | `OfferBrief` model accepts `payment_split: {points_max_pct: 75, cash_min_pct: 25}` without validation error |
| AC-02 | Redemption with 75% points + 25% cash → accepted (HTTP 200) |
| AC-03 | Redemption with 80% points + 20% cash → rejected (HTTP 422) |
| AC-04 | Redemption with no `payment_split` field → accepted (backward compatible) |
| AC-05 | `POST /api/scout/partner-trigger` with valid Tim Hortons payload + HMAC → returns HTTP 202 |
| AC-06 | `POST /api/scout/partner-trigger` without valid HMAC → returns HTTP 401 |
| AC-07 | After valid Tim Hortons trigger, `GET /api/hub/offers` contains a new `active` offer within 2s |
| AC-08 | Partner offer has `trigger_type: "partner_triggered"` and `valid_until` set to 24h from creation |
| AC-09 | When Haiku classification fails, a fallback offer is still created and saved to Hub |
| AC-10 | `DealScraperService` returns > 6 items from clearance source when items are available |
| AC-11 | Setting `offer_percentage` manually in Designer form and then receiving an AI suggestion does not change the manually entered value |
| AC-12 | After generating an offer for inventory item X, the "Generate Offer" button for item X is disabled |
| AC-13 | `tests/unit/redemption_logic_test.py` contains tests covering AC-02, AC-03, AC-04 and all pass |
| AC-14 | Integration test simulates Tim Hortons purchase event and verifies Hub contains the resulting offer |

---

## Constraints

| ID | Constraint |
|----|-----------|
| CON-01 | Claude 3.5 Haiku for classification and scraping; Claude 3.5 Sonnet (or claude-sonnet-4-6) for offer generation |
| CON-02 | No PII in logs — member_id only (no names, emails, purchase details) |
| CON-03 | 75/25 enforcement is backend-only; no Zod schema change required in frontend |
| CON-04 | Partner trigger authentication reuses existing SCOUT_WEBHOOK_SECRET pattern |
| CON-05 | Partner-triggered offers skip marketer approval (auto-active) |
| CON-06 | In-memory store for partner event deduplication (MVP); Redis dedup is a future enhancement |
| CON-07 | `valid_until` is required for all partner-triggered offers (existing model validator) |

---

## Non-Goals

| ID | Non-Goal |
|----|---------|
| NG-01 | WestJet and Sport Chek partner integrations (future phases) |
| NG-02 | Frontend Zod validation of the 75/25 payment split |
| NG-03 | Redis-backed partner event queue or retry mechanism |
| NG-04 | Marketer override dirty flag for fields other than `offer_percentage` |
| NG-05 | A/B testing of partner offer templates |
| NG-06 | Real-time scraper WebSocket feed to Designer UI |

---

## Assumptions

| ID | Assumption | Risk if Wrong |
|----|-----------|---------------|
| A-01 | `SCOUT_WEBHOOK_SECRET` is already set in `.env` and Modal secrets | High — partner trigger endpoint will return 401 for all requests |
| A-02 | Tim Hortons purchase events can be simulated via direct API call for testing | Low — integration test uses mock payload |
| A-03 | Clearance page HTML structure is stable enough for Haiku extraction | Medium — scraper may return 0 items if CTC changes page layout |
| A-04 | `ManualEntryForm` currently uses controlled React state for `offer_percentage` | Low — confirmed by reading component code |
| A-05 | Hub Store `save_offer()` is idempotent for same `offer_id` | Medium — duplicate partner triggers could create duplicate active offers |

---

## Edge Cases

| ID | Edge Case | Expected Behaviour |
|----|-----------|-------------------|
| EC-01 | Partner sends duplicate purchase event within 60s | Deduplication via `event_id` — second event silently ignored |
| EC-02 | Member already has an active CTC offer when partner trigger fires | New partner offer still created; delivery constraints (rate-limit 1/hr) apply at notification time |
| EC-03 | `points_max_pct` = 75 exactly | Accepted (boundary condition: ≤ 75% allowed) |
| EC-04 | `points_max_pct` = 75.0001 | Rejected (strictly enforced) |
| EC-05 | Clearance page returns 0 items | Scraper returns empty list; Designer falls back to inventory suggestions |
| EC-06 | Marketer clears manually-entered value back to empty | Dirty flag remains `true`; AI suggestion can re-populate empty field |
| EC-07 | Partner trigger fires during quiet hours (10pm–8am) | Offer saved to Hub as active; notification delivery blocked by existing quiet-hours constraint |

---

## Backward Compatibility

- `payment_split` is an optional field on `OfferBrief.construct` — all existing offers without this field continue to function without change
- `TriggerType` enum gains a new value `partner_triggered` — existing `marketer_initiated` and `purchase_triggered` values are unchanged
- Hub Store API is unchanged; partner offers use the same `save_offer()` / `GET /api/hub/offers` interface
- No database migration required (in-memory Hub store)

---

## Glossary

| Term | Definition |
|------|-----------|
| Partner Trigger | A purchase event at a CTC partner store (Tim Hortons, WestJet, Sport Chek) that initiates a real-time CTC offer for the member |
| Payment Split | The 75/25 rule: Triangle Rewards points may cover at most 75% of an offer's value; 25% minimum must be paid via credit/debit |
| Dirty Flag | A boolean `marketer_overridden` tracking whether a form field has been manually edited, preventing AI from overwriting it |
| Haiku Classification | Use of Claude 3.5 Haiku to analyse partner purchase context and predict relevant CTC product categories |
| Fallback Offer | A pre-defined generic CTC offer template used when Haiku classification fails |
| HMAC Signature | Hash-based message authentication code used to verify partner webhook authenticity |
