# TriStar Project Instructions

**Last updated:** 2026-03-26
**Project:** Triangle Smart Targeting and Real-Time Activation
**Hackathon:** CTC True North 2026 (March 9-18)
**Tech Stack:** React 19, FastAPI, Claude API, Azure

Read this file before any task. Keep under 500 lines.

---

## Critical Guardrails

⛔ **NEVER**:
- Commit .env files, API keys, or secrets
- Expose mock data APIs beyond localhost
- Modify database directly without backup verification
- Skip OfferBrief schema validation before activation
- Deploy real-time triggers without isolation testing
- Modify files in `All Demo Files-20260325T171750Z-3-001/` (reference only)
- Use `git push --force` to main/master branches
- Run destructive commands (`rm -rf`, `git reset --hard`) without confirmation

✅ **ALWAYS**:
- Validate OfferBrief schema against `src/shared/types/offer-brief.ts`
- Test real-time triggers in isolation before integration
- Use TypeScript strict mode (no 'any' types)
- Write tests for all new features (>80% coverage)
- Run security scan before PR creation
- Use async/await for all FastAPI routes
- Log member_id only (no PII in logs)

---

## Definition of Done

### Frontend Components (React 19)
- [ ] TypeScript types exported from `src/shared/types`
- [ ] React 19 features used (`React.use()`, actions, `useOptimistic`)
- [ ] No class components (hooks only)
- [ ] Storybook story with 3+ variants
- [ ] Unit tests with React Testing Library (>80% coverage)
- [ ] Responsive design (mobile, tablet, desktop breakpoints)
- [ ] Accessibility: ARIA labels, keyboard navigation, semantic HTML
- [ ] CSS-in-JS or Tailwind (no inline styles)

### Backend APIs (FastAPI)
- [ ] FastAPI route with async/await
- [ ] Pydantic v2 models for request/response validation
- [ ] OpenAPI documentation auto-generated
- [ ] Input validation with proper error messages
- [ ] HTTP status codes: 200 (success), 400 (validation), 404 (not found), 500 (server error)
- [ ] Unit tests with pytest (>80% coverage)
- [ ] Integration tests with httpx TestClient
- [ ] Structured logging with loguru (no print statements)

### Features (End-to-End)
- [ ] All three layers integrated: Designer → Hub → Scout
- [ ] Mock data flows through complete pipeline
- [ ] Error states handled gracefully with user feedback
- [ ] Performance: <200ms p95 response time
- [ ] Security scan passes (no critical vulnerabilities)
- [ ] Code review by reviewer subagent completed
- [ ] Manual testing checklist completed
- [ ] Documentation updated (API docs, architecture diagrams)

---

## Tech Stack Standards

### React 19

**Data Fetching:**
```typescript
// Use React.use() for data fetching
const data = React.use(fetchPromise);

// Use Suspense boundaries
<Suspense fallback={<Loading />}>
  <DataComponent />
</Suspense>
```

**Mutations:**
```typescript
// Use actions for mutations
async function updateOffer(formData: FormData) {
  'use server';
  // mutation logic
}

// Use useOptimistic for optimistic updates
const [optimisticState, addOptimistic] = useOptimistic(state);
```

**Component Patterns:**
- Server Components by default (no 'use client' unless needed)
- Client Components only for interactivity (event handlers, hooks)
- CSS: Styled Components or Tailwind CSS
- State: React Context for global, useState for local
- Forms: React Server Actions with progressive enhancement

### FastAPI

**Route Structure:**
```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/api/designer", tags=["designer"])

class OfferBriefRequest(BaseModel):
    objective: str
    segment_criteria: list[str]

@router.post("/generate", response_model=OfferBriefResponse)
async def generate_offer_brief(
    request: OfferBriefRequest,
    service: DesignerService = Depends(get_designer_service)
) -> OfferBriefResponse:
    try:
        result = await service.generate(request)
        return result
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Patterns:**
- Async/await for all routes (non-blocking I/O)
- Pydantic v2 models for validation
- Dependency injection for services/database
- CORS: Allow localhost:3000 in dev, specific origins in prod
- Structured logging: `logger.info()` with context, no `print()`

### TypeScript

**Strict Configuration:**
```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUncheckedIndexedAccess": true
  }
}
```

**Type Patterns:**
- Shared types in `src/shared/types` (single source of truth)
- Use `unknown` instead of `any` when type is unclear
- Zod for runtime validation of API responses
- Export interfaces, not types (for better IDE support)

### Testing

**Frontend (Jest + React Testing Library):**
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

test('OfferBriefForm submits correctly', async () => {
  const onSubmit = jest.fn();
  render(<OfferBriefForm onSubmit={onSubmit} />);

  await userEvent.type(screen.getByLabelText('Objective'), 'Reactivate lapsed members');
  await userEvent.click(screen.getByRole('button', { name: 'Generate' }));

  await waitFor(() => expect(onSubmit).toHaveBeenCalled());
});
```

**Backend (Pytest + httpx):**
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_generate_offer_brief(client: AsyncClient):
    response = await client.post("/api/designer/generate", json={
        "objective": "Reactivate lapsed members",
        "segment_criteria": ["high_value", "lapsed_90_days"]
    })
    assert response.status_code == 200
    data = response.json()
    assert "offer_id" in data
    assert data["segment"]["name"] == "lapsed_high_value"
```

**E2E (Playwright):**
- Test critical paths: Designer → Hub → Scout
- Mock external APIs (Claude, Weather)
- Run in CI/CD pipeline before deploy

---

## Project-Specific Rules

### Layer 1: Designer (Marketer Copilot)

**OfferBrief Schema:**
- Location: `src/shared/types/offer-brief.ts`
- Must include: offer_id, objective, segment, construct, channels, kpis, risk_flags
- Validate with Zod before sending to Hub
- Risk flags: over_discounting, cannibalization, frequency_abuse, offer_stacking

**Claude API Integration:**
- Model: claude-sonnet-4-6
- Prompt: Business objective → Structured OfferBrief
- Retry logic: 3 attempts with exponential backoff
- Cache responses for identical objectives (5 min TTL)

**Fraud Detection:**
- Run `loyalty-fraud-detection` skill before approval
- Block activation if severity === 'critical'
- Log all risk flags for audit trail

### Layer 2: Scout (Real-Time Activation Engine)

**Context Signals:**
- Location: GPS lat/lon, proximity to store (within 2km)
- Time: hour, day_of_week, is_weekend, seasonal_pattern
- Weather: temperature, conditions (sunny/rainy/cold/hot)
- Behavior: last_purchase_category, days_since_visit, recent_categories

**Activation Rules:**
- Use `semantic-context-matching` skill for scoring
- Threshold: score > 60 to activate
- Rate limiting: 1 notification per member per hour (enforce in Hub)
- Deduplication: No duplicate offers within 24h

**Notification Delivery:**
- Channel priority: Push > SMS > Email
- Personalization: Use member name, relevant store name
- Timing: Respect quiet hours (no notifications 10pm-8am)
- Fallback: Queue for later if delivery fails

### The Hub (Shared Context State)

**State Management:**
- Dev: In-memory dict (restart clears state)
- Prod: Redis with persistence enabled
- Offer status: draft → approved → active → expired
- Atomic updates (no race conditions)

**Status Transitions:**
```
draft → approved (marketer approval + fraud check passes)
approved → active (activation rules met)
active → expired (time-based expiry OR redemption completed)
```

**Audit Trail:**
- Log all status changes with timestamp, user_id, reason
- Store in `audit_log` table (append-only)
- Queryable by offer_id, member_id, date_range

---

## Iceberg Technique (Context Management)

### Load ONLY What's Needed

**Before Reading Files:**
1. Use `Grep` to search for keywords
2. Use `Glob` to find files by pattern
3. Read only relevant files (max 3-5 per task)
4. Summarize large files (>200 lines) before reading fully

**Context Budget:**
- Total: 200k tokens
- System prompt: 20% (~40k tokens)
- Codebase: 30% (~60k tokens)
- Task context: 50% (~100k tokens)

**Compression Strategies:**
- Use MEMORY.md for cross-session context
- Summarize verbose logs before appending
- Reference file:line instead of copying code blocks
- Link to docs instead of duplicating content

### File Includes (Auto-Load)

These files are loaded at session start:
- `.claude/CLAUDE.md` (this file)
- `.claude/memory/MEMORY.md` (learnings)
- `docs/ARCHITECTURE.md` (system design)
- `src/shared/types/offer-brief.ts` (core schema)

**Other files:** Load on-demand via Grep/Glob/Read tools.

---

## Cross-File References

### Frontend
- Components: `src/frontend/components/`
- Hooks: `src/frontend/hooks/`
- Services: `src/frontend/services/` (API clients)
- Types: `src/shared/types/` (shared with backend)

### Backend
- API routes: `src/backend/api/`
- Models: `src/backend/models/` (Pydantic)
- Services: `src/backend/services/` (business logic)
- Utils: `src/backend/utils/` (helpers)

### Shared
- Types: `src/shared/types/` (TypeScript interfaces + Python dataclasses)
- Mock data: `src/shared/mock-data/` (synthetic member profiles)

### Tests
- Mirror src/ structure: `tests/unit/`, `tests/integration/`, `tests/e2e/`
- Test file naming: `test_<module>.py` (backend), `<Component>.test.tsx` (frontend)

---

## Naming Conventions

### Files
- React components: `PascalCase.tsx` (e.g., `OfferBriefForm.tsx`)
- Python modules: `snake_case.py` (e.g., `offer_generator.py`)
- Test files: `test_*.py` or `*.test.tsx`
- Config files: `kebab-case.json` (e.g., `tsconfig.json`)

### Code
- TypeScript: `camelCase` (variables, functions), `PascalCase` (types, components)
- Python: `snake_case` (variables, functions), `PascalCase` (classes)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_DISCOUNT_PCT`)
- Environment variables: `UPPER_SNAKE_CASE` (e.g., `CLAUDE_API_KEY`)

### URLs
- API routes: `/api/<layer>/<action>` (e.g., `/api/designer/generate`)
- Kebab-case for multi-word: `/api/scout/context-signals`
- Version prefix: `/api/v1/...` (when versioning needed)

---

## Error Handling

### Frontend
- Use Error Boundaries for React component errors
- Show user-friendly messages (not stack traces)
- Toast notifications for transient errors
- Modal dialogs for critical errors requiring action

### Backend
- Catch exceptions at route level
- Return structured error responses:
  ```json
  {
    "error": "ValidationError",
    "message": "Invalid OfferBrief schema",
    "details": { "field": "segment.criteria", "reason": "must be non-empty array" }
  }
  ```
- Log full stack trace server-side (not to client)
- HTTP status codes: 400 (client error), 500 (server error), 503 (service unavailable)

---

## Security Guidelines

### Input Validation
- Validate all user inputs with Pydantic (backend) and Zod (frontend)
- Sanitize before logging (strip PII)
- Reject suspicious patterns (SQL injection, XSS attempts)

### Secrets Management
- Store in Azure Key Vault (prod) or .env (dev, gitignored)
- Access via environment variables only
- Never log secrets (mask in logs)
- Rotate API keys quarterly

### API Security
- CORS: Whitelist specific origins (no `*` in prod)
- Rate limiting: 100 requests/minute per IP
- Authentication: JWT tokens with 1h expiry
- HTTPS only in production

### OWASP Top 10
- Injection: Use parameterized queries, validate inputs
- Broken authentication: Enforce strong passwords, MFA
- Sensitive data exposure: Encrypt at rest and in transit
- XML external entities: Disable XML parsing if not needed
- Broken access control: Enforce least privilege
- Security misconfiguration: Follow Azure security baseline
- XSS: Sanitize HTML, use Content Security Policy
- Insecure deserialization: Validate before deserializing
- Known vulnerabilities: Keep dependencies updated
- Insufficient logging: Log security events (auth failures, privilege escalation attempts)

---

## Performance Targets

### Response Times
- API endpoints: <200ms p95
- Frontend page load: <2s (First Contentful Paint)
- Real-time activation: <500ms (signal received → notification sent)

### Optimization Strategies
- Cache Claude API responses (5 min TTL)
- Use Redis for Hub state (in-memory lookup)
- Index frequently queried fields (member_id, offer_id)
- Paginate large result sets (max 100 items per page)
- Use CDN for static assets (fonts, images)

---

## Documentation

### API Documentation
- OpenAPI spec auto-generated from FastAPI routes
- Hosted at `/docs` (Swagger UI) and `/redoc` (ReDoc)
- Include examples for each endpoint

### Code Comments
- JSDoc for exported functions/types (TypeScript)
- Docstrings for public methods (Python)
- Explain "why" not "what" (code should be self-explanatory)

### Architecture Diagrams
- Location: `docs/ARCHITECTURE.md`
- Keep Mermaid diagrams up-to-date with code changes
- Review quarterly for accuracy

---

## Git Workflow

### Branching
- Main branch: `main` (protected, requires PR)
- Feature branches: `feature/<description>` (e.g., `feature/designer-ui`)
- Bugfix branches: `bugfix/<issue>` (e.g., `bugfix/context-scoring`)

### Commits
- Conventional Commits format: `<type>: <description>`
- Types: feat, fix, docs, style, refactor, test, chore
- Examples:
  - `feat: add OfferBrief validation logic`
  - `fix: correct context matching scoring algorithm`
  - `docs: update ARCHITECTURE.md with Hub state diagram`

### Pull Requests
- Title: Same as commit message (if single commit)
- Description: Explain what changed and why
- Checklist: Tests pass, security scan passes, code review completed
- Reviewers: At least one human or subagent reviewer

---

## Environment Variables

### Required (Dev)
```bash
CLAUDE_API_KEY=sk-ant-...
WEATHER_API_KEY=...
DATABASE_URL=sqlite:///tristar.db
REDIS_URL=redis://localhost:6379
LOG_LEVEL=DEBUG
ENVIRONMENT=development
```

### Required (Prod)
```bash
CLAUDE_API_KEY=<from Azure Key Vault>
WEATHER_API_KEY=<from Azure Key Vault>
DATABASE_URL=<Azure SQL connection string>
REDIS_URL=<Azure Redis connection string>
LOG_LEVEL=INFO
ENVIRONMENT=production
CORS_ORIGINS=https://tristar.azurewebsites.net
```

---

## Troubleshooting

### Common Issues

**Claude API rate limits:**
- Solution: Implement exponential backoff, cache responses

**Context matching returns no offers:**
- Check: Are there approved offers in Hub? (status === 'active')
- Check: Is score threshold too high? (lower from 60 to 40 for testing)

**Frontend/backend type mismatch:**
- Solution: Regenerate shared types from `src/shared/types/offer-brief.ts`
- Validate with Zod at runtime (catch drift early)

**Memory leaks in long-running tasks:**
- Solution: Clear large objects after use, use `weak` references where possible

---

## Scoped Rules

For detailed guidelines on specific topics, see `.claude/rules/`:
- `code-style.md` - Naming conventions, formatting, linting
- `testing.md` - Test structure, coverage, mocking
- `security.md` - Input validation, secrets, OWASP
- `react-19-standards.md` - Component patterns, hooks
- `fastapi-standards.md` - Route structure, async patterns

---

**Word count:** ~2400 words (~480 lines) ✅ Under 500 line limit