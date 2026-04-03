/**
 * Unit tests for ApproveButton — COMP-014.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApproveButton } from '../../../../../src/frontend/components/Designer/ApproveButton';
import type { OfferBrief } from '../../../../../src/shared/types/offer-brief';

jest.mock('../../../../../src/frontend/app/designer/actions', () => ({
  approveOfferAction: jest.fn(),
  generateOfferAction: jest.fn(),
  rejectOfferAction: jest.fn(),
  updateConstructValueAction: jest.fn(),
}));

import {
  approveOfferAction,
  rejectOfferAction,
  updateConstructValueAction,
} from '../../../../../src/frontend/app/designer/actions';
const mockApproveAction = approveOfferAction as jest.MockedFunction<typeof approveOfferAction>;
const mockRejectAction = rejectOfferAction as jest.MockedFunction<typeof rejectOfferAction>;
const mockUpdateConstructAction = updateConstructValueAction as jest.MockedFunction<
  typeof updateConstructValueAction
>;

function makeMockOffer(riskSeverity: 'low' | 'medium' | 'critical' = 'low'): OfferBrief {
  return {
    offer_id: 'test-offer-123',
    objective: 'Reactivate lapsed high-value members with winter sports gear offer',
    segment: {
      name: 'lapsed_high_value',
      definition: 'Test definition',
      estimated_size: 1000,
      criteria: ['high_value'],
    },
    construct: { type: 'points_multiplier', value: 3, description: '3× points' },
    channels: [{ channel_type: 'push', priority: 1 }],
    kpis: { expected_redemption_rate: 0.15, expected_uplift_pct: 25.0 },
    risk_flags: {
      over_discounting: riskSeverity === 'critical',
      cannibalization: false,
      frequency_abuse: false,
      offer_stacking: false,
      severity: riskSeverity,
      warnings: riskSeverity === 'critical' ? ['Discount exceeds threshold'] : [],
    },
    status: 'draft',
    trigger_type: 'marketer_initiated',
    created_at: '2026-03-27T10:00:00Z',
  };
}

describe('ApproveButton', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Critical Risk', () => {
    test('button is disabled when severity is critical', () => {
      render(<ApproveButton offer={makeMockOffer('critical')} />);

      // Accessible name comes from aria-label, not visible text
      const button = screen.getByRole('button', { name: /cannot approve/i });
      expect(button).toBeDisabled();
    });

    test('shows critical risk message when severity is critical', () => {
      render(<ApproveButton offer={makeMockOffer('critical')} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/critical fraud risk/i)).toBeInTheDocument();
    });

    test('does not call approveOfferAction when severity is critical', async () => {
      render(<ApproveButton offer={makeMockOffer('critical')} />);

      // Try clicking disabled button (accessible name from aria-label)
      const button = screen.getByRole('button', { name: /cannot approve/i });
      await userEvent.click(button);

      expect(mockApproveAction).not.toHaveBeenCalled();
    });
  });

  describe('Safe Risk', () => {
    test('button is enabled when severity is low', () => {
      render(<ApproveButton offer={makeMockOffer('low')} />);

      const button = screen.getByRole('button', { name: /Approve/i });
      expect(button).not.toBeDisabled();
    });

    test('button is enabled when severity is medium', () => {
      render(<ApproveButton offer={makeMockOffer('medium')} />);

      const button = screen.getByRole('button', { name: /Approve/i });
      expect(button).not.toBeDisabled();
    });
  });

  describe('Success State', () => {
    // The "Saved to Hub" banner is shown when offer.status === 'approved' (parent re-renders
    // after the server action completes). useOptimistic reverts once the transition ends,
    // so we verify the steady-state by passing an already-approved offer directly.
    test('shows Saved to Hub when offer is already approved', () => {
      const approvedOffer = { ...makeMockOffer('low'), status: 'approved' as const };
      render(<ApproveButton offer={approvedOffer} />);

      expect(screen.getByText('Saved to Hub')).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Approve/i })).not.toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    test('shows error message and retry when approval fails', async () => {
      mockApproveAction.mockResolvedValue({
        success: false,
        error: 'Hub API temporarily unavailable',
      });

      render(<ApproveButton offer={makeMockOffer('low')} />);

      await userEvent.click(screen.getByRole('button', { name: /Approve/i }));

      await waitFor(() => {
        expect(screen.getByText('Hub API temporarily unavailable')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Retry/i })).toBeInTheDocument();
      });
    });
  });

  describe('Reject Offer', () => {
    test('shows confirmation dialog when Reject Offer is clicked', async () => {
      render(<ApproveButton offer={makeMockOffer('low')} />);

      await userEvent.click(screen.getByRole('button', { name: /Reject Offer/i }));

      expect(screen.getByText('Reject this offer?')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Yes, Reject/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
    });

    test('cancel hides confirmation dialog', async () => {
      render(<ApproveButton offer={makeMockOffer('low')} />);

      await userEvent.click(screen.getByRole('button', { name: /Reject Offer/i }));
      await userEvent.click(screen.getByRole('button', { name: /Cancel/i }));

      expect(screen.queryByText('Reject this offer?')).not.toBeInTheDocument();
    });

    test('calls rejectOfferAction on confirmation and shows rejected state', async () => {
      mockRejectAction.mockResolvedValue({ success: true });
      render(<ApproveButton offer={makeMockOffer('low')} />);

      await userEvent.click(screen.getByRole('button', { name: /Reject Offer/i }));
      await userEvent.click(screen.getByRole('button', { name: /Yes, Reject/i }));

      await waitFor(() => {
        expect(mockRejectAction).toHaveBeenCalledWith('test-offer-123');
        expect(screen.getByText(/Offer rejected and removed/i)).toBeInTheDocument();
      });
    });
  });

  describe('Discount Override', () => {
    test('shows construct value input pre-filled with offer construct value', () => {
      render(<ApproveButton offer={makeMockOffer('low')} />);

      const input = screen.getByLabelText(/Points Multiplier/i) as HTMLInputElement;
      expect(input).toBeInTheDocument();
      expect(input.value).toBe('3');
    });

    test('calls updateConstructValueAction when Update is clicked', async () => {
      mockUpdateConstructAction.mockResolvedValue({ success: true });
      render(<ApproveButton offer={makeMockOffer('low')} />);

      const input = screen.getByLabelText(/Points Multiplier/i);
      await userEvent.clear(input);
      await userEvent.type(input, '5');
      await userEvent.click(screen.getByRole('button', { name: /Update/i }));

      await waitFor(() => {
        expect(mockUpdateConstructAction).toHaveBeenCalledWith('test-offer-123', 5);
      });
    });
  });
});
