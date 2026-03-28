/**
 * COMP-012: StatusBadge — Server Component.
 * Renders a colored badge for Hub offer status.
 * Color map: draft=grey, approved=blue, active=green, expired=red/opacity.
 */

import type { OfferStatus } from '@/../../shared/types/offer-brief';

interface StatusBadgeProps {
  status: OfferStatus;
}

const STATUS_STYLES: Record<OfferStatus, string> = {
  draft: 'bg-gray-100 text-gray-700 border border-gray-300',
  approved: 'bg-blue-100 text-blue-800 border border-blue-300',
  active: 'bg-green-100 text-green-800 border border-green-300',
  expired: 'bg-red-100 text-red-400 border border-red-200 opacity-70',
};

const STATUS_LABELS: Record<OfferStatus, string> = {
  draft: 'Draft',
  approved: 'Approved',
  active: 'Active',
  expired: 'Expired',
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const styles = STATUS_STYLES[status] ?? 'bg-gray-100 text-gray-600 border border-gray-200';
  const label = STATUS_LABELS[status] ?? status;

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${styles}`}>
      {label}
    </span>
  );
}
