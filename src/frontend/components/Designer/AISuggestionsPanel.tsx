/**
 * AISuggestionsPanel — Server Component.
 *
 * Receives pre-fetched inventory suggestions from the parent page and maps
 * them to InventorySuggestionCard components. Shows a notice when data is stale.
 */

import type { InventorySuggestion } from '../../../shared/types/offer-brief';
import { InventorySuggestionCard } from './InventorySuggestionCard';

interface AISuggestionsPanelProps {
  suggestions: InventorySuggestion[];
}

export function AISuggestionsPanel({ suggestions }: AISuggestionsPanelProps) {
  const hasStaleData = suggestions.some((s) => s.stale);

  if (suggestions.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center">
        <p className="text-gray-500">No overstock items found requiring attention.</p>
        <p className="mt-1 text-sm text-gray-400">
          All inventory levels are within normal thresholds.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">
          AI Inventory Recommendations
        </h2>
        <span className="text-sm text-gray-500">
          {suggestions.length} item{suggestions.length !== 1 ? 's' : ''} need attention
        </span>
      </div>

      {hasStaleData && (
        <div
          className="rounded-md bg-orange-50 border border-orange-200 px-4 py-3 text-sm text-orange-800"
          role="alert"
        >
          <strong>Notice:</strong> Stock data may be over 24 hours old. Recommendations are
          based on the last inventory snapshot.
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {suggestions.map((suggestion) => (
          <InventorySuggestionCard key={suggestion.product_id} suggestion={suggestion} />
        ))}
      </div>
    </div>
  );
}
