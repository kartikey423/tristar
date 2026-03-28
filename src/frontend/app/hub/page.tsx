/**
 * COMP-008: Hub page — Server Component.
 * Renders the OfferList with optional status filter from searchParams.
 * Handles Hub 503 gracefully with an inline error message.
 */

import type { OfferStatus } from '@/../../shared/types/offer-brief';
import { OfferList } from '../../components/Hub/OfferList';
import { fetchOffers } from '../../services/hub-api';

interface HubPageProps {
  searchParams: Promise<{ status?: string }>;
}

export default async function HubPage({ searchParams }: HubPageProps) {
  const { status } = await searchParams;

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

  const statusFilter = status as OfferStatus | undefined;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Hub — Offer State</h1>
        <StatusFilterNav currentStatus={statusFilter} />
      </div>

      {errorMessage ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {errorMessage}
        </div>
      ) : (
        <OfferList offers={offers} />
      )}
    </main>
  );
}

function StatusFilterNav({ currentStatus }: { currentStatus?: OfferStatus }) {
  const filters: Array<{ label: string; value: OfferStatus | undefined }> = [
    { label: 'All', value: undefined },
    { label: 'Draft', value: 'draft' },
    { label: 'Approved', value: 'approved' },
    { label: 'Active', value: 'active' },
    { label: 'Expired', value: 'expired' },
  ];

  return (
    <nav className="flex gap-1" aria-label="Filter offers by status">
      {filters.map(({ label, value }) => {
        const href = value ? `/hub?status=${value}` : '/hub';
        const isActive = currentStatus === value;
        return (
          <a
            key={label}
            href={href}
            className={`rounded px-3 py-1 text-sm transition ${
              isActive
                ? 'bg-gray-900 text-white'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
            aria-current={isActive ? 'page' : undefined}
          >
            {label}
          </a>
        );
      })}
    </nav>
  );
}
