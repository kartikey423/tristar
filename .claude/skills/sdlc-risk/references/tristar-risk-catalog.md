# TriStar Risk Catalog

Domain-specific risks for the TriStar loyalty offer system. Use this catalog during risk assessment to ensure comprehensive coverage.

---

## 1. Loyalty Fraud Risks

### R-FRAUD-001: Over-Discounting
**Description:** Offers with discount > 30% of item value bypass fraud detection or are incorrectly approved.
**Likelihood:** 3 (Possible) | **Impact:** 4 (Major)
**Detection:** Monitor average discount percentage per approved offer. Alert if > 25%.
**Mitigation:** Fraud detection pipeline checks discount threshold before draft -> approved transition. Critical severity blocks approval.

### R-FRAUD-002: Frequency Abuse
**Description:** Member receives more than 3 offers per day due to race conditions or parallel processing.
**Likelihood:** 4 (Likely) | **Impact:** 3 (Moderate)
**Detection:** Monitor daily offer count per member. Alert if any member exceeds 3.
**Mitigation:** Atomic counter per member per day. Check before activation, not after.

### R-FRAUD-003: Offer Stacking
**Description:** Member accumulates more than 2 concurrent active offers, amplifying discounts.
**Likelihood:** 3 (Possible) | **Impact:** 4 (Major)
**Detection:** Monitor concurrent active offers per member. Alert if > 2.
**Mitigation:** Check active offer count before approved -> active transition.

### R-FRAUD-004: Cannibalization
**Description:** New offer competes with existing active offer for the same segment, splitting redemptions.
**Likelihood:** 3 (Possible) | **Impact:** 3 (Moderate)
**Detection:** Monitor segment overlap between active offers. Alert on full overlap.
**Mitigation:** Fraud detection checks for segment overlap during approval.

---

## 2. PII Exposure Risks

### R-PII-001: Member Names/Emails in Logs
**Description:** Structured logging accidentally includes member PII fields beyond member_id.
**Likelihood:** 3 (Possible) | **Impact:** 5 (Catastrophic)
**Detection:** Regular log audit. Grep for name/email patterns in log output.
**Mitigation:** Log sanitization middleware. Only member_id in log extra fields.

### R-PII-002: GPS Coordinates in Plaintext
**Description:** Raw latitude/longitude stored in logs or database, enabling member location tracking.
**Likelihood:** 3 (Possible) | **Impact:** 4 (Major)
**Detection:** Grep logs for coordinate patterns (decimal numbers near expected ranges).
**Mitigation:** Log only calculated distance, not raw coordinates. Hash or omit GPS data in persistence.

### R-PII-003: Context Signals Leaking Location
**Description:** Combination of time, weather, and GPS proximity data can triangulate member location even without raw GPS.
**Likelihood:** 2 (Unlikely) | **Impact:** 4 (Major)
**Detection:** Privacy review of stored context signal combinations.
**Mitigation:** Store only computed scores, not raw context signals. Apply data retention limits.

### R-PII-004: Claude API Prompt PII
**Description:** Member PII included in Claude API prompts, stored in Anthropic's logs.
**Likelihood:** 2 (Unlikely) | **Impact:** 4 (Major)
**Detection:** Prompt template review. Grep for member data field injection.
**Mitigation:** Prompts use only business objectives and segment criteria, never member-specific data.

---

## 3. Rate Limiting Failures

### R-RATE-001: Notification Spam
**Description:** Member receives more than 1 notification per hour due to race condition or limit bypass.
**Likelihood:** 3 (Possible) | **Impact:** 3 (Moderate)
**Detection:** Monitor notification frequency per member. Alert if > 1/hour.
**Mitigation:** Atomic rate limiter (Redis INCR with TTL). Check before send, not after.

### R-RATE-002: Duplicate Offers Within 24h
**Description:** Same offer sent to same member twice within 24-hour window.
**Likelihood:** 3 (Possible) | **Impact:** 2 (Minor)
**Detection:** Monitor (member_id, offer_id) pairs within 24h window.
**Mitigation:** Dedup key in Redis with 24h TTL. Check before delivery.

### R-RATE-003: Quiet Hours Violation
**Description:** Notifications delivered between 10pm and 8am member local time.
**Likelihood:** 3 (Possible) | **Impact:** 3 (Moderate)
**Detection:** Monitor notification timestamps against member timezone. Alert on violations.
**Mitigation:** Timezone-aware quiet hours check. Queue notifications for 8am delivery.

---

## 4. Context Signal Reliability Risks

### R-CTX-001: GPS Unavailability
**Description:** GPS signal unavailable (indoor, permissions denied, device limitation).
**Likelihood:** 4 (Likely) | **Impact:** 2 (Minor)
**Detection:** Monitor percentage of context evaluations with missing GPS.
**Mitigation:** Exclude GPS from weighted average. Redistribute weight to remaining signals.

### R-CTX-002: Weather API Downtime
**Description:** Weather API returns errors or is temporarily unavailable.
**Likelihood:** 3 (Possible) | **Impact:** 2 (Minor)
**Detection:** Monitor Weather API error rate. Alert if > 5% failure rate.
**Mitigation:** Cache last known weather data. Fall back to cached data during outage. Exclude from score if stale > 1 hour.

### R-CTX-003: Stale Behavior Data
**Description:** Member purchase behavior data is older than 7 days, leading to inaccurate scoring.
**Likelihood:** 3 (Possible) | **Impact:** 2 (Minor)
**Detection:** Monitor data age for behavior signals. Alert if average age > 7 days.
**Mitigation:** Discount behavior score proportionally to data age. Exclude if > 30 days.

### R-CTX-004: All Signals Unavailable
**Description:** All context signals are unavailable simultaneously (network outage, permissions).
**Likelihood:** 1 (Rare) | **Impact:** 3 (Moderate)
**Detection:** Monitor evaluations with 0 available signals.
**Mitigation:** Skip activation entirely. Queue for re-evaluation when signals restore.

---

## 5. Hub State Corruption Risks

### R-HUB-001: Race Condition on Status Transition
**Description:** Concurrent requests attempt to transition the same offer to different states simultaneously.
**Likelihood:** 4 (Likely) | **Impact:** 4 (Major)
**Detection:** Monitor for state transition conflicts. Alert on any rejected transitions.
**Mitigation:** Atomic state transitions (Redis WATCH/MULTI). Optimistic locking with retry.

### R-HUB-002: Orphaned Offers
**Description:** Offers stuck in approved state indefinitely because activation conditions are never met.
**Likelihood:** 3 (Possible) | **Impact:** 2 (Minor)
**Detection:** Monitor offers in approved state > 72 hours.
**Mitigation:** Automatic expiry after configurable window (e.g., 7 days in approved state).

### R-HUB-003: Redis Failover Data Loss
**Description:** Azure Redis Cache failover loses recent state changes.
**Likelihood:** 2 (Unlikely) | **Impact:** 4 (Major)
**Detection:** Monitor Redis failover events. Alert immediately.
**Mitigation:** Redis persistence (AOF or RDB). Audit log in Azure SQL for state reconstruction. Accept brief inconsistency during failover.

### R-HUB-004: In-Memory to Redis Behavior Mismatch
**Description:** Dev (in-memory) and Prod (Redis) stores behave differently, causing bugs found only in production.
**Likelihood:** 3 (Possible) | **Impact:** 3 (Moderate)
**Detection:** Integration tests run against both store backends.
**Mitigation:** Store abstraction interface. Tests parameterized for both backends.

---

## 6. Claude API Risks

### R-CLAUDE-001: Prompt Injection
**Description:** Malicious objective text manipulates Claude API prompt to generate harmful output.
**Likelihood:** 2 (Unlikely) | **Impact:** 4 (Major)
**Detection:** Monitor generated OfferBrief for anomalous content (extreme discounts, inappropriate text).
**Mitigation:** Input sanitization. Output validation via Pydantic schema. Reject OfferBrief that fails validation.

### R-CLAUDE-002: Response Caching Issues
**Description:** Cached Claude API response returns stale OfferBrief for different objective.
**Likelihood:** 2 (Unlikely) | **Impact:** 3 (Moderate)
**Detection:** Monitor cache hit/miss rates. Spot-check cached responses.
**Mitigation:** Cache key includes full objective text hash. 5 min TTL. Invalidation on schema change.

### R-CLAUDE-003: Rate Limiting
**Description:** Claude API rate limits hit during high-traffic periods.
**Likelihood:** 3 (Possible) | **Impact:** 3 (Moderate)
**Detection:** Monitor 429 responses from Claude API.
**Mitigation:** Exponential backoff (3 retries). Request queuing. Cache frequent objectives.

### R-CLAUDE-004: Cost Overrun
**Description:** Excessive Claude API usage drives costs beyond budget.
**Likelihood:** 2 (Unlikely) | **Impact:** 3 (Moderate)
**Detection:** Monitor daily API spend. Alert at 80% of budget threshold.
**Mitigation:** Request caching (5 min TTL). Rate limiting on generate endpoint. Budget alerts.

---

## 7. Azure Infrastructure Risks

### R-AZURE-001: Key Vault Access Failure
**Description:** Azure Key Vault unavailable, preventing secret retrieval (API keys, JWT secret).
**Likelihood:** 1 (Rare) | **Impact:** 5 (Catastrophic)
**Detection:** Monitor Key Vault access latency and error rate.
**Mitigation:** Secret caching at application startup. Graceful degradation with cached secrets.

### R-AZURE-002: Redis Cache Eviction
**Description:** Azure Redis Cache evicts Hub state data under memory pressure.
**Likelihood:** 2 (Unlikely) | **Impact:** 4 (Major)
**Detection:** Monitor Redis memory usage and eviction events.
**Mitigation:** Configure maxmemory-policy to noeviction for state data. Separate cache for transient data.

### R-AZURE-003: App Service Scaling
**Description:** Azure App Service cannot scale fast enough for traffic spikes.
**Likelihood:** 2 (Unlikely) | **Impact:** 3 (Moderate)
**Detection:** Monitor response latency and queue depth.
**Mitigation:** Auto-scale configuration. Minimum instance count. Load testing before launch.

### R-AZURE-004: SQL Database Connection Exhaustion
**Description:** Connection pool exhausted under high load, causing 500 errors.
**Likelihood:** 3 (Possible) | **Impact:** 3 (Moderate)
**Detection:** Monitor active connection count and pool wait time.
**Mitigation:** Connection pooling with proper limits (pool_size=10, max_overflow=20). Connection timeout configuration.
