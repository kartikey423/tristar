/**
 * OfferBriefCard — Server Component.
 *
 * Displays all OfferBrief fields in a structured card layout.
 * Sections: Segment, Construct (type + value + validity), Channels,
 * KPIs, Risk Flags (RiskFlagBadge), Approve button (ApproveButton).
 */

import type { OfferBrief } from '../../../shared/types/offer-brief';
import { RiskFlagBadge } from './RiskFlagBadge';
import { ApproveButton } from './ApproveButton';

interface OfferBriefCardProps {
  offer: OfferBrief;
}

const CHANNEL_LABELS: Record<string, string> = {
  push: 'Push',
  email: 'Email',
  sms: 'SMS',
  in_app: 'In-App',
};

export function OfferBriefCard({ offer }: OfferBriefCardProps) {
  const isPurchaseTriggered = offer.trigger_type === 'purchase_triggered';
  const sortedChannels = [...offer.channels].sort((a, b) => a.priority - b.priority);

  return (
    <article
      className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden"
      aria-label={`Offer brief: ${offer.objective}`}
    >
      {/* Header */}
      <div className="border-b border-gray-100 bg-gray-50 px-6 py-4 flex items-start justify-between">
        <div>
          <h2 className="font-semibold text-gray-900 text-base">{offer.objective}</h2>
          <div className="mt-1.5 flex items-center gap-2">
            <span className="text-xs text-gray-500">
              Status: <span className="font-medium capitalize">{offer.status}</span>
            </span>
            {isPurchaseTriggered && (
              <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs text-purple-700 font-medium">
                Purchase-triggered
              </span>
            )}
            {offer.valid_until && (
              <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs text-orange-700">
                Valid until {new Date(offer.valid_until).toLocaleString()}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="px-6 py-5 space-y-5">
        {/* Segment */}
        <section aria-label="Target segment">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Segment</h3>
          <p className="mt-1 font-medium text-gray-900">{offer.segment.name}</p>
          <p className="text-sm text-gray-600">{offer.segment.definition}</p>
          <p className="mt-1 text-xs text-gray-500">
            Est. {offer.segment.estimated_size.toLocaleString()} members ·{' '}
            {offer.segment.criteria.join(', ')}
          </p>
        </section>

        {/* Construct */}
        <section aria-label="Offer construct">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Construct</h3>
          <div className="mt-1 flex items-center gap-3">
            <span className="rounded-md bg-blue-50 px-3 py-1 text-sm font-medium text-blue-700 capitalize">
              {offer.construct.type.replace(/_/g, ' ')}
            </span>
            <span className="text-lg font-bold text-gray-900">{offer.construct.value}</span>
          </div>
          <p className="mt-1 text-sm text-gray-600">{offer.construct.description}</p>
        </section>

        {/* Channels */}
        <section aria-label="Delivery channels">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">Channels</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {sortedChannels.map((channel) => (
              <span
                key={channel.channel_type}
                className="flex items-center gap-1 rounded-full border border-gray-200 bg-white px-3 py-1 text-xs text-gray-700"
                aria-label={`Channel: ${CHANNEL_LABELS[channel.channel_type] ?? channel.channel_type} (priority ${channel.priority})`}
              >
                <span className="font-medium">{CHANNEL_LABELS[channel.channel_type] ?? channel.channel_type}</span>
                <span className="text-gray-400">·{channel.priority}</span>
              </span>
            ))}
          </div>
        </section>

        {/* KPIs */}
        <section aria-label="Key performance indicators">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">KPIs</h3>
          <div className="mt-2 grid grid-cols-2 gap-3">
            <div className="rounded-md bg-green-50 px-3 py-2">
              <p className="text-xs text-gray-500">Redemption rate</p>
              <p className="font-semibold text-green-700">
                {(offer.kpis.expected_redemption_rate * 100).toFixed(1)}%
              </p>
            </div>
            <div className="rounded-md bg-blue-50 px-3 py-2">
              <p className="text-xs text-gray-500">Expected uplift</p>
              <p className="font-semibold text-blue-700">
                +{offer.kpis.expected_uplift_pct.toFixed(1)}%
              </p>
            </div>
          </div>
        </section>

        {/* Risk Flags */}
        <section aria-label="Risk assessment">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
            Risk Assessment
          </h3>
          <RiskFlagBadge riskFlags={offer.risk_flags} />
        </section>

        {/* Approve Button */}
        <div className="pt-2">
          <ApproveButton offer={offer} />
        </div>
      </div>
    </article>
  );
}
