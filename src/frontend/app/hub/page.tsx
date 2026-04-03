import { OFFER_STATUSES } from '../../../shared/types/offer-brief';
import type { OfferStatus } from '../../../shared/types/offer-brief';
import { Breadcrumb } from '../../components/Shell/Breadcrumb';
import { OfferList } from '../../components/Hub/OfferList';
import { fetchOffers } from '../../services/hub-api';

interface HubPageProps {
  searchParams: Promise<{ status?: string; q?: string; trigger?: string }>;
}

export default async function HubPage({ searchParams }: HubPageProps) {
  const { status, q, trigger } = await searchParams;

  let offers: Awaited<ReturnType<typeof fetchOffers>>['offers'] = [];
  let errorMessage: string | null = null;

  try {
    const result = await fetchOffers(status ? { status } : {});
    offers = result.offers;
  } catch (err) {
    errorMessage =
      err instanceof Error && err.message.includes('503')
        ? 'Hub is temporarily unavailable. Please try again shortly.'
        : 'Failed to load offers. Please refresh the page.';
  }

  const searchQuery = q?.trim() ?? '';
  const triggerFilter = trigger?.trim() ?? '';
  const filteredOffers = offers.filter((o) => {
    const matchesSearch = !searchQuery || o.objective.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTrigger = !triggerFilter || o.trigger_type === triggerFilter;
    return matchesSearch && matchesTrigger;
  });

  const statusFilter = status as OfferStatus | undefined;
  const activeCount = offers.filter((o) => o.status === 'active').length;
  const approvedCount = offers.filter((o) => o.status === 'approved').length;
  const draftCount = offers.filter((o) => o.status === 'draft').length;
  const expiredCount = offers.filter((o) => o.status === 'expired').length;

  return (
    <>
      <Breadcrumb
        items={['TriStar', 'Hub']}
        trailing={
          <span className="flex items-center gap-2 text-xs text-gray-400">
            <span className="status-dot status-dot-draft" /> draft
            <span className="text-gray-300">&rarr;</span>
            <span className="status-dot status-dot-approved" /> approved
            <span className="text-gray-300">&rarr;</span>
            <span className="status-dot status-dot-active" /> active
            <span className="text-gray-300">&rarr;</span>
            <span className="status-dot status-dot-expired" /> expired
          </span>
        }
      />

      <div className="mb-6">
        <h1 className="text-headline text-gray-900">Hub</h1>
        <p className="mt-1 text-sm text-gray-500 max-w-xl">
          Offer state store — manage the lifecycle of all Triangle Rewards offers.
        </p>
      </div>

      {/* Summary chips */}
      <div className="flex items-center gap-4 mb-6 text-sm">
        <span className="text-gray-500">
          Total: <span className="font-semibold text-gray-900">{offers.length}</span>
        </span>
        <span className="w-px h-4 bg-gray-200" />
        <span className="flex items-center gap-1.5 text-gray-500">
          <span className="status-dot status-dot-active" />
          Active: <span className="font-semibold text-gray-900">{activeCount}</span>
        </span>
        <span className="flex items-center gap-1.5 text-gray-500">
          <span className="status-dot status-dot-approved" />
          Approved: <span className="font-semibold text-gray-900">{approvedCount}</span>
        </span>
        <span className="flex items-center gap-1.5 text-gray-500">
          <span className="status-dot status-dot-draft" />
          Draft: <span className="font-semibold text-gray-900">{draftCount}</span>
        </span>
        <span className="flex items-center gap-1.5 text-gray-500">
          <span className="status-dot status-dot-expired" />
          Expired: <span className="font-semibold text-gray-900">{expiredCount}</span>
        </span>
      </div>

      {/* Filter tabs + search */}
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <StatusFilterNav currentStatus={statusFilter} searchQuery={searchQuery} counts={{ active: activeCount, approved: approvedCount, draft: draftCount, expired: expiredCount, total: offers.length }} />

        <form action="/hub" method="GET" className="w-full lg:max-w-lg">
          {status && <input type="hidden" name="status" value={status} />}
          <div className="flex gap-2">
            <div className="relative flex-1">
              <span className="material-symbols-outlined pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[16px] text-gray-400" aria-hidden="true">search</span>
              <input
                type="text"
                name="q"
                defaultValue={searchQuery}
                placeholder="Search by objective…"
                aria-label="Search offers"
                className="w-full rounded-md border border-gray-200 bg-white py-2 pl-8 pr-3 text-sm text-gray-900 placeholder-gray-400 focus:border-gray-400 focus:outline-none focus:ring-1 focus:ring-gray-400"
              />
            </div>
            <select
              name="trigger"
              defaultValue=""
              aria-label="Filter by trigger type"
              className="rounded-md border border-gray-200 bg-white px-2 py-2 text-xs text-gray-600 focus:border-gray-400 focus:outline-none focus:ring-1 focus:ring-gray-400"
            >
              <option value="">All triggers</option>
              <option value="marketer_initiated">Marketer</option>
              <option value="purchase_triggered">Purchase</option>
            </select>
            <button
              type="submit"
              className="rounded-md bg-gray-900 px-4 py-2 text-xs font-semibold text-white hover:bg-gray-700 transition"
            >
              Filter
            </button>
          </div>
        </form>
      </div>

      {/* Search result info */}
      {searchQuery && (
        <div className="mb-4 flex items-center gap-2 text-sm text-gray-500">
          <span>
            Showing <span className="font-semibold text-gray-900">{filteredOffers.length}</span>{' '}
            result{filteredOffers.length !== 1 ? 's' : ''} for &ldquo;{searchQuery}&rdquo;
          </span>
          <a href={status ? `/hub?status=${status}` : '/hub'} className="text-xs text-blue-600 hover:underline">
            Clear search
          </a>
        </div>
      )}

      {/* Offer list */}
      {errorMessage ? (
        <div className="card px-4 py-3 border-l-2 border-red-500">
          <p className="text-sm text-red-700">{errorMessage}</p>
        </div>
      ) : (
        <OfferList offers={filteredOffers} />
      )}
    </>
  );
}

function StatusFilterNav({
  currentStatus,
  searchQuery,
  counts,
}: {
  currentStatus?: OfferStatus;
  searchQuery?: string;
  counts: Record<string, number>;
}) {
  const filters: Array<{ label: string; value: OfferStatus | undefined; count: number }> = [
    { label: 'All', value: undefined, count: counts.total },
    ...OFFER_STATUSES.map((s) => ({
      label: s.charAt(0).toUpperCase() + s.slice(1),
      value: s,
      count: counts[s] ?? 0,
    })),
  ];

  return (
    <nav className="flex gap-1" aria-label="Filter offers by status">
      {filters.map(({ label, value, count }) => {
        const params = new URLSearchParams();
        if (value) params.set('status', value);
        if (searchQuery) params.set('q', searchQuery);
        const qs = params.toString();
        const href = qs ? `/hub?${qs}` : '/hub';
        const isActive = currentStatus === value;
        return (
          <a
            key={label}
            href={href}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
              isActive
                ? 'bg-gray-900 text-white'
                : 'text-gray-500 hover:bg-surface-low hover:text-gray-700'
            }`}
            aria-current={isActive ? 'page' : undefined}
          >
            {label}
            <span className={`ml-1.5 ${isActive ? 'text-gray-400' : 'text-gray-400'}`}>
              {count}
            </span>
          </a>
        );
      })}
    </nav>
  );
}
