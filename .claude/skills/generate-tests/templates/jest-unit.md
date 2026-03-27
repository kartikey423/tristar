# Jest + React Testing Library Patterns

Test patterns for TriStar frontend code (React 19 + Next.js 15).

---

## Basic Function Test

```typescript
import { calculateContextScore } from '@/services/context-matcher';

describe('calculateContextScore', () => {
  test('returns weighted average of available signals', () => {
    const signals = {
      gps: { score: 80, available: true },
      time: { score: 60, available: true },
      weather: { score: 40, available: true },
      behavior: { score: 90, available: true },
    };

    const result = calculateContextScore(signals);

    // GPS 30%, Time 25%, Weather 20%, Behavior 25%
    // (80*0.3) + (60*0.25) + (40*0.2) + (90*0.25) = 24 + 15 + 8 + 22.5 = 69.5
    expect(result).toBeCloseTo(69.5);
  });

  test('excludes unavailable signals and redistributes weights', () => {
    const signals = {
      gps: { score: 0, available: false },
      time: { score: 60, available: true },
      weather: { score: 40, available: true },
      behavior: { score: 90, available: true },
    };

    const result = calculateContextScore(signals);

    expect(result).toBeGreaterThan(0);
    expect(result).toBeLessThanOrEqual(100);
  });
});
```

---

## Async Function Test

```typescript
import { generateOfferBrief } from '@/services/designer-api';

describe('generateOfferBrief', () => {
  test('returns offer brief for valid objective', async () => {
    const result = await generateOfferBrief('Reactivate lapsed members');

    expect(result).toHaveProperty('offer_id');
    expect(result.objective).toBe('Reactivate lapsed members');
    expect(result.status).toBe('draft');
  });

  test('throws validation error for short objective', async () => {
    await expect(generateOfferBrief('short')).rejects.toThrow();
  });
});
```

---

## React Component Test

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { OfferBriefForm } from '@/components/Designer/OfferBriefForm';

describe('OfferBriefForm', () => {
  test('renders objective input and submit button', () => {
    render(<OfferBriefForm />);

    expect(screen.getByRole('textbox', { name: /objective/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /generate/i })).toBeInTheDocument();
  });

  test('shows validation error when objective is empty', async () => {
    render(<OfferBriefForm />);

    await userEvent.click(screen.getByRole('button', { name: /generate/i }));

    expect(screen.getByText(/objective is required/i)).toBeInTheDocument();
  });

  test('calls onSubmit with form data when valid', async () => {
    const onSubmit = jest.fn();
    render(<OfferBriefForm onSubmit={onSubmit} />);

    await userEvent.type(
      screen.getByRole('textbox', { name: /objective/i }),
      'Reactivate lapsed high-value members',
    );
    await userEvent.click(screen.getByRole('button', { name: /generate/i }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          objective: 'Reactivate lapsed high-value members',
        }),
      );
    });
  });

  test('disables submit button while pending', async () => {
    const slowSubmit = jest.fn(() => new Promise((r) => setTimeout(r, 1000)));
    render(<OfferBriefForm onSubmit={slowSubmit} />);

    await userEvent.type(
      screen.getByRole('textbox', { name: /objective/i }),
      'Reactivate lapsed members with points',
    );
    await userEvent.click(screen.getByRole('button', { name: /generate/i }));

    expect(screen.getByRole('button', { name: /generating/i })).toBeDisabled();
  });
});
```

---

## React Hook Test

```typescript
import { renderHook, act } from '@testing-library/react';
import { useOfferValidation } from '@/hooks/useOfferValidation';

describe('useOfferValidation', () => {
  test('returns valid for correct offer data', () => {
    const { result } = renderHook(() => useOfferValidation());

    act(() => {
      result.current.validate({
        objective: 'Reactivate lapsed members',
        segment_criteria: ['high_value', 'lapsed_90_days'],
      });
    });

    expect(result.current.isValid).toBe(true);
    expect(result.current.errors).toHaveLength(0);
  });

  test('returns errors for invalid offer data', () => {
    const { result } = renderHook(() => useOfferValidation());

    act(() => {
      result.current.validate({
        objective: 'short',
        segment_criteria: [],
      });
    });

    expect(result.current.isValid).toBe(false);
    expect(result.current.errors.length).toBeGreaterThan(0);
  });
});
```

---

## Mock Patterns

### Mock API Client

```typescript
jest.mock('@/services/api', () => ({
  api: {
    post: jest.fn(),
    get: jest.fn(),
  },
}));

import { api } from '@/services/api';

beforeEach(() => {
  jest.clearAllMocks();
});

test('calls API with correct payload', async () => {
  (api.post as jest.Mock).mockResolvedValue({ offer_id: 'test-123' });

  const result = await generateOfferBrief('Reactivate lapsed members');

  expect(api.post).toHaveBeenCalledWith('/api/designer/generate', {
    objective: 'Reactivate lapsed members',
  });
});
```

### Mock Claude API Response

```typescript
jest.mock('@/services/claude-api', () => ({
  generateWithClaude: jest.fn().mockResolvedValue({
    offer_id: 'test-offer-123',
    objective: 'Reactivate lapsed members',
    segment: { name: 'lapsed_high_value', criteria: ['high_value', 'lapsed_90_days'] },
    construct: { type: 'points_multiplier', value: 5, description: '5x points' },
    channels: [{ channel_type: 'push', priority: 1 }],
    kpis: { expected_redemption_rate: 0.15, expected_uplift_pct: 25 },
    risk_flags: { over_discounting: false, cannibalization: false },
    status: 'draft',
    created_at: '2026-03-27T00:00:00Z',
  }),
}));
```

---

## OfferBrief Mock Factory

```typescript
import type { OfferBrief } from '@/types/offer-brief';

export function createMockOfferBrief(overrides?: Partial<OfferBrief>): OfferBrief {
  return {
    offer_id: 'test-offer-123',
    objective: 'Reactivate lapsed high-value members',
    segment: {
      name: 'lapsed_high_value',
      definition: 'Members inactive >90 days with LTV >$500',
      estimated_size: 15000,
      criteria: ['high_value', 'lapsed_90_days'],
    },
    construct: {
      type: 'points_multiplier',
      value: 5,
      description: '5x points on next purchase',
    },
    channels: [
      { channel_type: 'push', priority: 1 },
      { channel_type: 'email', priority: 2 },
    ],
    kpis: {
      expected_redemption_rate: 0.15,
      expected_uplift_pct: 25,
    },
    risk_flags: {
      over_discounting: false,
      cannibalization: false,
      frequency_abuse: false,
      offer_stacking: false,
    },
    status: 'draft',
    created_at: '2026-03-27T00:00:00Z',
    ...overrides,
  };
}
```
