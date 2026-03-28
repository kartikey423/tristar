/**
 * Unit tests for ApproveButton — COMP-014.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ApproveButton } from '../../../../../src/frontend/components/Designer/ApproveButton';
import { jest } from '@jest/globals';
import type { OfferBrief } from '../../../../../src/shared/types/offer-brief';

jest.mock('../../../../../src/frontend/app/designer/actions', () => ({
  approveOfferAction: jest.fn(),
  generateOfferAction: jest.fn(),
}));

import { approveOfferAction } from '../../../../../src/frontend/app/designer/actions';
const mockApproveAction = approveOfferAction as jest.MockedFunction<typeof approveOfferAction>;

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

      const button = screen.getByRole('button', { name: /Blocked/i });
      expect(button).toBeDisabled();
    });

    test('shows critical risk message when severity is critical', () => {
      render(<ApproveButton offer={makeMockOffer('critical')} />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/critical fraud risk/i)).toBeInTheDocument();
    });

    test('does not call approveOfferAction when severity is critical', async () => {
      render(<ApproveButton offer={makeMockOffer('critical')} />);

      // Try clicking disabled button
      const button = screen.getByRole('button', { name: /Blocked/i });
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
    test('shows Saved to Hub confirmation after successful approval', async () => {
      mockApproveAction.mockResolvedValue({ success: true, message: 'Offer saved to Hub' });

      render(<ApproveButton offer={makeMockOffer('low')} />);

      await userEvent.click(screen.getByRole('button', { name: /Approve/i }));

      await waitFor(() => {
        expect(screen.getByText('Saved to Hub')).toBeInTheDocument();
      });
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
});
