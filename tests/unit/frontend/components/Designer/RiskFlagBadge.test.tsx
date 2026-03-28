/**
 * Unit tests for RiskFlagBadge — COMP-015.
 */

import { render, screen } from '@testing-library/react';
import { RiskFlagBadge } from '../../../../../src/frontend/components/Designer/RiskFlagBadge';
import type { RiskFlags } from '../../../../../src/shared/types/offer-brief';

function makeRiskFlags(overrides: Partial<RiskFlags> = {}): RiskFlags {
  return {
    over_discounting: false,
    cannibalization: false,
    frequency_abuse: false,
    offer_stacking: false,
    severity: 'low',
    warnings: [],
    ...overrides,
  };
}

describe('RiskFlagBadge', () => {
  describe('Critical Severity', () => {
    test('renders critical badge with correct styling', () => {
      render(
        <RiskFlagBadge
          riskFlags={makeRiskFlags({
            over_discounting: true,
            severity: 'critical',
            warnings: ['Discount of 40% exceeds threshold'],
          })}
        />,
      );

      expect(screen.getByText(/critical risk/i)).toBeInTheDocument();
    });

    test('lists active flag names for critical flags', () => {
      render(
        <RiskFlagBadge
          riskFlags={makeRiskFlags({
            over_discounting: true,
            offer_stacking: true,
            severity: 'critical',
            warnings: [],
          })}
        />,
      );

      expect(screen.getByText('Over-discounting')).toBeInTheDocument();
      expect(screen.getByText('Offer stacking')).toBeInTheDocument();
    });
  });

  describe('Medium Severity', () => {
    test('renders medium badge for medium severity', () => {
      render(
        <RiskFlagBadge
          riskFlags={makeRiskFlags({
            cannibalization: true,
            severity: 'medium',
          })}
        />,
      );

      expect(screen.getByText(/medium risk/i)).toBeInTheDocument();
      expect(screen.getByText('Cannibalization')).toBeInTheDocument();
    });
  });

  describe('Low/No Flags', () => {
    test('shows safe indicator when no flags are set', () => {
      render(<RiskFlagBadge riskFlags={makeRiskFlags()} />);

      expect(screen.getByText(/safe to approve/i)).toBeInTheDocument();
    });
  });

  describe('Warnings Display', () => {
    test('displays warning text when present', () => {
      render(
        <RiskFlagBadge
          riskFlags={makeRiskFlags({
            over_discounting: true,
            severity: 'critical',
            warnings: ['Discount of 40.0% exceeds 30% threshold'],
          })}
        />,
      );

      expect(screen.getByText('Discount of 40.0% exceeds 30% threshold')).toBeInTheDocument();
    });
  });
});
