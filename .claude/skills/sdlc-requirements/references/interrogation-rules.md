# Interrogation Rules

Rules governing the interrogation phase of requirements gathering for TriStar features.

---

## Rule 1: Never Assume Layer Scope

Always ask which of Designer (Layer 1), Hub (Layer 2), and Scout (Layer 3) are affected. A feature name alone is insufficient to determine scope. Even seemingly single-layer features often have cross-layer implications.

**Example:** "Add weather-based activation" sounds Scout-only, but may require Hub to store weather preferences and Designer to configure weather thresholds.

---

## Rule 2: Never Assume OfferBrief Fields

Always confirm which OfferBrief fields are needed or modified. The schema includes: offer_id, objective, segment, construct, channels, kpis, risk_flags. Do not assume a feature uses all fields or only the obvious ones.

**Example:** "Improve offer targeting" could mean changes to segment, construct, channels, or kpis - ask which.

---

## Rule 3: Always Ask About Hub State Transitions

Every feature that touches Hub must define valid state changes. The current state machine is: draft -> approved -> active -> expired. Ask:

- Does this feature add new states?
- Does this feature add new transition paths?
- Does this feature modify transition guards (conditions)?
- Can this feature cause invalid state transitions?

---

## Rule 4: Always Ask About Rate Limiting Impact

Notifications, offer delivery, and API calls all have rate limits. For any feature involving member-facing actions:

- 1 notification per member per hour
- No duplicate offers within 24 hours
- Quiet hours: 10pm-8am (no notifications)
- Claude API: respect token limits and cost

---

## Rule 5: Always Ask About Fraud Detection Triggers

Ask which risk flags this feature could affect:

- **over_discounting**: discount > 30% of item value
- **cannibalization**: new offer competes with existing active offer for same segment
- **frequency_abuse**: member receives > 3 offers per day
- **offer_stacking**: member has > 2 concurrent active offers

If severity === 'critical', activation MUST be blocked.

---

## Rule 6: Never Skip the PII Check

For every feature, confirm:

- Only member_id appears in logs (no names, emails, addresses, phone numbers)
- GPS coordinates are not logged in plaintext (hash or omit)
- Context signals do not leak personally identifiable location patterns
- Claude API prompts do not contain member PII

---

## Rule 7: Always Ask About Context Signal Dependencies

If the feature involves Scout or activation logic, ask about:

- **GPS proximity**: is <2km threshold appropriate? What if GPS unavailable?
- **Time/day**: which time patterns matter? Quiet hours impact?
- **Weather**: which conditions? What if Weather API is down?
- **Behavior data**: how recent must it be? What if stale (>7 days)?

---

## Rule 8: Never Assume Channel Priority

If the feature involves notifications or offer delivery, confirm the delivery order:

- Default priority: Push > SMS > Email
- Does this feature change priority for certain segments?
- Does the feature need multi-channel delivery or single channel?
- What happens if preferred channel fails?

---

## Rule 9: Always Check Quiet Hours Compliance

Any feature delivering notifications or activating offers must respect:

- **Quiet hours**: 10pm-8am local time
- What timezone? Member's local timezone or system timezone?
- What happens to activations triggered during quiet hours? Queue? Discard?
- Does the feature need quiet hours override for urgent communications?

---

## Rule 10: Never Skip Backward Compatibility

Existing offers in Hub must not be corrupted by new features. Ask:

- Will existing offers in draft/approved/active states be affected?
- Does the OfferBrief schema change require migration of existing data?
- Will existing API consumers break?
- Will existing frontend views render correctly with old data?

---

## Rule 11: Always Document Non-Goals Explicitly

Prevent scope creep by explicitly documenting what the feature does NOT do:

- At least 2 non-goals per feature
- Each non-goal must have a rationale
- Non-goals prevent future misunderstandings about feature boundaries

**Example:**
- NG-001: This feature does NOT modify the fraud detection algorithm - Rationale: Fraud detection is a separate concern handled by the loyalty-fraud-detection skill
- NG-002: This feature does NOT add new notification channels - Rationale: Channel expansion is planned for Q3

---

## Interrogation Flow Rules

### Batching
- Ask 2-3 questions per category to reduce back-and-forth
- Group related questions together
- Use multiple-choice format whenever possible

### Escalation
- If an answer contradicts a previous answer, call it out immediately
- If an answer reveals a new concern, add it to the next round
- If an answer is vague ("it depends"), drill down with specific scenarios

### Termination
- Maximum 3 rounds of interrogation
- After 3 rounds, remaining unknowns become assumptions with risk_if_wrong levels
- Never proceed to draft plan with unresolved P0 questions

### Multiple Choice Guidelines
- Always include "Other (please specify)" as an option
- Order options from most common to least common
- Include "Not applicable" when the question may not apply
- Limit to 4-6 options per question
