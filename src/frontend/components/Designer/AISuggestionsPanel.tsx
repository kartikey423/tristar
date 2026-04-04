'use client';

import { useState, useEffect, useCallback } from 'react';
import type { InventorySuggestion } from '../../../shared/types/offer-brief';
import { getInventorySuggestions } from '../../services/designer-api';
import { InventorySuggestionCard } from './InventorySuggestionCard';

interface AISuggestionsPanelProps {
  suggestions: InventorySuggestion[];
}

const REFRESH_INTERVAL_S = 60;

export function AISuggestionsPanel({ suggestions: initialSuggestions }: AISuggestionsPanelProps) {
  const [suggestions, setSuggestions] = useState<InventorySuggestion[]>(initialSuggestions);
  const [secondsAgo, setSecondsAgo] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  // Track product_ids that already have an offer generated — disables the Generate button
  const [offeredProductIds, setOfferedProductIds] = useState<Set<string>>(new Set());

  const refresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const fresh = await getInventorySuggestions(20);
      setSuggestions(fresh);
      setSecondsAgo(0);
    } catch {
      // Keep existing suggestions on error
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  // Tick the "seconds ago" counter every second
  useEffect(() => {
    const timer = setInterval(() => {
      setSecondsAgo((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    const timer = setInterval(() => {
      refresh();
    }, REFRESH_INTERVAL_S * 1000);
    return () => clearInterval(timer);
  }, [refresh]);

  const hasStaleData = suggestions.some((s) => s.stale);

  const timeLabel =
    secondsAgo < 5
      ? 'Refreshed just now'
      : secondsAgo < 60
        ? `Refreshed ${secondsAgo}s ago`
        : `Refreshed ${Math.floor(secondsAgo / 60)}m ago`;

  function handleOfferGenerated(productId: string) {
    setOfferedProductIds((prev) => new Set(prev).add(productId));
  }

  if (suggestions.length === 0) {
    return (
      <div className="card border-dashed border-gray-300 p-8 text-center">
        <p className="text-gray-500 text-sm">No overstock items found requiring attention.</p>
        <p className="mt-1 text-xs text-gray-400">
          All inventory levels are within normal thresholds.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-title text-gray-900">
          AI Inventory Recommendations
        </h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-400">
            {suggestions.length} item{suggestions.length !== 1 ? 's' : ''} need attention
          </span>
          <span className="text-[10px] text-gray-400 hidden sm:inline" aria-live="polite">
            {timeLabel}
          </span>
          <button
            type="button"
            onClick={refresh}
            disabled={isRefreshing}
            className="rounded-md border border-gray-300 px-2.5 py-1 text-xs text-gray-600 transition hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-ct-red focus:ring-offset-1 disabled:opacity-50"
            aria-label="Refresh suggestions"
          >
            <span className={isRefreshing ? 'inline-block animate-spin' : ''}>
              {isRefreshing ? '\u21BB' : '\u21BB'}
            </span>
            {' '}Refresh
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2 text-[10px] text-gray-400">
        <span
          className={`inline-block h-1.5 w-1.5 rounded-full ${secondsAgo < 10 ? 'bg-green-400 animate-pulse' : 'bg-gray-300'}`}
        />
        Auto-refreshing every {REFRESH_INTERVAL_S}s
      </div>

      {hasStaleData && (
        <div
          className="card border-l-2 border-amber-500 px-4 py-3 text-sm text-amber-800 bg-amber-50"
          role="alert"
        >
          <strong>Notice:</strong> Stock data may be over 24 hours old. Recommendations are
          based on the last inventory snapshot.
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {suggestions.map((suggestion) => (
          <InventorySuggestionCard
            key={suggestion.product_id}
            suggestion={suggestion}
            isOffered={offeredProductIds.has(suggestion.product_id)}
            onOfferGenerated={handleOfferGenerated}
          />
        ))}
      </div>
    </div>
  );
}
