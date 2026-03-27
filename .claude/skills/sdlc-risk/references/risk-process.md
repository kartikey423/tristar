# Risk Assessment Process

10-step risk assessment process adapted for the TriStar 3-layer loyalty offer system.

---

## Step 1: Load All Artifacts

Read every available artifact for the feature:
- problem_spec.md (requirements, edge cases, assumptions)
- design_spec.md (architecture, ADRs, data flows)
- implementation_plan.md (file list, wave plan, known risks)
- code_review.md (code quality findings)
- verification_report.md (test results, coverage, domain checks)

Also scan the actual implementation code for the feature.

---

## Step 2: Catalog Technical Risks

Systematically scan for technical risks in each layer:

**Frontend (React 19 + Next.js 15):**
- Unhandled promise rejections in data fetching
- Missing error boundaries around Suspense components
- Client-side state inconsistency with server state
- Bundle size impact (new dependencies)
- SSR/hydration mismatches

**Backend (FastAPI + Pydantic v2):**
- Unhandled exceptions in route handlers (500 errors)
- Missing input validation (Pydantic models incomplete)
- Blocking sync code in async routes
- Database connection leaks
- Memory leaks from unclosed resources

**Shared:**
- Zod/Pydantic schema mismatch
- Type misalignment between frontend and backend
- Breaking API contract changes

---

## Step 3: Catalog Domain Risks

Reference `references/tristar-risk-catalog.md` and check each risk category:

- Loyalty fraud vectors (over-discounting, stacking, frequency abuse)
- PII exposure (logs, API prompts, error messages)
- Rate limiting failures (notification spam, quiet hours violations)
- Context signal reliability (GPS, weather, behavior data)
- Hub state corruption (race conditions, orphaned offers)
- Claude API risks (prompt injection, cost, availability)

---

## Step 4: Catalog Operational Risks

Assess deployment and runtime risks:

**Azure Infrastructure:**
- App Service scaling under load
- Redis Cache eviction policy impact
- Key Vault access latency
- CDN cache invalidation timing

**Monitoring:**
- Are failure conditions detectable?
- Are alerts configured for critical paths?
- Is the audit trail complete for Hub state changes?

**Rollback:**
- Can the feature be disabled via feature flag?
- Is database migration reversible?
- What is the blast radius of a rollback?

---

## Step 5: Score Each Risk

For every identified risk, assign:

**Likelihood (1-5):**
| Score | Description | TriStar Example |
|-------|-------------|-----------------|
| 1 | Rare | Azure Key Vault total outage |
| 2 | Unlikely | Claude API response > 30s |
| 3 | Possible | Weather API returns stale data |
| 4 | Likely | GPS unavailable for indoor members |
| 5 | Almost Certain | Concurrent state transitions attempted |

**Impact (1-5):**
| Score | Description | TriStar Example |
|-------|-------------|-----------------|
| 1 | Negligible | Log message formatting wrong |
| 2 | Minor | Single member gets wrong offer score |
| 3 | Moderate | Offer activated with stale context |
| 4 | Major | PII exposed in logs for multiple members |
| 5 | Catastrophic | Hub state corrupted, all offers invalid |

**Risk Score:** Likelihood x Impact

**Severity Classification:**
- Low: 1-6
- Medium: 7-12
- High: 13-18
- Critical: 19-25

---

## Step 6: Assess Mitigations

For each risk, evaluate existing mitigations:

- **Present and adequate**: Risk is mitigated, residual risk is low
- **Present but insufficient**: Mitigation exists but gaps remain
- **Missing**: No mitigation in place

Document what additional mitigations are needed.

---

## Step 7: Identify Risk Clusters

Find chains of risks that could cascade:

**Example TriStar Cascade:**
```
Weather API down (R-003)
  -> Context score incomplete (R-007)
    -> Activation decision based on partial data (R-011)
      -> Wrong offer activated for member (R-015)
        -> Member receives irrelevant notification (R-019)
```

Risk clusters are more dangerous than individual risks because failure compounds.

---

## Step 8: Calculate Overall Risk Score

Aggregate scoring:
- Sum all individual risk scores
- Weight Critical risks at 3x
- Weight High risks at 2x
- Weight Medium risks at 1x
- Weight Low risks at 0.5x

**Overall Score = (Critical * 3) + (High * 2) + (Medium * 1) + (Low * 0.5)**

---

## Step 9: Make Ship Recommendation

| Recommendation | Criteria | Action |
|---------------|----------|--------|
| **ship** | 0 Critical, 0 unmitigated High, overall < 50 | Deploy with standard monitoring |
| **ship_with_monitoring** | 0 Critical, <=2 High (mitigated), overall < 100 | Deploy with enhanced monitoring and alerts |
| **fix_first** | 1+ Critical OR 3+ unmitigated High | Fix specified risks, re-assess |
| **redesign** | 3+ Critical OR fundamental flaw | Major architectural changes needed |

---

## Step 10: Write Risk Assessment

Compile all findings into `docs/artifacts/<feature>/risk_assessment.md` with:
- Executive summary (1 paragraph)
- Risk catalog (table format, sorted by severity)
- Risk clusters (cascade diagrams)
- Ship recommendation with detailed rationale
- Monitoring plan (if ship_with_monitoring)
- Fix plan (if fix_first)
- Alternative approach (if redesign)
