/**
 * COMP-010: OfferCard — Server Component.
 * Renders a single offer with status badge, objective, trigger_type label,
 * risk severity, and an Approve button for draft offers.
 *
 * F-005 FIX: Import from @/../../shared/types/offer-brief (correct relative path).
 */

import type { OfferBrief } from '@/../../shared/types/offer-brief';
import { StatusBadge } from './StatusBadge';
import { ApproveButton } from './ApproveButton';

interface OfferCardProps {
  offer: OfferBrief;
}

const TRIGGER_LABELS: Record<string, string> = {
  marketer_initiated: 'Marketer',
  purchase_triggered: 'Purchase Trigger',
};

const RISK_SEVERITY_STYLES: Record<string, string> = {
  low: 'text-green-700 bg-green-50',
  medium: 'text-yellow-700 bg-yellow-50',
  critical: 'text-red-700 bg-red-50 font-semibold',
};

export function OfferCard({ offer }: OfferCardProps) {
  const shortId = offer.offer_id.slice(0, 8);
  const triggerLabel = TRIGGER_LABELS[offer.trigger_type] ?? offer.trigger_type;
  const riskStyle = RISK_SEVERITY_STYLES[offer.risk_flags.severity] ?? 'text-gray-600';

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <StatusBadge status={offer.status} />
          <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-500">
            {shortId}…
          </span>
        </div>
        <span className="rounded-full bg-purple-50 px-2 py-0.5 text-xs text-purple-700">
          {triggerLabel}
        </span>
      </div>

      <p className="mb-3 text-sm font-medium text-gray-900 leading-snug">{offer.objective}</p>

      <div className="mb-3 flex items-center gap-2">
        <span className={`rounded px-2 py-0.5 text-xs ${riskStyle}`}>
          Risk: {offer.risk_flags.severity}
        </span>
      </div>

      {offer.status === 'draft' && (
        <div className="mt-3 border-t border-gray-100 pt-3">
          <ApproveButton offerId={offer.offer_id} />
        </div>
      )}
    </div>
  );
}
