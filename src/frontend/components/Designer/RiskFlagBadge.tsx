/**
 * RiskFlagBadge — Server Component.
 *
 * Displays active fraud risk flags with severity-appropriate styling:
 * - Critical → red background + warning icon
 * - Medium → yellow background + caution icon
 * - Low → gray background + info icon
 */

import type { RiskFlags } from '../../../shared/types/offer-brief';

interface RiskFlagBadgeProps {
  riskFlags: RiskFlags;
}

const FLAG_KEYS = ['over_discounting', 'cannibalization', 'frequency_abuse', 'offer_stacking'] as const;
type FlagKey = (typeof FLAG_KEYS)[number];

const FLAG_LABELS: Record<FlagKey, string> = {
  over_discounting: 'Over-discounting',
  cannibalization: 'Cannibalization',
  frequency_abuse: 'Frequency abuse',
  offer_stacking: 'Offer stacking',
};

const SEVERITY_STYLES: Record<string, { container: string; badge: string; icon: string }> = {
  critical: {
    container: 'bg-red-50 border-red-200',
    badge: 'bg-red-100 text-red-800',
    icon: '⚠️',
  },
  medium: {
    container: 'bg-yellow-50 border-yellow-200',
    badge: 'bg-yellow-100 text-yellow-800',
    icon: '⚡',
  },
  low: {
    container: 'bg-gray-50 border-gray-200',
    badge: 'bg-gray-100 text-gray-700',
    icon: 'ℹ️',
  },
};

export function RiskFlagBadge({ riskFlags }: RiskFlagBadgeProps) {
  const styles = SEVERITY_STYLES[riskFlags.severity] ?? SEVERITY_STYLES.low;

  const activeFlags = FLAG_KEYS
    .filter((key) => riskFlags[key])
    .map((key) => FLAG_LABELS[key]);

  if (activeFlags.length === 0 && riskFlags.severity === 'low') {
    return (
      <div className="flex items-center gap-2 rounded-md bg-green-50 border border-green-200 px-3 py-2">
        <span aria-hidden="true">✅</span>
        <span className="text-sm text-green-700 font-medium">No risk flags — safe to approve</span>
      </div>
    );
  }

  return (
    <div
      className={`rounded-md border px-3 py-2 ${styles.container}`}
      role="region"
      aria-label={`Risk assessment: ${riskFlags.severity}`}
    >
      <div className="flex items-center gap-2">
        <span aria-hidden="true">{styles.icon}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold uppercase ${styles.badge}`}>
          {riskFlags.severity} risk
        </span>
      </div>

      {activeFlags.length > 0 && (
        <ul className="mt-2 space-y-1">
          {activeFlags.map((flag) => (
            <li key={flag} className="text-sm text-gray-700 flex items-center gap-1.5">
              <span className="text-xs" aria-hidden="true">•</span>
              {flag}
            </li>
          ))}
        </ul>
      )}

      {riskFlags.warnings.length > 0 && (
        <ul className="mt-2 space-y-1">
          {riskFlags.warnings.map((warning) => (
            <li key={warning} className="text-xs text-gray-600 italic">
              {warning}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
