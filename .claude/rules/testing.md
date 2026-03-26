# Testing Rules

**Purpose:** Test structure, coverage requirements, and mocking patterns for TriStar project
**Scope:** Unit, integration, and E2E tests
**Enforcement:** CI/CD pipeline blocks PRs if coverage <80%

---

## Coverage Requirements

| Test Type | Min Coverage | Files Excluded |
|-----------|--------------|----------------|
| Unit | 80% | Config files, types, constants |
| Integration | 70% | External API calls (mocked) |
| E2E | Critical paths only | Non-critical flows |

**Critical Paths:**
1. Designer: Objective input → OfferBrief generation → Fraud check → Hub save
2. Scout: Context signal received → Semantic matching → Notification sent
3. Hub: Offer status transitions (draft → approved → active → expired)

---

## Test Structure

### Frontend (Jest + React Testing Library)

**File Naming:** `<ComponentName>.test.tsx`

**Structure:**
```typescript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OfferBriefForm } from './OfferBriefForm';

describe('OfferBriefForm', () => {
  describe('Form Validation', () => {
    test('shows error when objective is empty', async () => {
      render(<OfferBriefForm />);
      await userEvent.click(screen.getByRole('button', { name: 'Generate' }));
      expect(screen.getByText('Objective is required')).toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    test('calls onSubmit with correct data', async () => {
      const onSubmit = jest.fn();
      render(<OfferBriefForm onSubmit={onSubmit} />);

      await userEvent.type(screen.getByLabelText('Objective'), 'Reactivate lapsed members');
      await userEvent.click(screen.getByRole('button', { name: 'Generate' }));

      await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({
        objective: 'Reactivate lapsed members',
      }));
    });
  });
});
```

**Patterns:**
- Group tests with `describe` blocks (by feature/behavior)
- Use `test()` not `it()` (clearer intent)
- Prefer `screen.getByRole` over `getByTestId` (better accessibility)
- Use `waitFor` for async assertions
- Mock external dependencies (API calls, browser APIs)

### Backend (Pytest + httpx)

**File Naming:** `test_<module>.py`

**Structure:**
```python
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_generate_offer_brief_success(client: AsyncClient):
    response = await client.post("/api/designer/generate", json={
        "objective": "Reactivate lapsed members",
        "segment_criteria": ["high_value", "lapsed_90_days"]
    })

    assert response.status_code == 200
    data = response.json()
    assert "offer_id" in data
    assert data["segment"]["name"] == "lapsed_high_value"

@pytest.mark.asyncio
async def test_generate_offer_brief_validation_error(client: AsyncClient):
    response = await client.post("/api/designer/generate", json={
        "objective": "",  # Empty objective
        "segment_criteria": []
    })

    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert "objective" in data["details"]
```

**Patterns:**
- Use `@pytest.mark.asyncio` for async tests
- Group tests by endpoint (e.g., `test_<endpoint>_<scenario>`)
- Test happy path + validation errors + edge cases
- Use fixtures for shared setup (database, clients)
- Mock external APIs (Claude, Weather)

---

## Mocking

### Mock External APIs

**Claude API (TypeScript):**
```typescript
import { vi } from 'vitest';
import * as claudeApi from '@/services/claude-api';

vi.spyOn(claudeApi, 'generateOfferBrief').mockResolvedValue({
  offer_id: 'test-offer-id',
  objective: 'Reactivate lapsed members',
  segment: { name: 'lapsed_high_value', criteria: ['high_value', 'lapsed_90_days'] },
  // ... rest of OfferBrief
});
```

**Claude API (Python):**
```python
from unittest.mock import AsyncMock, patch

@patch('app.services.claude_api.generate_offer_brief')
async def test_generate_with_mocked_claude(mock_generate):
    mock_generate.return_value = OfferBrief(
        offer_id="test-offer-id",
        objective="Reactivate lapsed members",
        segment=Segment(name="lapsed_high_value", criteria=["high_value", "lapsed_90_days"]),
        # ... rest
    )

    result = await generate_offer_brief_service(objective="...")
    assert result.offer_id == "test-offer-id"
```

### Mock Time-Dependent Logic
```python
from freezegun import freeze_time

@freeze_time("2026-03-26 14:30:00")
def test_time_based_activation():
    # Test activation logic at specific time
    context = {"hour": 14, "day_of_week": "wednesday"}
    score = calculate_time_score(context)
    assert score == 30  # Matches preferred hours
```

---

## Test Data

### Fixtures (Pytest)
```python
@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def sample_offer_brief():
    return OfferBrief(
        offer_id="test-offer-123",
        objective="Reactivate lapsed members",
        segment=Segment(name="lapsed_high_value", criteria=["high_value", "lapsed_90_days"]),
        construct=Construct(type="points_multiplier", value=5, description="5x points"),
        channels=[Channel(channel_type="push", priority=1)],
        kpis=KPIs(expected_redemption_rate=0.15, expected_uplift_pct=25),
        risk_flags=RiskFlags(over_discounting=False, cannibalization=False)
    )
```

### Test Factories (TypeScript)
```typescript
export function createMockOfferBrief(overrides?: Partial<OfferBrief>): OfferBrief {
  return {
    offer_id: 'test-offer-123',
    objective: 'Reactivate lapsed members',
    segment: { name: 'lapsed_high_value', criteria: ['high_value', 'lapsed_90_days'] },
    construct: { type: 'points_multiplier', value: 5, description: '5x points' },
    channels: [{ channel_type: 'push', priority: 1 }],
    kpis: { expected_redemption_rate: 0.15, expected_uplift_pct: 25 },
    risk_flags: { over_discounting: false, cannibalization: false },
    ...overrides,
  };
}
```

---

## Integration Tests

**Purpose:** Test interactions between components (e.g., API → Service → Database)

**Example (Backend):**
```python
@pytest.mark.integration
async def test_offer_brief_end_to_end(client: AsyncClient, db_session):
    # Create offer via API
    response = await client.post("/api/designer/generate", json={
        "objective": "Reactivate lapsed members"
    })
    assert response.status_code == 200
    offer_id = response.json()["offer_id"]

    # Verify offer saved to Hub
    hub_response = await client.get(f"/api/hub/offers/{offer_id}")
    assert hub_response.status_code == 200
    assert hub_response.json()["status"] == "approved"

    # Verify audit log entry
    logs = await client.get(f"/api/hub/audit/{offer_id}")
    assert len(logs.json()) == 1
    assert logs.json()[0]["action"] == "created"
```

**Run separately:** `pytest -m integration` (slower, needs database)

---

## E2E Tests (Playwright)

**Purpose:** Test critical user flows in real browser

**Example:**
```typescript
import { test, expect } from '@playwright/test';

test('Designer flow: Generate offer and approve', async ({ page }) => {
  await page.goto('http://localhost:3000/designer');

  // Enter objective
  await page.fill('input[name="objective"]', 'Reactivate lapsed members');
  await page.click('button:has-text("Generate")');

  // Wait for OfferBrief to appear
  await expect(page.locator('.offer-brief-card')).toBeVisible();

  // Check risk flags
  await expect(page.locator('.risk-flag-over-discounting')).not.toBeVisible();

  // Approve offer
  await page.click('button:has-text("Approve")');
  await expect(page.locator('.toast-success')).toContainText('Offer approved');

  // Verify offer in Hub
  await page.goto('http://localhost:3000/hub');
  await expect(page.locator('.offer-list')).toContainText('Reactivate lapsed members');
});
```

**Run separately:** `npm run test:e2e` (slowest, needs full stack)

---

## Test Naming

### Pattern: `test_<what>_<when>_<expected>`

**Good Examples:**
- `test_generate_offer_brief_when_valid_input_then_returns_offer`
- `test_context_matching_when_score_below_threshold_then_queues_offer`
- `test_fraud_detection_when_over_discounting_then_blocks_activation`

**Bad Examples:**
- `test_1`, `test_offer`, `test_works` (not descriptive)

---

## Assertion Patterns

### Use Specific Assertions
```typescript
// Good
expect(offer.status).toBe('approved');
expect(offer.kpis.expected_uplift_pct).toBeGreaterThan(0);
expect(offer.segment.criteria).toContain('high_value');

// Bad
expect(offer.status === 'approved').toBe(true);
expect(offer.kpis.expected_uplift_pct > 0).toBeTruthy();
```

### Test One Thing Per Test
```typescript
// Good (separate tests)
test('validates objective is not empty', () => { ... });
test('validates segment criteria is array', () => { ... });

// Bad (tests multiple things)
test('validates input', () => {
  // Tests objective AND segment criteria in same test
});
```

---

## Snapshot Testing

**Use sparingly:** Only for stable UI components

**Example:**
```typescript
test('OfferBriefCard renders correctly', () => {
  const { container } = render(<OfferBriefCard offer={mockOffer} />);
  expect(container.firstChild).toMatchSnapshot();
});
```

**Update snapshots:** `npm test -- -u` (review changes carefully!)

---

## Performance Testing

**Test response time targets:**
```python
import time

@pytest.mark.performance
async def test_generate_offer_brief_performance(client: AsyncClient):
    start = time.time()
    response = await client.post("/api/designer/generate", json={...})
    elapsed = time.time() - start

    assert response.status_code == 200
    assert elapsed < 0.2  # <200ms requirement
```

---

## Test Organization

```
tests/
├── unit/
│   ├── frontend/
│   │   ├── components/
│   │   │   ├── Designer/
│   │   │   │   └── OfferBriefForm.test.tsx
│   │   │   └── Hub/
│   │   │       └── OfferList.test.tsx
│   │   └── services/
│   │       └── api.test.ts
│   └── backend/
│       ├── services/
│       │   ├── test_offer_generator.py
│       │   └── test_fraud_detector.py
│       └── models/
│           └── test_offer_brief.py
├── integration/
│   ├── test_designer_api.py
│   ├── test_scout_api.py
│   └── test_hub_api.py
└── e2e/
    ├── designer-flow.spec.ts
    ├── scout-flow.spec.ts
    └── end-to-end.spec.ts
```

---

## CI/CD Pipeline

**Run on every PR:**
1. Unit tests (must pass, coverage >80%)
2. Integration tests (must pass)
3. E2E tests (critical paths only, can be flaky)

**Block merge if:**
- Any test fails
- Coverage drops below 80%
- Performance tests exceed targets

---

**Best Practice:** Write tests BEFORE implementation (TDD) or DURING implementation (not after)