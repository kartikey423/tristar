/**
 * Unit tests for ContextDashboard — AC-020, AC-021.
 *
 * Tests the purchase-event simulation form and rich push-notification card.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ContextDashboard } from '../../../../../src/frontend/components/Scout/ContextDashboard';
import type { MatchResponse, NoMatchResponse } from '../../../../../src/frontend/lib/scout-api';

// Mock callScoutMatch and fetchActivationLog; keep isMatchResponse as real implementation.
jest.mock('../../../../../src/frontend/lib/scout-api', () => {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const actual = jest.requireActual('../../../../../src/frontend/lib/scout-api') as {
    isMatchResponse: (r: unknown) => boolean;
  };
  return {
    isMatchResponse: actual.isMatchResponse,
    callScoutMatch: jest.fn(),
    fetchActivationLog: jest.fn(),
  };
});

import { callScoutMatch, fetchActivationLog } from '../../../../../src/frontend/lib/scout-api';
const mockCallScoutMatch = callScoutMatch as jest.MockedFunction<typeof callScoutMatch>;
const mockFetchActivationLog = fetchActivationLog as jest.MockedFunction<typeof fetchActivationLog>;

const activatedResult: MatchResponse = {
  score: 82.5,
  rationale: 'Strong match — outdoor fan near Sport Chek',
  notification_text: 'Earn 3× points on outdoor gear today!',
  offer_id: 'offer-demo-001',
  outcome: 'activated',
  scoring_method: 'claude',
};

const queuedResult: MatchResponse = {
  score: 73.0,
  rationale: 'Quiet hours — queued for morning',
  notification_text: '5× points on sporting goods!',
  offer_id: 'offer-demo-002',
  outcome: 'queued',
  scoring_method: 'claude',
  queued: true,
  delivery_time: '08:00',
};

const rateLimitedResult: MatchResponse = {
  score: 76.0,
  rationale: 'Rate limited',
  notification_text: '',
  offer_id: 'offer-demo-003',
  outcome: 'rate_limited',
  scoring_method: 'fallback',
  retry_after_seconds: 21600,
};

const noMatchResult: NoMatchResponse = {
  matches: [],
  message: 'No offers scored above activation threshold',
};

describe('ContextDashboard', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Keep ActivationFeed quiet — return empty list so it renders null
    mockFetchActivationLog.mockResolvedValue([]);
  });

  describe('Form rendering', () => {
    test('renders Customer, Store, Item, and Purchase Date fields', () => {
      render(<ContextDashboard />);

      expect(screen.getByLabelText('Customer')).toBeInTheDocument();
      expect(screen.getByLabelText('Store & Branch')).toBeInTheDocument();
      expect(screen.getByLabelText('Item Being Purchased')).toBeInTheDocument();
      expect(screen.getByLabelText('Purchase Date')).toBeInTheDocument();
    });

    test('defaults to demo-001, Canadian Tire Queen St W, first store-specific item', () => {
      render(<ContextDashboard />);

      expect(screen.getByLabelText('Customer')).toHaveValue('demo-001');
      expect(screen.getByLabelText('Store & Branch')).toHaveValue('ctc-001');
      // Item select defaults to index 0
      expect(screen.getByLabelText('Item Being Purchased')).toHaveValue('0');
    });

    test('submit button is present with correct label', () => {
      render(<ContextDashboard />);
      expect(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      ).toBeInTheDocument();
    });

    test('shows Triangle Points preview with purchase total derived from item price and tier', () => {
      render(<ContextDashboard />);
      // demo-001 is gold (15 pts/$1), Motor Oil 5W-30 $38.99 → 585 pts (store-specific inventory)
      expect(screen.getByText(/Triangle Points/)).toBeInTheDocument();
      expect(screen.getByText(/\+585/)).toBeInTheDocument();
      // Shows purchase total cost
      expect(screen.getByText('Purchase total: $38.99')).toBeInTheDocument();
    });

    test('shows dollar value alongside points', () => {
      render(<ContextDashboard />);
      // 585 pts × $0.01 = $5.85
      expect(screen.getByText(/~\$5\.85 value/)).toBeInTheDocument();
    });

    test('shows past purchase history for selected customer', () => {
      render(<ContextDashboard />);
      expect(screen.getByText('Recent purchases')).toBeInTheDocument();
      // demo-001 (Alice Chen) has purchase history
      expect(screen.getByText('Camping Tent (2-person)')).toBeInTheDocument();
    });
  });

  describe('Form submission', () => {
    test('calls callScoutMatch with MatchRequest derived from store+item+member', async () => {
      mockCallScoutMatch.mockResolvedValue(noMatchResult);
      render(<ContextDashboard />);

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      await waitFor(() => {
        expect(mockCallScoutMatch).toHaveBeenCalledWith(
          expect.objectContaining({
            member_id: 'demo-001',
            purchase_location: { lat: 43.6488, lon: -79.3981 }, // Canadian Tire Queen St W
            purchase_category: 'automotive',                      // Motor Oil 5W-30 (store-specific)
            rewards_earned: 585,                                  // $38.99 × 15 pts/$ = 585
            // day_context is derived from today's date — accept any valid value
            day_context: expect.stringMatching(/^(weekday|weekend|long_weekend)$/),
          }),
        );
      });
    });

    test('button shows loading text and is disabled while request is in-flight', async () => {
      mockCallScoutMatch.mockImplementation(() => new Promise(() => {}));
      render(<ContextDashboard />);

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      const btn = screen.getByRole('button');
      expect(btn).toBeDisabled();
      expect(btn).toHaveTextContent(/Processing Transaction\.\.\./i);
    });
  });

  describe('Push notification card', () => {
    test('shows activated outcome badge and personalized notification text', async () => {
      mockCallScoutMatch.mockResolvedValue(activatedResult);
      render(<ContextDashboard />);

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      await waitFor(() => {
        // Original notification text is still shown (as sub-text)
        expect(screen.getByText('Earn 3× points on outdoor gear today!')).toBeInTheDocument();
      });
      expect(screen.getByText('activated')).toBeInTheDocument();
      // Personalized message includes the member first name
      expect(screen.getByText(/Alice/)).toBeInTheDocument();
      // Score shown as integer
      expect(screen.getByText('83/100')).toBeInTheDocument();
    });

    test('shows context signal badges after submission', async () => {
      mockCallScoutMatch.mockResolvedValue(activatedResult);
      render(<ContextDashboard />);

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      await waitFor(() => {
        expect(screen.getByText(/GPS:/)).toBeInTheDocument();
        expect(screen.getByText(/gold tier/)).toBeInTheDocument();
        expect(screen.getByText('automotive')).toBeInTheDocument();
      });
    });

    test('shows purchase receipt with points earned', async () => {
      mockCallScoutMatch.mockResolvedValue(activatedResult);
      render(<ContextDashboard />);

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      await waitFor(() => {
        // Item name in receipt — Motor Oil from store-specific inventory
        expect(screen.getAllByText(/Motor Oil/).length).toBeGreaterThan(0);
        // Points earned shown in receipt ("+585")
        expect(screen.getByText('+585')).toBeInTheDocument();
      });
    });

    test('shows recommended clearance item section', async () => {
      mockCallScoutMatch.mockResolvedValue(activatedResult);
      render(<ContextDashboard />);

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      await waitFor(() => {
        expect(screen.getByText(/Recommended for you/i)).toBeInTheDocument();
      });
    });

    test('shows Petro-Canada fuel redemption section', async () => {
      mockCallScoutMatch.mockResolvedValue(activatedResult);
      render(<ContextDashboard />);

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      await waitFor(() => {
        // Use exact text so it matches only the <p> element, not the store dropdown options
        expect(screen.getByText('Save $0.03/L at Petro-Canada')).toBeInTheDocument();
      });
    });

    test('displays queued outcome with delivery_time', async () => {
      mockCallScoutMatch.mockResolvedValue(queuedResult);
      render(<ContextDashboard />);

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      await waitFor(() => {
        expect(screen.getByText('queued')).toBeInTheDocument();
      });
      expect(screen.getByText(/08:00/)).toBeInTheDocument();
    });

    test('displays rate_limited outcome with retry countdown in minutes', async () => {
      mockCallScoutMatch.mockResolvedValue(rateLimitedResult);
      render(<ContextDashboard />);

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      await waitFor(() => {
        expect(screen.getByText('rate limited')).toBeInTheDocument();
      });
      // 21600 seconds = 360 minutes
      expect(screen.getByText(/360 min/)).toBeInTheDocument();
    });

    test('displays NoMatchResponse message', async () => {
      mockCallScoutMatch.mockResolvedValue(noMatchResult);
      render(<ContextDashboard />);

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      await waitFor(() => {
        expect(
          screen.getByText('No offers scored above activation threshold'),
        ).toBeInTheDocument();
      });
    });

    test('shows error with role="alert" on API failure', async () => {
      mockCallScoutMatch.mockRejectedValue({ detail: 'Scout API temporarily unavailable' });
      render(<ContextDashboard />);

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });
      expect(screen.getByText('Scout API temporarily unavailable')).toBeInTheDocument();
    });
  });

  describe('ActivationFeed integration', () => {
    test('fetchActivationLog is called again after successful submit (refreshCount increments)', async () => {
      mockCallScoutMatch.mockResolvedValue(activatedResult);
      render(<ContextDashboard />);

      // Wait for initial fetch from ActivationFeed mount
      await waitFor(() => {
        expect(mockFetchActivationLog).toHaveBeenCalledTimes(1);
      });

      await userEvent.click(
        screen.getByRole('button', { name: /Run Match Scoring/i }),
      );

      // After submit resolves, refreshCount increments → ActivationFeed re-fetches
      await waitFor(() => {
        expect(mockFetchActivationLog).toHaveBeenCalledTimes(2);
      });
    });
  });
});
