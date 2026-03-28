/**
 * COMP-009: OfferList — Server Component.
 * Maps offers to OfferCard components.
 * Displays "No offers yet." when the list is empty.
 */

import type { OfferBrief } from '@/../../shared/types/offer-brief';
import { OfferCard } from './OfferCard';

interface OfferListProps {
  offers: OfferBrief[];
}

export function OfferList({ offers }: OfferListProps) {
  if (offers.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-gray-500">
        No offers yet.
      </p>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {offers.map((offer) => (
        <OfferCard key={offer.offer_id} offer={offer} />
      ))}
    </div>
  );
}
