# Problem Specification: designer-layer

## Meta

| Field | Value |
|-------|-------|
| **Feature Name** | designer-layer |
| **Layer(s)** | Designer (Layer 1), Hub (Layer 2 - integration only), Scout (Layer 3 - purchase event trigger) |
| **Created** | 2026-03-27 |
| **Author** | SDLC Requirements Skill |
| **Status** | Approved |
| **Priority** | P0 (Critical Path) |

---

## Problem Statement

### Context

The Triangle loyalty program currently operates reactively - members earn points after purchases but receive no intelligent, contextual engagement at the moment of maximum purchase intent. CTC marketers lack AI-powered tools to design targeted offers efficiently, and the system cannot capitalize on cross-sell opportunities when members interact with partner stores (Tim Hortons, Westside, etc.).

### The Problem

**For marketers:** Creating targeted loyalty offers is manual, time-consuming, and lacks data-driven insights about inventory levels and member segmentation. Marketers need an AI copilot that can analyze stock levels and generate structured offers (OfferBrief schema) validated against fraud patterns.

**For members:** When they make purchases at CTC or partner stores, the system misses the opportunity to deliver relevant offers immediately while they're in a purchasing mindset. A customer buying coffee at Tim Hortons is an active shopper who may be near a CTC store, but receives no intelligent prompt to visit.

### Success Criteria

1. **Marketer productivity:** Reduce offer creation time from 30+ minutes (manual) to <5 minutes (AI-assisted)
2. **Purchase-triggered activation:** Deliver personalized offers to members within 2 minutes of purchase at CTC/partner stores
3. **Cross-sell effectiveness:** Achieve >15% redemption rate for offers triggered by partner store purchases
4. **Fraud prevention:** Block 100% of critical-risk offers before activation

---

## Requirements

### P0 (Must Have)

#### REQ-001: AI-Driven Inventory Analysis
**Description:** The system shall analyze inventory levels and generate offer recommendations proactively to help marketers clear excess stock or promote high-margin products.

**Acceptance Criteria:**
- AC-001: Given inventory data with 500+ units of winter coats, When AI analyzes stock, Then suggest "Clear winter inventory" offer targeting relevant segments
- AC-002: Given low-stock items (<50 units), When AI analyzes, Then de-prioritize or exclude from suggestions
- AC-003: Given marketer views Designer UI, When page loads, Then display top 3 AI-recommended offers based on current inventory

**Priority:** P0
**Business Value:** Reduces manual effort for marketers, optimizes inventory turnover

---

#### REQ-002: Claude API Integration for OfferBrief Generation
**Description:** The system shall integrate with Claude API (claude-sonnet-4-6) to transform business objectives or purchase context into structured OfferBrief JSON containing segment, construct, channels, kpis, and risk_flags.

**Acceptance Criteria:**
- AC-004: Given marketer enters objective "Reactivate lapsed high-value members", When submit clicked, Then call Claude API with structured prompt
- AC-005: Given Claude returns valid JSON, When parsed, Then populate OfferBrief with all required fields (segment, construct, channels, kpis, risk_flags)
- AC-006: Given Claude API times out, When retry count < 3, Then retry with exponential backoff (1s, 2s, 4s)
- AC-007: Given 3 retries exhausted, When all fail, Then show error message "Unable to generate offer. Please try again."

**Priority:** P0
**Business Value:** Core AI capability enabling rapid offer design

---

#### REQ-003: Fraud Detection Integration
**Description:** The system shall validate all generated OfferBriefs using the loyalty-fraud-detection skill to identify over-discounting, offer stacking, cannibalization, and frequency abuse patterns before approval.

**Acceptance Criteria:**
- AC-008: Given generated OfferBrief, When validation runs, Then invoke loyalty-fraud-detection skill
- AC-009: Given fraud detection returns severity='critical', When marketer attempts approval, Then block with error message containing risk details
- AC-010: Given severity='low' or 'medium', When displayed, Then show warning but allow approval with confirmation

**Priority:** P0
**Business Value:** Prevents revenue loss from fraudulent or financially harmful offers

---

#### REQ-004: Hub Integration for Approved Offers
**Description:** The system shall save marketer-approved offers to the Hub via API, enabling Scout to access them for activation.

**Acceptance Criteria:**
- AC-011: Given marketer approves offer, When approval confirmed, Then POST offer to Hub with OfferBrief payload
- AC-012: Given Hub returns 201 Created, When response received, Then show success message "Offer saved to Hub"
- AC-013: Given Hub returns error (4xx/5xx), When save fails, Then show error message and provide retry option

**Priority:** P0
**Business Value:** Connects Designer to activation pipeline, enables end-to-end flow

---

#### REQ-005: JWT Authentication and Role-Based Access Control
**Description:** The system shall require JWT token authentication for all Designer API endpoints and restrict access to users with 'marketing' role only.

**Acceptance Criteria:**
- AC-014: Given unauthenticated request to /api/designer/*, When received, Then return 401 Unauthorized
- AC-015: Given authenticated user with role != 'marketing', When accessing Designer endpoints, Then return 403 Forbidden
- AC-016: Given valid JWT with marketing role, When accessing Designer, Then allow access and process request

**Priority:** P0
**Business Value:** Secures offer creation, ensures audit trail compliance

---

#### REQ-006: Dual-Mode Offer Creation (AI Suggestions + Manual Entry)
**Description:** The system shall support two offer creation modes: (1) AI Suggestions based on inventory analysis, and (2) Manual Entry where marketers provide business objectives directly.

**Acceptance Criteria:**
- AC-017: Given marketer selects "AI Suggestions" mode, When viewing, Then display recommended offers with stock context
- AC-018: Given marketer selects "Manual Entry" mode, When viewing, Then show objective input form
- AC-019: Given either mode used, When offer approved, Then save to Hub with identical OfferBrief schema

**Priority:** P0
**Business Value:** Flexibility for marketers - automated suggestions or custom objectives

---

#### REQ-007: Frontend Designer User Interface
**Description:** The system shall provide a web-based UI at /designer for marketers to generate, review, and approve offers.

**Acceptance Criteria:**
- AC-020: Given marketer navigates to /designer, When page loads, Then display mode selector (AI Suggestions / Manual Entry)
- AC-021: Given AI mode selected, When rendered, Then show top 3 stock-based recommendations with product details
- AC-022: Given Manual mode selected, When rendered, Then show objective textarea (10-500 chars) and submit button
- AC-023: Given OfferBrief generated, When displayed, Then show all fields: segment, construct, channels, kpis, risk_flags with visual formatting

**Priority:** P0
**Business Value:** User-facing interface for marketer interaction

---

#### REQ-008: Purchase-Triggered Offer Generation
**Description:** When a customer makes a purchase at CTC or partner stores (rewards credited to account), Scout shall analyze context signals (purchase location, history, nearby stores, weather, behavior) and trigger Designer to generate a personalized offer in real-time, capitalizing on the customer's active purchasing mindset.

**Acceptance Criteria:**
- AC-024: Given customer purchases at Tim Hortons (partner), When rewards credited to member account, Then trigger Scout purchase event listener
- AC-025: Given customer purchases at Sport Chek/Mark's (CTC store), When rewards credited, Then trigger Scout purchase event listener
- AC-026: Given Scout receives purchase event, When processing, Then extract: member_id, purchase_location (store name, lat/lon), purchase_amount, purchase_category, timestamp
- AC-027: Given purchase event data extracted, When Scout analyzes context, Then gather: member purchase history (last 6 months), nearby CTC stores (<2km), current weather, member behavior patterns, member segment
- AC-028: Given all context signals gathered, When Scout scores context (using defined factors) AND score > 70, Then call Designer API endpoint with context payload
- AC-029: Given Designer receives purchase-triggered request, When processing, Then generate personalized OfferBrief using Claude API with context-enriched prompt (include recent purchase details, nearby stores, member patterns)
- AC-030: Given OfferBrief generated from purchase event, When fraud check passes (severity < critical), Then auto-save to Hub with status='active' (skip manual approval)
- AC-031: Given OfferBrief saved to Hub, When complete, Then return offer_id to Scout for immediate activation
- AC-032: Given Scout receives offer_id, When ready, Then send push notification to member within 2 minutes of purchase completion

**Priority:** P0
**Business Value:** Core innovation - real-time contextual engagement during purchase mindset, drives cross-sell from partners to CTC

---

#### REQ-009: Context Signal Scoring for Purchase Triggers
**Description:** Scout shall score purchase events using multiple context factors (purchase value, nearby store proximity, purchase frequency, category affinity, partner cross-sell opportunity, weather relevance, time alignment) to determine whether to trigger Designer for offer generation. Threshold for triggering is score > 70/100.

**Acceptance Criteria:**
- AC-033: Given customer purchased at partner store (Tim Hortons, Westside), When analyzing, Then prioritize cross-sell to CTC stores (add +15pts partner cross-sell bonus)
- AC-034: Given customer purchased at CTC store (Sport Chek), When analyzing, Then prioritize upsell within CTC family (e.g., Mark's for complementary products)
- AC-035: Given purchase category is food/beverage (Tim Hortons), When analyzing, Then suggest complementary CTC products (outdoor gear, automotive)
- AC-036: Given purchase amount > $50, When analyzing, Then add +20pts to score (high-value transaction signals spending mood)
- AC-037: Given purchase is member's 2nd transaction this week, When analyzing, Then add +15pts (high engagement signal)
- AC-038: Given nearby CTC store within 1km of purchase location, When analyzing, Then add +25pts (convenience factor for redemption)
- AC-039: Given member purchase history shows affinity for suggested product category, When analyzing, Then add +20pts (category match increases relevance)
- AC-040: Given weather conditions favor suggested products (cold weather = winter gear, rain = automotive), When analyzing, Then add +10pts
- AC-041: Given all factors scored, When total > 70/100, Then trigger Designer for purchase-driven offer generation

**Priority:** P0
**Business Value:** Ensures offers are only generated for high-intent moments, prevents notification spam

---

#### REQ-010: Purchase-Triggered Offer Delivery Constraints
**Description:** The system shall respect rate limits, quiet hours, notification preferences, and delivery reliability constraints when sending purchase-triggered offers to prevent member fatigue and comply with notification policies.

**Acceptance Criteria:**
- AC-042: Given purchase-triggered offer generated, When ready to send, Then enforce rate limit: max 1 purchase-triggered offer per member per 6 hours
- AC-043: Given member received purchase-triggered offer in last 24h, When new purchase detected, Then suppress duplicate UNLESS purchase amount > $100 (high-value override)
- AC-044: Given current time in quiet hours (10pm-8am), When purchase trigger fires, Then queue offer for 8am delivery (don't send immediately)
- AC-045: Given member has notification preferences disabled, When purchase trigger fires, Then log opportunity but don't generate/send offer
- AC-046: Given offer delivery attempted 3 times and failed (push notification error), When exhausted, Then fallback to email notification
- AC-047: Given purchase-triggered offer sent, When delivered, Then mark with urgency indicator "Valid for 4 hours only" to create scarcity

**Priority:** P0
**Business Value:** Balances engagement with user experience, prevents opt-outs due to over-notification

---

#### REQ-011: Purchase Event Data Integration
**Description:** The rewards system shall publish purchase events to Scout when points are credited to member accounts, providing sufficient data to trigger contextual offer generation.

**Acceptance Criteria:**
- AC-048: Given rewards system credits points to member account, When transaction complete, Then publish purchase event to Scout with payload: {member_id, store_id, store_name, store_location, amount, category, items, timestamp}
- AC-049: Given purchase event received by Scout, When payload invalid/incomplete, Then log error and discard (don't trigger with bad data)
- AC-050: Given purchase is refund/return transaction (negative amount), When detected, Then ignore event (don't trigger offer for returns)

**Priority:** P0
**Business Value:** Enables purchase-triggered flow, provides data quality assurance

---

### P1 (Should Have)

#### REQ-012: Caching for Duplicate Objectives
**Description:** The system shall cache OfferBrief results for identical objectives for 5 minutes to reduce Claude API costs and improve response time for repeated queries.

**Acceptance Criteria:**
- AC-051: Given objective "X" submitted at T0, When same objective submitted at T0+2min, Then return cached OfferBrief (no Claude API call)
- AC-052: Given cached entry age > 5 minutes, When retrieved, Then invalidate cache and regenerate

**Priority:** P1
**Business Value:** Cost optimization, faster response for common objectives

---

#### REQ-013: Audit Logging for Compliance
**Description:** The system shall log all offer generation events (marketer-initiated and purchase-triggered) for compliance auditing, ensuring PII is excluded from logs.

**Acceptance Criteria:**
- AC-053: Given offer generated, When logged, Then include: marketer_id (or 'system' for purchase-triggered), offer_id, objective/context, timestamp, trigger_type (manual/purchase-triggered)
- AC-054: Given PII in objective, When logged, Then scrub names/emails before writing (log member_id only per TriStar standard)

**Priority:** P1
**Business Value:** Compliance with audit requirements, forensic analysis capability

---

#### REQ-014: Risk Flag Visual Indicators
**Description:** The system shall display fraud detection risk flags with color-coded visual indicators to quickly communicate severity to marketers.

**Acceptance Criteria:**
- AC-055: Given risk severity='critical', When displayed, Then show red badge with warning icon
- AC-056: Given severity='medium', When displayed, Then show yellow badge with caution icon
- AC-057: Given severity='low', When displayed, Then show gray informational badge

**Priority:** P1
**Business Value:** Improved UX for risk assessment, faster decision-making

---

#### REQ-015: Purchase-Triggered Offer Monitoring Dashboard
**Description:** The system shall provide a dashboard for marketers to monitor purchase-triggered offer performance, including generation count, activation rate, top triggering stores, and redemption rate.

**Acceptance Criteria:**
- AC-058: Given purchase-triggered offers generated, When marketer views dashboard, Then display: count generated in last 24h, activation rate (% delivered), top triggering stores (Tim Hortons, Sport Chek, etc.), redemption rate
- AC-059: Given low activation rate (<10%) detected, When threshold crossed, Then alert marketers to review context thresholds
- AC-060: Given high redemption rate from specific partner (e.g., Tim Hortons → 40% CTC redemption), When detected, Then highlight as high-value trigger for future campaigns

**Priority:** P1
**Business Value:** Data-driven optimization of purchase-triggered strategy

---

#### REQ-016: Partner Store Effectiveness Tracking
**Description:** The system shall track and rank partner store effectiveness by conversion rate to identify which partner purchases lead to highest CTC redemptions.

**Acceptance Criteria:**
- AC-061: Given purchase-triggered offers by store type, When analyzed, Then rank partner effectiveness (Tim Hortons vs Westside vs CTC internal) by conversion rate
- AC-062: Given partner with low conversion (<5%), When detected, Then flag for review (may need different offer types for that partner's customers)

**Priority:** P1
**Business Value:** Identifies high-value partner relationships, informs partnership strategy

---

### P2 (Nice to Have)

#### REQ-017: Streaming Responses for Real-Time Feedback
**Description:** The system shall stream Claude API responses incrementally to provide real-time feedback to marketers during offer generation.

**Acceptance Criteria:**
- AC-063: Given Claude API call in progress, When response streams, Then display OfferBrief fields incrementally (segment first, then construct, channels, kpis, risk_flags)

**Priority:** P2
**Business Value:** Improved perceived performance, better UX for slow API calls

---

#### REQ-018: Advanced Inventory Recommendations with ML
**Description:** The system shall use historical redemption patterns to prioritize offers for products with high past conversion rates.

**Acceptance Criteria:**
- AC-064: Given historical redemption data available, When AI suggests offers, Then prioritize products with conversion rate > 20% in last 90 days

**Priority:** P2
**Business Value:** Data-driven recommendations increase redemption likelihood

---

#### REQ-019: Purchase-Triggered Offer Learning Loop
**Description:** The system shall feed redemption outcomes back to Claude prompts to improve future purchase-triggered offer generation.

**Acceptance Criteria:**
- AC-065: Given purchase-triggered offers activated, When redemption data available, Then analyze patterns and adjust Claude prompt templates
- AC-066: Given purchases at specific partner consistently lead to CTC redemptions, When pattern detected (>30% conversion over 100 samples), Then auto-prioritize that cross-sell path in future triggers

**Priority:** P2
**Business Value:** Self-improving system, long-term optimization

---

#### REQ-020: Multi-Purchase Pattern Recognition
**Description:** The system shall detect when members make purchases at multiple partners in the same day and generate combo offers.

**Acceptance Criteria:**
- AC-067: Given member makes purchases at 2+ partners in same day, When detected, Then generate combo offer ("You shopped at Tim's and Westside - here's 20% off Sport Chek")

**Priority:** P2
**Business Value:** Enhanced personalization, rewards multi-channel shoppers

---

## Constraints

### Performance Constraints

1. **Offer Generation Latency:** p95 response time < 5 seconds for Claude API calls (includes retry logic)
2. **Purchase-Triggered End-to-End Latency:** < 3 seconds from purchase event to Hub save (Claude call + fraud check + save)
3. **Notification Delivery:** Push notification sent within 2 minutes of purchase completion for 95% of cases
4. **Frontend Page Load:** First Contentful Paint (FCP) < 2 seconds for Designer UI

### Security Constraints

1. **PII Logging:** Only member_id, marketer_id, offer_id logged. No names, emails, addresses, phone numbers in logs.
2. **Input Validation:** All user inputs validated with Zod (frontend) and Pydantic (backend) before processing
3. **Authentication:** JWT tokens required for all /api/designer/* endpoints, 1-hour expiry
4. **RBAC:** Only users with role='marketing' can access Designer endpoints

### Rate Limiting Constraints

1. **Purchase-Triggered Offers:** Max 1 per member per 6 hours, no duplicates within 24h (unless purchase > $100)
2. **Quiet Hours:** No notifications between 10pm-8am (queue for 8am delivery)
3. **Notification Preferences:** Respect member opt-out preferences at all times

### Data Constraints

1. **Inventory Data:** MVP uses mock data (CSV/JSON), minimum fields: product_id, name, stock_level, category, store_location
2. **Purchase Event Data:** Minimum fields: member_id, store_id, store_name, store_location, amount, category, timestamp
3. **Member History:** Last 6 months of purchase data sufficient for context analysis

### Technology Constraints

1. **Claude API:** claude-sonnet-4-6 model, retry 3 times with exponential backoff (1s, 2s, 4s)
2. **Frontend:** React 19 + Next.js 15 (App Router), Server Components default
3. **Backend:** FastAPI + Pydantic v2, async/await for all routes
4. **OfferBrief Schema:** Single source of truth in src/shared/types/, mirrored in backend models

### Testing Constraints

1. **Unit Test Coverage:** >80% for all new code (TriStar standard)
2. **Integration Tests:** Designer → Hub API flow must be tested end-to-end
3. **E2E Tests:** Full user flow (marketer generates offer → approves → appears in Hub) via Playwright
4. **Mock Claude API:** Use fixtures/stubs in tests to avoid API costs in CI/CD

---

## Non-Goals

1. **NG-001: Real-time inventory integration with retail systems**
   - **Rationale:** MVP uses mock/hardcoded inventory data (CSV or JSON). Real-time integration with Sport Chek, Mark's inventory systems deferred to Phase 2 due to complexity of external system integration.

2. **NG-002: Weather API integration for marketer-initiated offers**
   - **Rationale:** Weather context is only relevant for purchase-triggered flow (Scout provides weather data at activation time). Marketers don't need weather data when designing offers manually.

3. **NG-003: Comprehensive offer performance analytics dashboard**
   - **Rationale:** Basic monitoring included in P1 (count, activation rate, redemption rate). Comprehensive analytics with cohort analysis, attribution modeling, ROI tracking deferred post-MVP.

4. **NG-004: Multi-language support for objectives**
   - **Rationale:** English only for hackathon. Internationalization (i18n) for French, Spanish deferred to future releases.

5. **NG-005: Purchase-triggered offers for ALL purchases**
   - **Rationale:** MVP targets purchases >$5 at select partners only. Micro-transactions (<$5) excluded to avoid notification noise. Future expansion to all purchases after validating engagement metrics.

6. **NG-006: Real-time collaborative filtering (member similarity matching)**
   - **Rationale:** Context factors use member's own purchase history only. Collaborative filtering ("members like you also bought...") deferred to Phase 2 due to computational complexity.

7. **NG-007: Integration with external partner loyalty systems (Tim Hortons Tims Rewards)**
   - **Rationale:** MVP assumes CTC Triangle tracks all partner purchases through rewards credit events. Deep integration with partner systems (reading Tims Rewards balance, applying joint offers) deferred.

8. **NG-008: Multi-offer delivery (send 2-3 offers after one purchase)**
   - **Rationale:** Single best offer only for MVP to avoid overwhelming customers. Multi-offer A/B testing and optimal offer portfolio selection deferred to Phase 2.

---

## Assumptions

1. **ASM-001:** Mock inventory data (CSV with product_id, name, stock_level, category, store_location) is sufficient for AI suggestions in MVP
   **Risk if wrong:** medium - if AI needs richer data like sales velocity, margins, seasonality, we'll need to expand schema or integrate real inventory API

2. **ASM-002:** Claude API responds in 2-5 seconds for 95% of requests
   **Risk if wrong:** low - retry logic handles transient failures, worst case is slightly slower user experience

3. **ASM-003:** Marketers are familiar with OfferBrief schema (segment, construct, channels, kpis) and don't need extensive in-app documentation
   **Risk if wrong:** low - can add tooltips, help text, or onboarding guide post-MVP

4. **ASM-004:** Hub API exists and accepts OfferBrief JSON via POST /api/hub/offers, returns 201 Created on success
   **Risk if wrong:** high - Designer cannot function without Hub integration; requires coordination with Hub team on API contract before implementation

5. **ASM-005:** JWT authentication middleware exists or can be added to FastAPI backend with <4 hours effort
   **Risk if wrong:** medium - if not available, need to implement JWT library integration, may delay MVP by 1-2 days

6. **ASM-006:** Phased rollout with 2-3 pilot marketers is sufficient to validate Designer functionality before full release
   **Risk if wrong:** low - can expand pilot group or extend pilot duration if needed

7. **ASM-007:** Rewards system publishes purchase events with sufficient data (member_id, store, amount, category) via webhook or message queue
   **Risk if wrong:** high - purchase-triggered flow cannot work without purchase event data; requires integration with rewards team before Scout implementation

8. **ASM-008:** Purchase-triggered generation completes within 3 seconds (Claude call + fraud check + Hub save) to feel real-time
   **Risk if wrong:** medium - users may perceive delay if >5s total latency; may need to optimize Claude prompt length or parallelize fraud check

9. **ASM-009:** Claude API can handle context-enriched prompts (include member history, location, weather, recent purchase in prompt) without exceeding token limits
   **Risk if wrong:** low - can truncate purchase history to last 10 transactions or summarize if token limits approached

10. **ASM-010:** Fraud detection for purchase-triggered offers can auto-approve if severity < critical (no human-in-loop)
    **Risk if wrong:** medium - may need manual review queue for medium-severity risks if auto-approval causes financial issues

11. **ASM-011:** Push notification delivery succeeds within 30 seconds of offer generation for 95% of cases
    **Risk if wrong:** low - email fallback available, worst case is slightly delayed delivery

12. **ASM-012:** Partner stores (Tim Hortons, Westside) are integrated with CTC Triangle rewards system so purchases are tracked
    **Risk if wrong:** high - if partner purchases not visible to Triangle, purchase-triggered flow only works for CTC-owned stores (Sport Chek, Mark's, Canadian Tire), limiting cross-sell opportunity

13. **ASM-013:** Member remains in purchasing mindset for 4 hours post-purchase (offer validity window)
    **Risk if wrong:** low - can adjust validity period to 2 hours or 6 hours based on redemption data analysis

---

## Edge Cases

1. **EC-001: Claude API returns invalid JSON (missing required OfferBrief fields)**
   **Expected Behavior:** Retry once with same prompt. If still invalid, show error to user: "Generation failed. Please rephrase objective or try again." Log invalid response for debugging.

2. **EC-002: Fraud detection skill unavailable/times out after 10 seconds**
   **Expected Behavior:** For marketer-initiated: Log warning, show disclaimer "Risk validation unavailable - proceed with caution", allow approval. For purchase-triggered: Log failure, skip offer generation entirely (safety-first approach).

3. **EC-003: Hub API returns 503 Service Unavailable during offer save**
   **Expected Behavior:** Show error message with retry button. For marketer-initiated: Keep offer data in UI for retry. For purchase-triggered: Log failure, do NOT queue for retry (moment has passed).

4. **EC-004: Marketer enters empty objective or single word gibberish**
   **Expected Behavior:** Frontend Zod validation rejects before API call. Show error: "Objective must be 10-500 characters and describe a clear business goal."

5. **EC-005: Duplicate offer_id collision in Hub (UUID collision, extremely unlikely)**
   **Expected Behavior:** Hub returns 409 Conflict. Designer regenerates offer with new UUID and retries save automatically.

6. **EC-006: Claude returns OfferBrief with over-discounting risk (severity='critical'), marketer ignores warning and attempts approval**
   **Expected Behavior:** Block approval with modal: "Critical risk detected: Over-discounting (70% off exceeds 30% policy). Offer cannot be approved. Please revise objective." Force user to regenerate.

7. **EC-007: Inventory data stale (last updated >24 hours ago) or file unavailable**
   **Expected Behavior:** AI suggestions mode disabled. Show notice: "Stock data unavailable - using Manual Entry mode only." Allow marketers to continue with manual objectives.

8. **EC-008: Purchase event received but member profile incomplete (missing purchase history)**
   **Expected Behavior:** Designer generates generic offer based on current purchase data only (store location, purchase category). Log data gap for investigation. Include disclaimer in prompt: "Limited history available."

9. **EC-009: Purchase-triggered generation times out (>5 seconds)**
   **Expected Behavior:** Scout logs failure with timeout reason. Do NOT queue for retry (member may have left area, moment passed). Alert engineering team if timeout rate >5%.

10. **EC-010: Multiple purchases by same member within 1 minute (edge case: split transactions at same store)**
    **Expected Behavior:** Deduplicate by member_id + timestamp window (group purchases within 60 seconds). Treat as single purchase event with combined purchase amount.

11. **EC-011: Purchase-triggered offer generated but push notification fails 3 times (device offline, invalid token)**
    **Expected Behavior:** Queue for email delivery 10 minutes later with subject: "You just earned a special offer at [Store Name]". Log notification failure for device health monitoring.

12. **EC-012: Member makes purchase at Tim Hortons but no CTC stores within 5km radius**
    **Expected Behavior:** Skip offer generation (no nearby redemption option). Log as "no proximate CTC store" for partnership analysis (identify geographic gaps).

13. **EC-013: Fraud detection flags purchase-triggered offer as critical risk (offer stacking detected - member already has 3 active offers)**
    **Expected Behavior:** Block generation entirely. Do NOT send notification. Log incident with details: member_id, existing_offers, blocked_reason. Alert marketing team for manual review.

14. **EC-014: Purchase event data includes refund flag or negative amount**
    **Expected Behavior:** Ignore event completely. Do NOT trigger offer generation for returns/refunds. Log as "refund_ignored" for analytics.

15. **EC-015: Member opts out of notifications between purchase event and offer delivery (race condition)**
    **Expected Behavior:** Check notification preferences immediately before sending. If opted out, cancel delivery. Log as "suppressed_by_preference" to track opt-out timing.

16. **EC-016: Context score exactly equals threshold (score = 70.00)**
    **Expected Behavior:** Trigger offer generation (use >= threshold logic, not > threshold). Treat boundary as "qualified."

17. **EC-017: Marketer submits objective containing PII ("Send offer to John Doe at johndoe@email.com")**
    **Expected Behavior:** Frontend validation detects email pattern. Show warning: "Objectives should describe segments, not individuals. Remove personal information." Block submission until fixed.

18. **EC-018: Purchase-triggered offer delivery scheduled for 8am (queued during quiet hours), but member opts out at 7:50am**
    **Expected Behavior:** Pre-delivery check at 8am detects opt-out. Cancel scheduled delivery. Log as "suppressed_by_late_optout."

---

## Backward Compatibility

**Verdict:** Not applicable (new feature, no breaking changes)

**Rationale:**
This is a greenfield implementation of the Designer layer. No existing offer creation system is being replaced. The OfferBrief schema is newly defined for TriStar and does not modify any existing data structures in Triangle loyalty program.

**Migration Path:** None required.

**Impact Assessment:**
- **Existing Hub data:** No impact. Designer writes new offers to Hub using documented OfferBrief schema. Existing Hub state management unchanged.
- **Existing Scout activation:** No impact. Scout continues to activate offers from Hub. Purchase-triggered offers follow same OfferBrief schema as marketer-initiated offers.
- **Existing APIs:** No breaking changes. Designer introduces new endpoints (/api/designer/*) but does not modify existing Hub or Scout APIs.
- **Existing users:** Marketing team receives new tool. No impact on member-facing features (members only see offers delivered by Scout, which already exists).

**Future Compatibility Considerations:**
- OfferBrief schema changes require coordination across Designer, Hub, Scout (schema is shared contract)
- Purchase event payload format changes require Designer-Scout coordination
- Authentication changes (JWT → OAuth2) would require Designer API updates but not breaking schema changes

---

## Glossary

| Term | Definition |
|------|------------|
| **OfferBrief** | Core data structure containing offer_id, objective, segment, construct, channels, kpis, risk_flags. Single source of truth for offers across Designer, Hub, Scout. |
| **Designer (Layer 1)** | AI-powered marketer copilot that generates OfferBriefs from business objectives or purchase context via Claude API. |
| **Hub (Layer 2)** | Shared state store managing offer lifecycle: draft → approved → active → expired. Backed by Redis (prod) or in-memory dict (dev). |
| **Scout (Layer 3)** | Real-time activation engine that monitors context signals and delivers offers at optimal moments. Triggers Designer for purchase-driven offers. |
| **Purchase-Triggered Offer** | Offer automatically generated by Designer when Scout detects a purchase event (rewards credited) with high context score (>70). Delivered within 2 minutes to capitalize on purchase mindset. |
| **Context Score** | Numerical score (0-100) computed by Scout based on purchase value, nearby store proximity, category affinity, weather, purchase frequency. Threshold >70 triggers offer generation. |
| **Marketer-Initiated Offer** | Offer created manually by marketer via Designer UI (AI Suggestions or Manual Entry mode). Requires explicit approval before Hub save. |
| **Fraud Detection** | Validation process using loyalty-fraud-detection skill to identify over-discounting, offer stacking, cannibalization, frequency abuse. Critical severity blocks approval. |
| **Partner Store** | Non-CTC retail location integrated with Triangle rewards (e.g., Tim Hortons, Westside). Purchases at partners trigger cross-sell opportunities to CTC stores. |
| **CTC Store** | Canadian Tire Corporation-owned retail location (Sport Chek, Mark's, Canadian Tire, Party City, L'Équipeur). |
| **Rate Limit** | Constraint on notification frequency: max 1 purchase-triggered offer per member per 6 hours, no duplicates within 24h. |
| **Quiet Hours** | 10pm-8am time window when notifications are suppressed and queued for 8am delivery. |
| **Segment** | Subset of loyalty members defined by criteria (high_value, lapsed_90_days, new_member, active). Used to target offers. |
| **Construct** | Offer mechanics: type (points_multiplier, percentage_discount, bonus_points), value (e.g., 5x, 20%, 500pts), validity period. |
| **Channels** | Delivery methods for offers: push notification (priority=1), email (priority=2), in-app (priority=3). |
| **KPIs** | Key performance indicators for offer: expected_redemption_rate, expected_uplift_pct, estimated_cost_per_redemption, roi_projection, target_reach. |
| **Risk Flags** | Boolean flags from fraud detection: over_discounting, cannibalization, frequency_abuse, offer_stacking. Severity: critical/medium/low. |
| **Claude API** | Anthropic's Claude AI API (model: claude-sonnet-4-6) used to generate structured OfferBrief JSON from prompts. |
| **JWT (JSON Web Token)** | Authentication token format used to secure Designer API endpoints. Contains user_id and role claims. Expires after 1 hour. |
| **RBAC (Role-Based Access Control)** | Authorization model restricting Designer access to users with role='marketing'. |
| **Zod** | TypeScript schema validation library used in frontend for input validation before API calls. |
| **Pydantic v2** | Python data validation library used in backend to validate request/response models and enforce OfferBrief schema. |
| **PII (Personally Identifiable Information)** | Names, emails, phone numbers, addresses. TriStar policy: log member_id only, scrub PII from all logs. |

---

## Quality Gate Results

| Gate | Status | Notes |
|------|--------|-------|
| **Gate 1: Mandatory Category Coverage** | ✅ PASS | All 6 mandatory categories addressed: Scope & Layers (Designer + Hub + Scout), Error States (2+ scenarios documented), Security (PII + validation + JWT), Performance (latency targets defined), Feature Flags (phased rollout), Backward Compatibility (N/A - new feature) |
| **Gate 2: P0 Requirements Defined** | ✅ PASS | 11 P0 requirements defined (REQ-001 through REQ-011), each with clear acceptance criteria, together forming complete MVP |
| **Gate 3: Non-Goals Defined** | ✅ PASS | 8 non-goals defined (NG-001 through NG-008), each with specific rationale explaining exclusion |
| **Gate 4: Edge Cases Defined** | ✅ PASS | 18 edge cases documented (EC-001 through EC-018) covering error handling, boundary values, race conditions, invalid inputs |
| **Gate 5: Acceptance Criteria for P0** | ✅ PASS | Every P0 requirement has 1+ acceptance criteria in Given/When/Then format (AC-001 through AC-050) |
| **Gate 6: Backward Compatibility Section** | ✅ PASS | Section present with verdict "Not applicable (new feature)", rationale provided, no breaking changes |
| **Gate 7: No Implementation Details** | ✅ PASS | Requirements describe behavior (WHAT), not implementation (HOW). Technology constraints separated into Constraints section. |
| **Gate 8: Assumptions Have Risk Levels** | ✅ PASS | All 13 assumptions have risk_if_wrong levels (high/medium/low) with mitigation notes for high-risk items |

**Overall Result:** ✅ ALL GATES PASSED - Ready for Architecture Phase

---

**End of Problem Specification**
