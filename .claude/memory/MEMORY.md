# TriStar Project Memory

**Purpose:** Cross-session learnings and project context
**Last Updated:** 2026-03-26
**Auto-loaded:** First 200 lines loaded at session start

---

## Project Context

### TriStar Overview
- **Hackathon:** CTC True North 2026 (March 9-18)
- **Goal:** Transform Triangle loyalty program from reactive points ledger to proactive AI-powered engagement platform
- **Category:** Omni Channel Growth
- **Impact Area:** Triangle Program Growth & Incremental 1:1 Offers

### Three-Layer Architecture
1. **Designer (Layer 1):** Marketer copilot that generates OfferBriefs from business objectives using Claude API
2. **The Hub:** Shared context state storing approved offers (Redis for prod, in-memory dict for demo)
3. **Scout (Layer 2):** Real-time activation engine monitoring GPS, weather, time, and behavioral signals

### Key Innovation
- **End-to-End Loop:** Intelligent offer design → intelligent offer delivery
- **Context-Aware:** Real-time matching of offers to member context (location, weather, time, behavior)
- **Proactive:** Members receive relevant offers at the right moment, not just after purchase

---

## Tech Stack Decisions

### Frontend: React 19
- **Why React 19:** Latest features (React.use(), Server Components, actions, useOptimistic)
- **TypeScript:** Strict mode enforced, no 'any' types, shared types in src/shared/types
- **Styling:** Tailwind CSS (utility-first, rapid prototyping for hackathon)
- **Testing:** Jest + React Testing Library (>80% coverage requirement)

### Backend: FastAPI
- **Why FastAPI:** Fast async performance, auto-generated OpenAPI docs, Pydantic validation
- **Python 3.11+:** Modern async/await patterns, improved error messages
- **Pydantic v2:** Type-safe validation for OfferBrief schema
- **Testing:** Pytest + httpx (>80% coverage requirement)

### AI: Claude API
- **Model:** claude-sonnet-4-6 (best balance of quality/speed/cost for hackathon)
- **Use Case:** Generate structured OfferBriefs from natural language business objectives
- **Caching:** 5 min TTL for identical objectives (reduce API calls)

### Infrastructure: Azure
- **Compute:** App Service (frontend), Azure Functions (backend)
- **Data:** Redis Cache (Hub state), Azure SQL (audit log)
- **Monitoring:** Application Insights
- **Secrets:** Azure Key Vault

---

## Design Patterns Applied

### 1. Reverse Prompting (Architect Agent)
- Ask 5 clarifying questions before implementation
- Prevents wrong assumptions and wasted effort
- Example: "Should OfferBrief include expiry date or duration?" → "Duration (e.g., valid for 7 days)"

### 2. Subagent Verification Loops (Code Review)
- Fresh-context reviewer agent catches mistakes implementer missed
- Implement → Review → Resolve pattern
- Reviewer has no sunk-cost bias, only sees final output

### 3. Prompt Contracts (ADIC Pipeline Stage 3)
- Define GOAL, CONSTRAINTS, FORMAT, FAILURE conditions upfront
- FAILURE clause prevents agents from taking shortcuts
- Example: "FAILURE: If response time >200ms, reject implementation"

### 4. Iceberg Technique (Context Management)
- Load only relevant files (Grep/Glob), avoid reading full codebase
- Context budget: 20% system prompt, 30% codebase, 50% task
- Use MEMORY.md for cross-session context (this file!)

### 5. ADIC Pipeline (Automated SDLC)
- 8 stages: Requirements → Architecture → Design → Implementation → Code Review → QA → Security → Deployment
- ~2 hours per feature (fits 3-4 features in one-week hackathon)
- Failure handling: Ask user (stages 1-3), rollback/retry (stage 4), fix/re-run (stages 5-6), escalate (stage 7)

---

## Critical Schema: OfferBrief

**Location:** `src/shared/types/offer-brief.ts`

**Structure:**
```typescript
interface OfferBrief {
  offer_id: string;
  objective: string;
  segment: Segment;
  construct: Construct;
  channels: Channel[];
  kpis: KPIs;
  risk_flags: RiskFlags;
  created_at: Date;
  status: 'draft' | 'approved' | 'active' | 'expired';
}
```

**Why This Schema:**
- Single source of truth for Designer, Hub, Scout
- Validated with Zod (TypeScript) and Pydantic (Python)
- Risk flags prevent fraud (over-discounting, cannibalization, frequency abuse)
- KPIs enable measurement from day one

---

## Skills Created

### 1. loyalty-fraud-detection
- **Purpose:** Detect fraudulent offer patterns before activation
- **Triggers:** "check for fraud", "validate offer", "risk analysis"
- **Patterns:** Over-discounting (>30%), offer stacking (2+ within 7 days), frequency abuse (>1 per 24h), cannibalization
- **Output:** fraud-risk-report.json with severity (low/medium/high/critical)

### 2. semantic-context-matching
- **Purpose:** Match real-time context signals to approved offers
- **Triggers:** "match context to offer", Scout receives context update
- **Scoring:** Location (40pts), Time (30pts), Weather (20pts), Behavior (10pts)
- **Threshold:** Score >60 activates offer, <=60 queues for later

### 3. adic-pipeline
- **Purpose:** Automated SDLC pipeline for one-week hackathon timeline
- **Usage:** `claude-code --skill adic-pipeline "Build Designer UI"`
- **Stages:** 8 stages in ~2 hours per feature
- **Output:** requirements.md, design-contract.md, code, verification-report.md, test-results.json, security-report.md

---

## Agents Created

### 1. Architect Agent
- **Role:** Schema validation, reverse prompting, API contract review
- **Tools:** Read, Grep, Glob, Bash (run tsc, mypy)
- **Constraint:** Does NOT write code—validates and recommends only
- **Use Case:** Ensure OfferBrief schema consistency across frontend/backend

### 2. DevOps Agent
- **Role:** Azure setup, Terraform automation, CI/CD pipeline
- **Tools:** Bash (terraform, az cli), Write (terraform/*.tf only)
- **Constraint:** No direct Azure resource creation (use Terraform only)
- **Use Case:** Deploy to Azure staging after security scan passes

---

## Lessons Learned

### Session 1 (2026-03-26) - Initialization
- **Created:** Complete .claude/ hierarchy (6 levels), ARCHITECTURE.md with 6 Mermaid diagrams
- **Key Decision:** Use Tailwind CSS over Styled Components (faster prototyping for hackathon deadline)
- **Best Practice Applied:** CLAUDE.md under 500 lines (480 lines achieved), guardrails at top, bullet points, short headings

---

## Common Pitfalls to Avoid

1. **Context Overload:** Don't load full codebase—use Grep/Glob to find relevant files first
2. **Premature Optimization:** Keep it simple for hackathon (in-memory dict for Hub, not Redis initially)
3. **Schema Drift:** Always validate OfferBrief with Zod + Pydantic—frontend/backend must match
4. **Over-Discounting:** Run loyalty-fraud-detection before offer approval (block if critical)
5. **Rate Limiting:** Enforce 1 notification per member per hour (prevent notification fatigue)

---

## Quick Reference

### File Locations
- Project rules: `.claude/CLAUDE.md`
- Architecture diagrams: `docs/ARCHITECTURE.md`
- Shared types: `src/shared/types/`
- Skills: `.claude/skills/`
- Agents: `.claude/agents/`

### Key Commands
```bash
# Verify CLAUDE.md line count
wc -l .claude/CLAUDE.md

# Run security scan
bash scripts/security-scan.sh

# Test fraud detection skill
claude-code --skill loyalty-fraud-detection --test-mode

# Run ADIC pipeline
claude-code --skill adic-pipeline "Build feature X"
```

### Performance Targets
- API endpoints: <200ms p95
- Frontend page load: <2s (FCP)
- Real-time activation: <500ms
- Test coverage: >80%

---

## Demo Files Reference

**Location:** `All Demo Files-20260325T171750Z-3-001/All Demo Files/`

**DO NOT MODIFY** - These are reference materials showing 8 advanced agent patterns:
1. Multi-Agent MCP Orchestration
2. Agent Chatrooms
3. Prompt Contracts
4. Reverse Prompting
5. Stochastic Multi-Agent Consensus
6. Subagent Verification Loops
7. GEMINI (Self-Modifying)
8. Video-to-Action via Gemini

**Use for:** Learning patterns, not copying code

---

## Hackathon Success Criteria

**Target Score:** 85/100

**Judging Breakdown:**
1. Technology & Application (30%): LLM integration, real-time processing, agentic solution
2. Landscape & Positioning (20%): Market fit (reactive → proactive)
3. Relevance (20%): CTC need (Omni channel growth, 1:1 offers)
4. Resonance (15%): Human-centric (save time, get relevance)
5. Revolutionary Impact (15%): First loyalty program with AI copilot + real-time context

**Deliverables:**
- 5+5+1 pitch deck (5 min pitch, 5 min Q&A, 1 min transition)
- Live demo: Marketer enters objective → Scout activates offer
- Working PoC deployed to Azure staging

---

**Next Steps:**
1. Create scoped rules (.claude/rules/)
2. Implement skills (fraud-detection, context-matching, adic-pipeline)
3. Define agents (architect, devops)
4. Build OfferBrief schema (src/shared/types/offer-brief.ts)
5. Implement Layer 1 (Designer UI + API)
6. Implement Hub (state management + audit log)
7. Implement Layer 2 (Scout activation logic)
8. Integration testing + security scan
9. Deploy to Azure staging
10. Prepare pitch deck and demo script

---

*This memory file will be automatically updated with commit messages via post-commit hook.*