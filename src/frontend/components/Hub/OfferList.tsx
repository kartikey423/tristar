import type { OfferBrief } from '../../../shared/types/offer-brief';
import { StatusActionButtons } from './StatusActionButtons';
import { StatusBadge } from './StatusBadge';

interface OfferListProps {
  offers: OfferBrief[];
}

export function OfferList({ offers }: OfferListProps) {
  if (offers.length === 0) {
    return (
      <div className="card py-12 text-center">
        <p className="text-sm text-gray-500">No offers yet.</p>
      </div>
    );
  }

  const triggerLabelByType: Record<string, string> = {
    marketer_initiated: 'Marketer',
    purchase_triggered: 'Purchase',
  };

  const riskClassBySeverity: Record<string, string> = {
    low: 'badge-success',
    medium: 'badge-warning',
    critical: 'badge-danger',
  };

  function formatCreatedAt(createdAt: string): string {
    const date = new Date(createdAt);
    if (Number.isNaN(date.getTime())) return createdAt;
    return new Intl.DateTimeFormat('en-CA', {
      month: 'short',
      day: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  }

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="data-table min-w-[940px]">
          <thead>
            <tr>
              <th className="pl-4">Status</th>
              <th>Offer ID</th>
              <th>Objective</th>
              <th>Trigger</th>
              <th>Risk</th>
              <th>Created</th>
              <th className="pr-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {offers.map((offer) => {
              const triggerLabel = triggerLabelByType[offer.trigger_type] ?? offer.trigger_type;
              const riskClass = riskClassBySeverity[offer.risk_flags.severity] ?? 'badge-neutral';

              return (
                <tr key={offer.offer_id}>
                  <td className="pl-4 whitespace-nowrap">
                    <StatusBadge status={offer.status} />
                  </td>
                  <td className="whitespace-nowrap align-top">
                    <code className="font-mono text-xs text-gray-500">
                      {offer.offer_id.slice(0, 8)}
                    </code>
                  </td>
                  <td className="max-w-[400px] align-top">
                    <p className="text-sm font-medium text-gray-900 leading-snug" title={offer.objective}>
                      {offer.objective}
                    </p>
                  </td>
                  <td className="whitespace-nowrap align-top">
                    <span className="badge badge-neutral">{triggerLabel}</span>
                  </td>
                  <td className="whitespace-nowrap align-top">
                    <span className={`badge ${riskClass} capitalize`}>
                      {offer.risk_flags.severity}
                    </span>
                  </td>
                  <td className="whitespace-nowrap align-top text-xs text-gray-500">
                    {formatCreatedAt(offer.created_at)}
                  </td>
                  <td className="pr-4 align-top">
                    {offer.status === 'expired' ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-1 text-[11px] font-medium text-gray-400">
                        <span className="material-symbols-outlined text-[13px]" aria-hidden="true">check_circle</span>
                        Closed
                      </span>
                    ) : (
                      <div className="flex justify-end">
                        <StatusActionButtons offerId={offer.offer_id} status={offer.status} />
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
