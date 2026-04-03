import type { OfferBrief } from '../../../shared/types/offer-brief';
import { StatusBadge } from './StatusBadge';
import { StatusActionButtons } from './StatusActionButtons';

interface OfferCardProps {
  offer: OfferBrief;
}

const TRIGGER_LABELS: Record<string, string> = {
  marketer_initiated: 'Marketer',
  purchase_triggered: 'Purchase',
};

const RISK_SEVERITY_STYLES: Record<string, string> = {
  low: 'badge-success',
  medium: 'badge-warning',
  critical: 'badge-danger',
};

export function OfferCard({ offer }: OfferCardProps) {
  const shortId = offer.offer_id.slice(0, 8);
  const triggerLabel = TRIGGER_LABELS[offer.trigger_type] ?? offer.trigger_type;
  const riskStyle = RISK_SEVERITY_STYLES[offer.risk_flags.severity] ?? 'badge-neutral';

  return (
    <div className="card p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <StatusBadge status={offer.status} />
          <code className="text-xs text-gray-400 font-mono">
            {shortId}
          </code>
        </div>
        <span className="badge badge-neutral text-[10px]">
          {triggerLabel}
        </span>
      </div>

      <p className="mb-3 text-sm font-medium text-gray-900 leading-snug">{offer.objective}</p>

      <div className="mb-3 flex items-center gap-2">
        <span className={`badge ${riskStyle} capitalize text-[10px]`}>
          Risk: {offer.risk_flags.severity}
        </span>
      </div>

      {offer.status !== 'expired' && (
        <div className="mt-3 border-t border-gray-100 pt-3">
          <StatusActionButtons offerId={offer.offer_id} status={offer.status} />
        </div>
      )}
    </div>
  );
}
