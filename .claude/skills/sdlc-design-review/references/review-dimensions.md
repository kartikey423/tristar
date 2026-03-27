# Review Dimensions - Detailed Criteria

Comprehensive criteria and probing questions for each review dimension, tailored to the TriStar 3-layer loyalty offer system.

---

## Dimension A: Codebase Validation

**Purpose:** Verify the design is grounded in reality, not an idealized version of the codebase.

### Criteria

1. **File Path Accuracy**
   - Every referenced file path must be valid within the project structure
   - `src/frontend/` for React 19 + Next.js 15 components
   - `src/backend/` for FastAPI routes, services, models
   - `src/shared/types/` for shared TypeScript types
   - `tests/` for test files (unit/, integration/, e2e/)

2. **React 19 Pattern Compliance**
   - Server Components are default (no 'use client' unless interactive)
   - Data fetching uses React.use() with Suspense, not useEffect
   - Forms use Server Actions, not manual fetch + useState
   - Optimistic updates use useOptimistic where appropriate
   - No class components

3. **FastAPI Pattern Compliance**
   - All routes are async (async def, not def)
   - Dependency injection via Depends()
   - Pydantic v2 models (not v1 - check for model_validator vs @validator)
   - Structured logging with loguru (not print or stdlib logging)
   - Custom exception handlers for domain errors

4. **Existing Component Reuse**
   - Design does not reinvent components that already exist
   - Existing interfaces are correctly referenced
   - Extension points are used rather than duplicating logic

### TriStar Probing Questions
- Does the design assume OfferBrief fields that do not exist in the current schema?
- Does the design assume Hub state transitions that are not currently valid?
- Does the design reference Scout context signals that are not currently processed?
- Are referenced API endpoints consistent with existing route prefix conventions (/api/designer/, /api/hub/, /api/scout/)?

---

## Dimension B: Architectural Review

**Purpose:** Verify the design maintains TriStar's architectural integrity and patterns.

### Criteria

1. **3-Layer Separation**
   - Designer (Layer 1) components only in src/frontend/ and src/backend/api/designer.py
   - Hub (Layer 2) components only in src/backend/api/hub.py and hub-related services
   - Scout (Layer 3) components only in src/backend/api/scout.py and scout-related services
   - No cross-layer imports that bypass Hub

2. **Communication Patterns**
   - Designer -> Hub: offer creation, approval requests
   - Hub -> Scout: offer availability queries, state updates
   - NO Designer -> Scout direct communication
   - If a design requires Designer->Scout, it must be refactored through Hub

3. **Hub State Machine Validity**
   - All proposed state transitions are valid (per Pattern 3 in tristar-patterns.md)
   - No transitions from terminal states (expired -> anything)
   - No reverse transitions (active -> approved, approved -> draft)
   - Concurrency handling addressed for state changes

4. **ADR Quality**
   - At least 2 genuine alternatives per ADR (not strawmen)
   - Pros and cons are honest (not rigged to favor the chosen option)
   - Trade-offs are explicitly documented
   - Decision rationale is clear and defensible

5. **Component Design**
   - Single responsibility per component
   - No component with more than 5 dependencies
   - No circular dependency chains
   - Clear separation of concerns (routes vs services vs models)

### TriStar Probing Questions
- Is fraud detection running at the correct point in the flow (before approval, not after)?
- Is rate limiting enforced at the Scout layer (not delegated to the client)?
- Does the design ensure Hub is the single source of truth for offer state?
- Could a race condition corrupt Hub state during concurrent state transitions?

---

## Dimension C: Assumption Challenges

**Purpose:** Stress-test every assumption in the design to find hidden risks.

### Criteria

1. **External Dependency Assumptions**
   - Claude API: What if response time is 5s? What if rate limited? What if model changes?
   - Weather API: What if downtime is 30 minutes? What if data is stale?
   - Redis: What if Azure Redis Cache has failover? What if data is evicted?
   - Member timezone: Is timezone data accurate for quiet hours?

2. **Data Assumptions**
   - Segment data freshness: How old can it be before it affects targeting?
   - Behavior data: What if member has no purchase history?
   - GPS accuracy: What if precision is 500m instead of 10m?
   - Context signal completeness: What if only 1 of 4 signals is available?

3. **Scale Assumptions**
   - How many concurrent offers can Hub manage?
   - How many context evaluations per second can Scout handle?
   - What is the maximum number of active members being scored simultaneously?

4. **Business Rule Assumptions**
   - Is the 30% discount threshold always correct? (Different categories?)
   - Is 1 notification/hour appropriate for all member segments?
   - Are quiet hours always 10pm-8am? (Regional variation?)

### Challenge Template
For each assumption found:
```
ASSUMPTION: <what is assumed>
EVIDENCE: <what evidence supports this> or NONE
RISK_IF_WRONG: high | medium | low
MITIGATION: <what happens if wrong>
```

---

## Dimension D: Complexity Concerns

**Purpose:** Identify unnecessary complexity that increases risk and maintenance burden.

### Criteria

1. **Essential vs Accidental Complexity**
   - Essential: complexity required by the problem domain (offer lifecycle, fraud detection)
   - Accidental: complexity from poor design choices (over-abstraction, premature optimization)
   - Flag any accidental complexity

2. **Component Count**
   - Is the number of new components proportional to the feature scope?
   - Rule of thumb: a simple feature should add 3-5 components, not 15-20

3. **Abstraction Layers**
   - Is every abstraction layer earning its keep?
   - Would removing a layer simplify without losing needed flexibility?

4. **Pattern Overhead**
   - Are design patterns used because they solve a real problem, or because they are fashionable?
   - Does the feature actually need the proposed level of indirection?

### TriStar Probing Questions
- Could this feature be implemented by extending existing components instead of creating new ones?
- Is the proposed caching strategy worth its complexity for the expected request volume?
- Does this feature need its own state management, or can it use Hub's existing state?
- Is the proposed error handling proportional to the actual risk?

---

## Dimension E: Alternative Approaches

**Purpose:** Ensure major decisions were made after genuine consideration of alternatives.

### Criteria

1. **ADR Alternative Quality**
   - Each alternative must be genuinely viable (not a strawman)
   - Each alternative must have real pros (not just cons)
   - The chosen approach should not be obviously the only reasonable choice

2. **Simplicity Consideration**
   - Was the simplest approach that meets P0 requirements considered?
   - If a simpler approach was rejected, is the rationale convincing?

3. **Build vs Reuse**
   - Were existing components/libraries considered before proposing new ones?
   - Is the "build" decision justified over using what already exists?

4. **Technology Choices**
   - Are technology choices consistent with the established stack?
   - If a new technology is proposed, is the ADR convincing?

### TriStar Probing Questions
- Could the in-memory Hub store be extended instead of adding Redis-specific logic?
- Could this feature use existing Scout context signals instead of adding new ones?
- Was a simpler scoring algorithm considered for context matching?
- Could this be implemented as a configuration change rather than a code change?

---

## Dimension F: Missing Considerations

**Purpose:** Find gaps - things the design should address but does not.

### TriStar Missing Items Checklist

1. **Error Handling**
   - [ ] Claude API failure handling (retry with backoff)
   - [ ] Weather API failure handling (graceful degradation)
   - [ ] Redis failure handling (fallback behavior)
   - [ ] Network timeout handling
   - [ ] Invalid input handling (both frontend and backend)

2. **Observability**
   - [ ] Structured logging with loguru (JSON format)
   - [ ] Request/response logging middleware
   - [ ] Business event logging (offer created, approved, activated)
   - [ ] Performance metrics (latency, throughput)
   - [ ] Audit trail for Hub state changes

3. **Rate Limiting**
   - [ ] 1 notification per member per hour
   - [ ] No duplicate offers within 24 hours
   - [ ] Quiet hours enforcement (10pm-8am)
   - [ ] API rate limiting for endpoints

4. **Fraud Detection**
   - [ ] Over-discounting check (>30%)
   - [ ] Cannibalization check
   - [ ] Frequency abuse check (>3/day)
   - [ ] Offer stacking check (>2 concurrent)
   - [ ] Critical severity blocking behavior

5. **PII Protection**
   - [ ] Only member_id in logs
   - [ ] No GPS coordinates in plaintext logs
   - [ ] No member names/emails/addresses anywhere
   - [ ] Claude API prompts sanitized of PII

6. **Backward Compatibility**
   - [ ] Existing Hub state data preserved
   - [ ] Existing API contracts maintained
   - [ ] Existing OfferBrief data valid after changes

7. **Feature Flags**
   - [ ] Rollout strategy defined
   - [ ] Rollback plan documented
   - [ ] A/B testing capability (if needed)

8. **Testing**
   - [ ] Coverage target set (>80%)
   - [ ] Unit test strategy per layer
   - [ ] Integration test scenarios
   - [ ] E2E test scenarios for critical paths
   - [ ] Mock strategy for external dependencies

### Probing Questions
- What happens at 10:00 PM when quiet hours start and there are queued notifications?
- What happens when a member's segment changes while an offer is active?
- How does the system recover from a Redis failover in production?
- What metrics would indicate this feature is working correctly in production?
- How would an operator diagnose a problem with this feature using only logs?
