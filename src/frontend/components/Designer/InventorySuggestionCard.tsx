/**
 * InventorySuggestionCard — Server Component.
 * F-010 FIX: Added to Component Catalogue as COMP-024b.
 *
 * Displays a single AI-derived inventory suggestion with urgency badge
 * and a "Use This Objective" button that pre-fills ManualEntryForm.
 */

import type { InventorySuggestion } from '../../../shared/types/offer-brief';
import { prefillObjectiveAction } from '../../app/designer/actions';

interface InventorySuggestionCardProps {
  suggestion: InventorySuggestion;
}

const URGENCY_STYLES: Record<string, string> = {
  high: 'bg-red-100 text-red-800',
  medium: 'bg-yellow-100 text-yellow-800',
  low: 'bg-gray-100 text-gray-700',
};

const URGENCY_LABELS: Record<string, string> = {
  high: 'Urgent',
  medium: 'Moderate',
  low: 'Low',
};

export function InventorySuggestionCard({ suggestion }: InventorySuggestionCardProps) {
  const urgencyStyle = URGENCY_STYLES[suggestion.urgency] ?? URGENCY_STYLES.medium;
  const urgencyLabel = URGENCY_LABELS[suggestion.urgency] ?? suggestion.urgency;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-gray-900">{suggestion.product_name}</h3>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${urgencyStyle}`}
              aria-label={`Urgency: ${urgencyLabel}`}
            >
              {urgencyLabel}
            </span>
            {suggestion.stale && (
              <span
                className="rounded-full bg-orange-100 px-2 py-0.5 text-xs text-orange-700"
                title="Stock data may be outdated"
              >
                Stale data
              </span>
            )}
          </div>

          <p className="mt-1 text-sm text-gray-500">
            {suggestion.store} · {suggestion.category} · {suggestion.units_in_stock.toLocaleString()} units
          </p>

          <p className="mt-3 text-sm text-gray-700 italic">
            &ldquo;{suggestion.suggested_objective}&rdquo;
          </p>
        </div>
      </div>

      {/* "Use This Objective" — redirects to /designer?objective=... to pre-fill ManualEntryForm */}
      <form className="mt-4" action={prefillObjectiveAction}>
        <input type="hidden" name="objective" value={suggestion.suggested_objective} />
        <button
          type="submit"
          className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          aria-label={`Use objective: ${suggestion.suggested_objective}`}
        >
          Use This Objective
        </button>
      </form>
    </div>
  );
}
