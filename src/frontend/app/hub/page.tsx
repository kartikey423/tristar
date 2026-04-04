import { Breadcrumb } from '../../components/Shell/Breadcrumb';
import { LiveHubContent } from '../../components/Hub/LiveHubContent';
import { fetchOffers } from '../../services/hub-api';

interface HubPageProps {
  searchParams: Promise<{ status?: string; q?: string; trigger?: string }>;
}

export default async function HubPage({ searchParams }: HubPageProps) {
  const { status, q, trigger } = await searchParams;

  let initialOffers: Awaited<ReturnType<typeof fetchOffers>>['offers'] = [];

  try {
    // Always fetch ALL offers for initial render — LiveHubContent filters client-side
    const result = await fetchOffers({});
    initialOffers = result.offers;
  } catch {
    // LiveHubContent will show empty state; polling will recover
  }

  const searchQuery = q?.trim() ?? '';
  const triggerFilter = trigger?.trim() ?? '';

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

      {/* Search + trigger filter */}
      <div className="mb-4 flex justify-end">
        <form action="/hub" method="GET" className="w-full max-w-lg">
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
              defaultValue={triggerFilter}
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

      {/* Live offer content — polls every 5s, counts and list update automatically */}
      <LiveHubContent
        initialOffers={initialOffers}
        statusFilter={status}
        searchQuery={searchQuery}
        triggerFilter={triggerFilter}
      />
    </>
  );
}
