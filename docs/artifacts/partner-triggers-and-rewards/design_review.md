# Design Review: partner-triggers-and-rewards

## Review Summary

| Field | Value |
|-------|-------|
| Date | 2026-04-03 |
| Review Mode | Initial |
| Reviewer | SDLC Design Review Skill |
| Score | 55/100 |
| Decision | **APPROVE_WITH_CONCERNS** |

---

## Findings

### Dimension A: Codebase Validation

#### [CRITICAL] F-001: `HubApiClient` and Hub API server block `partner_triggered + active`

**Location:** `src/backend/services/hub_api_client.py:40` and `src/backend/api/hub.py:84`

Both the client-side assertion and the server-side Hub API endpoint enforce:
```python
if offer.status == OfferStatus.active and offer.trigger_type != TriggerType.purchase_triggered:
    raise AssertionError / HTTP 422
```
The design's partner-trigger pipeline saves offers with `status=active, trigger_type=partner_triggered`. This will **raise an AssertionError** in `HubApiClient.save_offer()` before the request even reaches the Hub server, breaking the entire partner-trigger flow at runtime.

**Required fix:** Both `hub_api_client.py` and `hub.py` must be updated to allow `trigger_type in (purchase_triggered, partner_triggered)` when `status=active`. The design spec does not include these files in its component list or implementation guidelines.

---

#### [MAJOR] F-002: Shared TypeScript types not listed as modified files

**Location:** `src/shared/types/offer-brief.ts`

The shared TypeScript file currently defines:
- `TriggerType = 'marketer_initiated' | 'purchase_triggered'` — missing `'partner_triggered'`
- `Construct` interface has no `payment_split` field

The design spec mentions "Frontend TypeScript types must mirror this" in implementation guidelines but does **not** list `src/shared/types/offer-brief.ts` as a modified file in any component definition. Without this update, the frontend will not type-check partner-triggered offers and the `payment_split` field will be unknown to Zod validators.

**Required fix:** Add `src/shared/types/offer-brief.ts` to the list of files to modify. Specify the exact TypeScript changes needed: add `'partner_triggered'` to `TriggerType` union, add `PaymentSplit` interface, add optional `payment_split?: PaymentSplit` to `Construct`.

---

#### [MINOR] F-003: `valid_until` model validator covers only `purchase_triggered`

**Location:** `src/backend/models/offer_brief.py:94-98`

```python
def validate_valid_until_for_purchase_triggered(self) -> "OfferBrief":
    if self.trigger_type == TriggerType.purchase_triggered and self.valid_until is None:
        raise ValueError("valid_until is required for purchase_triggered offers")
```

The design adds `partner_triggered` offers with `valid_until = now+24h`. The model validator must also enforce `valid_until` for `partner_triggered`. This is noted in CON-07 of the problem spec but **not reflected in the data models section** of the design spec.

**Required fix:** Update model validator condition to `trigger_type in (TriggerType.purchase_triggered, TriggerType.partner_triggered)`. Add this to the data models section.

---

### Dimension B: Architectural Review

#### [MINOR] F-004: `_seen_events` dedup dict isolation not addressed

**Location:** Design — COMP-001 dedup check

The design specifies dedup via `event_id` (60s window) matching the pattern in `purchase_event_handler.py`. However, `purchase_event_handler.py` maintains its own module-level `_seen_events: dict[str, datetime]`. The partner-trigger service will need its own dict (or share the same one, risking cross-contamination between event types).

The design is silent on whether these share state or are isolated. At scale, a shared dict causes false-positive dedup rejections if event_id namespaces overlap.

**Required fix:** Clarify that `PartnerTriggerService` uses its own isolated `_partner_seen_events` dict. Prefix event_ids with `partner:` to guarantee namespace isolation.

---

#### No other architectural violations found.
- 3-layer separation maintained ✓
- Hub state transitions valid (active → expired only) ✓
- ADRs have genuine alternatives ✓
- No Designer → Scout bypass ✓

---

### Dimension C: Assumption Challenges

#### [MAJOR] F-005: 2s latency SLA likely unachievable with sequential Haiku + Sonnet calls

**Location:** Design — Partner-Trigger Pipeline, CON-01, R-09

The pipeline is sequential:
1. HMAC verify + Pydantic (~10ms)
2. Haiku classification (~400–800ms)
3. Sonnet offer generation (~1,000–2,500ms at p95)
4. Hub save via HTTP (~100–200ms)

**Total p95 estimate: 1,510–3,510ms** — regularly exceeds the 2s SLA.

The design commits to using Sonnet for generation (CON-01) without acknowledging this constraint. On Claude API peak hours, Sonnet p95 latency can reach 3–4s alone.

**Required fix:** Either (a) use Haiku for both classification AND offer generation for partner-triggered offers (sacrificing output quality), or (b) return HTTP 202 immediately and generate/save the offer asynchronously using `BackgroundTasks`. Option (b) is architecturally cleaner — partner offer is saved within seconds but the HTTP response is instant.

---

### Dimension D: Complexity Concerns

#### [MAJOR] F-006: `offer_percentage` dirty flag references a non-existent field

**Location:** COMP-009, R-11, AC-11, `ManualEntryForm.tsx`

The design spec describes protecting `offer_percentage` with a dirty flag:
> "On onChange of `offer_percentage` input, add `'offer_percentage'` to the set"

**`offer_percentage` does not exist** in the current `ManualEntryForm`. The form has a single `objective` textarea (confirmed by reading the component source). The `discount_pct` / offer value field lives in `OfferBrief.construct.value` which is generated server-side by Claude — it is not a client-side editable input in the current Designer UI.

This means either:
- (a) The dirty flag must protect a field that will be added as part of this feature (not clearly scoped)
- (b) The dirty flag applies to a different field (e.g., `construct.value` preview in `OfferBriefCard`)

**Required fix:** Clarify which specific input field the dirty flag protects. If `offer_percentage` is a new input being added by this feature, it must be explicitly scoped in requirements. If it protects an existing field, name it correctly.

---

#### No over-engineering concerns.
- `RedemptionEnforcementService` is appropriately simple (one method) ✓
- `PaymentSplit` sub-model is warranted ✓
- Fallback dict pattern is simple and correct ✓

---

### Dimension E: Alternative Approaches

No findings. ADRs genuinely evaluated alternatives:
- ADR-001: Separate endpoint vs extend purchase-event — decision rationale is sound ✓
- ADR-002: Optional field on Construct — most backward-compatible choice ✓
- ADR-003: Few-shot Haiku — appropriate for cost and latency constraints ✓
- ADR-004: Set vs boolean flags — `Set<string>` is the correct extensible choice ✓

---

### Dimension F: Missing Considerations

#### [MINOR] F-007: No fraud detection for partner-triggered offers

**Location:** Design — Partner-Trigger Pipeline

Partner-triggered offers bypass the Designer fraud detection flow (marketer-initiated offers go through `FraudCheckService`). The design spec does not address whether `FraudCheckService` should run on partner-generated offers before Hub save.

Given that partner offers have `payment_split={75,25}` built in and use controlled fallback templates, fraud risk is low. However, the `over_discounting` flag should still be checked since Haiku/Sonnet-generated offers could produce high-discount constructs.

**Required fix:** Add a call to `FraudCheckService.check()` in `PartnerTriggerService.classify_and_generate()` after offer generation and before Hub save. Block if `severity == critical`. This is a minor gap given controlled templates, but aligns with the CLAUDE.md rule: "Run loyalty-fraud-detection before offer approval."

---

#### No PII concerns. ✓
- Logs use member_id only ✓
- No GPS data in partner events ✓
- `purchase_amount` is not PII ✓

#### No rate limiting gaps. ✓
- Existing delivery constraints (1/hr/member, quiet hours) apply at notification time ✓
- Dedup on event_id prevents duplicate offers ✓

#### Coverage targets defined. ✓
- Unit + integration tests specified for all new components ✓

---

## Score Breakdown

| Category | Count | Points Deducted |
|----------|-------|----------------|
| Critical | 1 | -15 |
| Major | 3 | -24 |
| Minor | 3 | -9 |
| Clean Dimensions | 1 (Dimension E) | +5 |
| **Base** | | **100** |
| **Total** | | **57/100** |

---

## Gate Decision

**APPROVE_WITH_CONCERNS** (Score: 57/100)

The design is architecturally sound and the component breakdown is accurate. However, **F-001 is a guaranteed runtime failure** that will break the partner-trigger pipeline entirely — `HubApiClient` and the Hub API server both enforce a hard assertion blocking `partner_triggered + active`. This **must** be fixed in implementation before any partner-trigger code can work.

**F-006** (non-existent `offer_percentage` field) also requires clarification before the dirty-flag feature can be implemented.

The pipeline can proceed to implementation planning with these concerns tracked as P0 blockers.

---

## Recommendations

1. **[P0 — Before any implementation]** Update `hub_api_client.py:40` and `hub.py:84` to allow `trigger_type in (TriggerType.purchase_triggered, TriggerType.partner_triggered)` when `status=active`. Add both files to the implementation plan's file list.

2. **[P0 — Before ManualEntryForm changes]** Define which specific input field the dirty flag protects. If `offer_percentage` is a new field being added by this feature, add it explicitly to R-11 scope. If it is `construct.value`, rename the field reference in the design.

3. **[P1]** Add `src/shared/types/offer-brief.ts` to the implementation file list with explicit changes: `TriggerType` union + `PaymentSplit` interface + `Construct.payment_split?: PaymentSplit`.

4. **[P1]** Resolve the 2s latency SLA by using `BackgroundTasks` for offer generation — return HTTP 202 immediately, run Haiku + Sonnet + Hub save asynchronously. Update the pipeline diagram in the design spec.

5. **[P2]** Extend `offer_brief.py` model validator to include `partner_triggered` in the `valid_until` requirement check.

6. **[P2]** Use isolated `_partner_seen_events` dict in `PartnerTriggerService` (not shared with `purchase_event_handler.py`). Prefix partner event_ids with `"partner:"` namespace.

7. **[P2]** Add `FraudCheckService.check()` call in `PartnerTriggerService` after offer generation, before Hub save. Block on `severity == critical`.
