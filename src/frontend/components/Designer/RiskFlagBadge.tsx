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

const SEVERITY_STYLES: Record<string, { container: string; badge: string }> = {
  critical: {
    container: 'bg-red-50 border-l-2 border-red-500',
    badge: 'badge-danger',
  },
  medium: {
    container: 'bg-amber-50 border-l-2 border-amber-500',
    badge: 'badge-warning',
  },
  low: {
    container: 'bg-surface-low border-l-2 border-gray-300',
    badge: 'badge-neutral',
  },
};

export function RiskFlagBadge({ riskFlags }: RiskFlagBadgeProps) {
  const styles = SEVERITY_STYLES[riskFlags.severity] ?? SEVERITY_STYLES.low;

  const activeFlags = FLAG_KEYS
    .filter((key) => riskFlags[key])
    .map((key) => FLAG_LABELS[key]);

  if (activeFlags.length === 0 && riskFlags.severity === 'low') {
    return (
      <div className="flex items-center gap-2 rounded-md bg-emerald-50 border-l-2 border-emerald-500 px-3 py-2.5">
        <span className="material-symbols-outlined text-[16px] text-emerald-600" aria-hidden="true">
          check_circle
        </span>
        <span className="text-sm text-emerald-700 font-medium">No risk flags — safe to approve</span>
      </div>
    );
  }

  return (
    <div
      className={`rounded-md px-3 py-2.5 ${styles.container}`}
      role="region"
      aria-label={`Risk assessment: ${riskFlags.severity}`}
    >
      <div className="flex items-center gap-2">
        <span className="material-symbols-outlined text-[16px] text-current" aria-hidden="true">
          {riskFlags.severity === 'critical' ? 'error' : 'warning'}
        </span>
        <span className={`badge ${styles.badge} uppercase text-[10px]`}>
          {riskFlags.severity} risk
        </span>
      </div>

      {activeFlags.length > 0 && (
        <ul className="mt-2 space-y-1 ml-6">
          {activeFlags.map((flag) => (
            <li key={flag} className="text-sm text-gray-700 flex items-center gap-1.5">
              <span className="w-1 h-1 rounded-full bg-gray-400" aria-hidden="true" />
              {flag}
            </li>
          ))}
        </ul>
      )}

      {riskFlags.warnings.length > 0 && (
        <ul className="mt-2 space-y-1 ml-6">
          {riskFlags.warnings.map((warning) => (
            <li key={warning} className="text-xs text-gray-500 italic">
              {warning}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
