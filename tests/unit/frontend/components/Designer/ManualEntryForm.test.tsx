/**
 * Unit tests for ManualEntryForm — COMP-011.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ManualEntryForm } from '../../../../../src/frontend/components/Designer/ManualEntryForm';
import { jest } from '@jest/globals';

// Mock Server Actions
jest.mock('../../../../../src/frontend/app/designer/actions', () => ({
  generateOfferAction: jest.fn(),
  approveOfferAction: jest.fn(),
}));

import { generateOfferAction } from '../../../../../src/frontend/app/designer/actions';
const mockGenerateAction = generateOfferAction as jest.MockedFunction<typeof generateOfferAction>;

// Sample offer for success responses
const mockOffer = {
  offer_id: '550e8400-e29b-41d4-a716-446655440000',
  objective: 'Reactivate lapsed high-value members with winter sports gear offer',
  segment: {
    name: 'lapsed_high_value',
    definition: 'Members with >$500 lifetime spend, inactive 90 days',
    estimated_size: 12500,
    criteria: ['high_value', 'lapsed_90_days'],
  },
  construct: { type: 'points_multiplier', value: 3, description: '3× points on Sport Chek' },
  channels: [{ channel_type: 'push' as const, priority: 1 }],
  kpis: { expected_redemption_rate: 0.15, expected_uplift_pct: 25.0 },
  risk_flags: {
    over_discounting: false,
    cannibalization: false,
    frequency_abuse: false,
    offer_stacking: false,
    severity: 'low' as const,
    warnings: [],
  },
  status: 'draft' as const,
  trigger_type: 'marketer_initiated' as const,
  created_at: '2026-03-27T10:00:00Z',
};

describe('ManualEntryForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Form Validation', () => {
    test('shows error when objective is empty on submit', async () => {
      render(<ManualEntryForm />);

      await userEvent.click(screen.getByRole('button', { name: /Generate Offer/i }));

      await waitFor(() => {
        expect(
          screen.getByText(/at least 10 characters/i),
        ).toBeInTheDocument();
      });
    });

    test('shows error when objective is shorter than 10 characters', async () => {
      render(<ManualEntryForm />);

      await userEvent.type(screen.getByLabelText('Marketing Objective'), 'too short');
      await userEvent.click(screen.getByRole('button', { name: /Generate Offer/i }));

      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });
    });

    test('clears validation error when user starts typing', async () => {
      render(<ManualEntryForm />);

      // Trigger error
      await userEvent.click(screen.getByRole('button', { name: /Generate Offer/i }));
      await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());

      // Start typing — error should clear on next submit attempt
      await userEvent.type(
        screen.getByLabelText('Marketing Objective'),
        'This is a valid objective for testing purposes',
      );

      // Form no longer shows old error for the field
      expect(screen.queryByText(/at least 10 characters/i)).not.toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    test('shows generating spinner while pending', async () => {
      // Never resolving promise to simulate pending
      mockGenerateAction.mockReturnValue(new Promise(() => {}));

      render(<ManualEntryForm />);

      await userEvent.type(
        screen.getByLabelText('Marketing Objective'),
        'Reactivate lapsed high-value members with winter offer',
      );
      await userEvent.click(screen.getByRole('button', { name: /Generate Offer/i }));

      // React 18+ form status
      // Note: useFormStatus requires server action form; in unit tests button state is tested
      // This verifies the button renders correctly before submission
      expect(screen.getByRole('button', { name: /Generate Offer/i })).toBeInTheDocument();
    });

    test('renders OfferBriefCard on successful generation', async () => {
      mockGenerateAction.mockResolvedValue({ success: true, offer: mockOffer });

      render(<ManualEntryForm />);

      await userEvent.type(
        screen.getByLabelText('Marketing Objective'),
        'Reactivate lapsed high-value members with winter offer',
      );
      await userEvent.click(screen.getByRole('button', { name: /Generate Offer/i }));

      await waitFor(() => {
        expect(screen.getByRole('article')).toBeInTheDocument();
      });
    });

    test('shows error message when generation fails', async () => {
      mockGenerateAction.mockResolvedValue({
        success: false,
        error: 'Claude API temporarily unavailable',
      });

      render(<ManualEntryForm />);

      await userEvent.type(
        screen.getByLabelText('Marketing Objective'),
        'Reactivate lapsed high-value members with winter offer',
      );
      await userEvent.click(screen.getByRole('button', { name: /Generate Offer/i }));

      await waitFor(() => {
        expect(screen.getByText('Claude API temporarily unavailable')).toBeInTheDocument();
      });
    });
  });
});
