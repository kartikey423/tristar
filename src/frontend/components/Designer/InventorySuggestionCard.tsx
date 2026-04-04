import type { InventorySuggestion } from '../../../shared/types/offer-brief';
import { prefillObjectiveAction } from '../../app/designer/actions';

interface InventorySuggestionCardProps {
  suggestion: InventorySuggestion;
  isOffered?: boolean;
  onOfferGenerated?: (productId: string) => void;
}

const URGENCY_STYLES: Record<string, string> = {
  high: 'badge-danger',
  medium: 'badge-warning',
  low: 'badge-neutral',
};

const URGENCY_LABELS: Record<string, string> = {
  high: 'OVERSTOCK',
  medium: 'WATCH',
  low: 'NORMAL',
};

export function InventorySuggestionCard({ suggestion, isOffered = false, onOfferGenerated }: InventorySuggestionCardProps) {
  const urgencyStyle = URGENCY_STYLES[suggestion.urgency] ?? URGENCY_STYLES.medium;
  const urgencyLabel = URGENCY_LABELS[suggestion.urgency] ?? suggestion.urgency;

  return (
    <div className="card p-5 flex flex-col h-full">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <h3 className="font-semibold text-sm text-gray-900">{suggestion.product_name}</h3>
          <p className="text-xs text-gray-400 mt-0.5">
            {suggestion.store} &middot; {suggestion.category}
          </p>
        </div>
        <span
          className={`badge ${urgencyStyle} text-[10px] uppercase shrink-0`}
          aria-label={`Urgency: ${urgencyLabel}`}
        >
          {urgencyLabel}
        </span>
      </div>

      {suggestion.stale && (
        <span className="badge badge-warning text-[10px] mb-2">Stale data</span>
      )}

      <p className="text-sm text-gray-500 mb-3">
        {suggestion.units_in_stock.toLocaleString()} units in stock
      </p>

      <p className="text-xs text-gray-500 italic leading-relaxed mb-4 flex-1">
        &ldquo;{suggestion.suggested_objective}&rdquo;
      </p>

      <form action={prefillObjectiveAction} className="mt-auto" onSubmit={() => onOfferGenerated?.(suggestion.product_id)}>
        <input type="hidden" name="objective" value={suggestion.suggested_objective} />
        <button
          type="submit"
          disabled={isOffered}
          className={`w-full rounded-md border px-4 py-2 text-sm font-medium transition
            focus:outline-none focus:ring-2 focus:ring-ct-red focus:ring-offset-2
            ${isOffered
              ? 'border-gray-300 bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'border-ct-red bg-white text-ct-red hover:bg-ct-red hover:text-white'
            }`}
          aria-label={isOffered ? 'Offer already created for this item' : `Use objective: ${suggestion.suggested_objective}`}
          aria-disabled={isOffered}
        >
          {isOffered ? 'Offer Created' : 'Generate Offer'}
        </button>
      </form>
    </div>
  );
}
