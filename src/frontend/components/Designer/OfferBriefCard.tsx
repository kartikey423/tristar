import type { OfferBrief } from '../../../shared/types/offer-brief';
import { RiskFlagBadge } from './RiskFlagBadge';
import { ApproveButton } from './ApproveButton';

interface OfferBriefCardProps {
  offer: OfferBrief;
  onApproved?: () => void;
}

const CHANNEL_LABELS: Record<string, string> = {
  push: 'Push',
  email: 'Email',
  sms: 'SMS',
  in_app: 'In-App',
};

export function OfferBriefCard({ offer, onApproved }: OfferBriefCardProps) {
  const isPurchaseTriggered = offer.trigger_type === 'purchase_triggered';
  const sortedChannels = [...offer.channels].sort((a, b) => a.priority - b.priority);

  return (
    <article className="card overflow-hidden" aria-label={`Offer brief: ${offer.objective}`}>
      {/* Header */}
      <div className="bg-surface-low px-6 py-4 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-title font-semibold text-gray-900">Offer Brief</span>
            <code className="text-xs text-gray-400 font-mono">
              {offer.offer_id.slice(0, 8)}
            </code>
            <span className="badge badge-neutral uppercase text-[10px]">{offer.status}</span>
          </div>
          <p className="text-sm text-gray-700">{offer.objective}</p>
          <div className="mt-1.5 flex items-center gap-2">
            {isPurchaseTriggered && (
              <span className="badge badge-info text-[10px]">Purchase-triggered</span>
            )}
            {offer.valid_until && (
              <span className="text-xs text-gray-400">
                Valid until {new Date(offer.valid_until).toLocaleString()}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="px-6 py-5 space-y-5">
        {/* Segment */}
        <section aria-label="Target segment">
          <h3 className="text-label uppercase tracking-wider text-gray-500 mb-2">Segment</h3>
          <p className="font-medium text-gray-900 text-sm">{offer.segment.name}</p>
          <p className="text-sm text-gray-500 mt-0.5">{offer.segment.definition}</p>
          <div className="mt-2 flex items-center gap-2">
            <span className="text-xs text-gray-400">
              Est. {offer.segment.estimated_size.toLocaleString()} members
            </span>
            <span className="w-px h-3 bg-gray-200" />
            {offer.segment.criteria.map((c) => (
              <span key={c} className="badge badge-neutral text-[10px]">{c}</span>
            ))}
          </div>
        </section>

        <div className="h-px bg-gray-100" />

        {/* Construct */}
        <section aria-label="Offer construct">
          <h3 className="text-label uppercase tracking-wider text-gray-500 mb-2">Construct</h3>
          <div className="flex items-center gap-3">
            <span className="badge badge-info capitalize">
              {offer.construct.type.replace(/_/g, ' ')}
            </span>
            <span className="text-xl font-bold text-gray-900">{offer.construct.value}</span>
          </div>
          <p className="mt-1 text-sm text-gray-500">{offer.construct.description}</p>
        </section>

        <div className="h-px bg-gray-100" />

        {/* Channels */}
        <section aria-label="Delivery channels">
          <h3 className="text-label uppercase tracking-wider text-gray-500 mb-2">Channels</h3>
          <div className="flex flex-wrap gap-2">
            {sortedChannels.map((channel) => (
              <span
                key={channel.channel_type}
                className="inline-flex items-center gap-1 rounded-md border border-gray-200 bg-white px-2.5 py-1 text-xs text-gray-600"
                aria-label={`Channel: ${CHANNEL_LABELS[channel.channel_type] ?? channel.channel_type} (priority ${channel.priority})`}
              >
                <span className="font-medium">{CHANNEL_LABELS[channel.channel_type] ?? channel.channel_type}</span>
                <span className="text-gray-300">({channel.priority})</span>
              </span>
            ))}
          </div>
        </section>

        <div className="h-px bg-gray-100" />

        {/* KPIs */}
        <section aria-label="Key performance indicators">
          <h3 className="text-label uppercase tracking-wider text-gray-500 mb-2">KPIs</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-md bg-emerald-50/50 border border-emerald-100 px-3 py-2.5">
              <p className="text-xs text-gray-500">Redemption rate</p>
              <p className="font-semibold text-emerald-700 mt-0.5">
                {(offer.kpis.expected_redemption_rate * 100).toFixed(1)}%
              </p>
            </div>
            <div className="rounded-md bg-blue-50/50 border border-blue-100 px-3 py-2.5">
              <p className="text-xs text-gray-500">Expected uplift</p>
              <p className="font-semibold text-blue-700 mt-0.5">
                +{offer.kpis.expected_uplift_pct.toFixed(1)}%
              </p>
            </div>
          </div>
        </section>

        <div className="h-px bg-gray-100" />

        {/* Risk Flags */}
        <section aria-label="Risk assessment">
          <h3 className="text-label uppercase tracking-wider text-gray-500 mb-2">
            Risk Assessment
          </h3>
          <RiskFlagBadge riskFlags={offer.risk_flags} />
        </section>

        {/* Approve Button */}
        <div className="pt-2">
          <ApproveButton offer={offer} onApproved={onApproved} />
        </div>
      </div>
    </article>
  );
}
