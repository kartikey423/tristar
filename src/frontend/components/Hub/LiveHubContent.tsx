'use client';

import { useState, useEffect, useCallback } from 'react';
import type { OfferBrief, OfferStatus } from '../../../shared/types/offer-brief';
import { OFFER_STATUSES } from '../../../shared/types/offer-brief';
import { OfferList } from './OfferList';

const POLL_MS = 5000;

interface LiveHubContentProps {
  initialOffers: OfferBrief[];
  statusFilter?: string;
  searchQuery?: string;
  triggerFilter?: string;
}

export function LiveHubContent({
  initialOffers,
  statusFilter,
  searchQuery,
  triggerFilter,
}: LiveHubContentProps) {
  const [offers, setOffers] = useState<OfferBrief[]>(initialOffers);

  const poll = useCallback(async () => {
    try {
      // Always fetch ALL offers — we filter client-side so counts stay accurate
      const res = await fetch('/api/hub-offers', { cache: 'no-store' });
      if (!res.ok) return;
      const data = await res.json();
      setOffers(data.offers ?? []);
    } catch {
      // Keep stale data on network error
    }
  }, []);

  useEffect(() => {
    const timer = setInterval(poll, POLL_MS);
    return () => clearInterval(timer);
  }, [poll]);

  // Counts always from the full unfiltered list
  const activeCount = offers.filter((o) => o.status === 'active').length;
  const approvedCount = offers.filter((o) => o.status === 'approved').length;
  const draftCount = offers.filter((o) => o.status === 'draft').length;
  const expiredCount = offers.filter((o) => o.status === 'expired').length;

  // Display list: apply status / search / trigger filters client-side
  const filtered = offers.filter((o) => {
    const matchStatus = !statusFilter || o.status === statusFilter;
    const matchSearch =
      !searchQuery || o.objective.toLowerCase().includes(searchQuery.toLowerCase());
    const matchTrigger = !triggerFilter || o.trigger_type === triggerFilter;
    return matchStatus && matchSearch && matchTrigger;
  });

  return (
    <>
      {/* Live summary chips */}
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

      {/* Status filter nav — live counts */}
      <LiveStatusNav
        currentStatus={statusFilter as OfferStatus | undefined}
        searchQuery={searchQuery}
        counts={{ active: activeCount, approved: approvedCount, draft: draftCount, expired: expiredCount, total: offers.length }}
      />

      {/* Offer table */}
      <OfferList offers={filtered} />
    </>
  );
}

function LiveStatusNav({
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
    <nav className="flex gap-1 mb-4" aria-label="Filter offers by status">
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
            <span className="ml-1.5 text-gray-400">{count}</span>
          </a>
        );
      })}
    </nav>
  );
}
