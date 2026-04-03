import type { OfferStatus } from '../../../shared/types/offer-brief';

interface StatusBadgeProps {
  status: OfferStatus;
}

const STATUS_STYLES: Record<OfferStatus, string> = {
  draft: 'badge-neutral',
  approved: 'badge-info',
  active: 'badge-success',
  expired: 'badge-danger opacity-70',
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const styles = STATUS_STYLES[status] ?? 'badge-neutral';

  return (
    <span className={`badge ${styles} capitalize text-[10px]`}>
      {status}
    </span>
  );
}
