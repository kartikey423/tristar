'use client';

/**
 * ModeSelectorTabs — Client Component.
 *
 * Tab switcher with useState<'ai' | 'manual'>.
 * Renders AISuggestionsPanel (server-fetched suggestions passed as props)
 * or ManualEntryForm based on active mode.
 */

import { useState } from 'react';
import type { InventorySuggestion } from '../../../shared/types/offer-brief';
import { AISuggestionsPanel } from './AISuggestionsPanel';
import { ManualEntryForm } from './ManualEntryForm';

interface ModeSelectorTabsProps {
  suggestions: InventorySuggestion[];
  initialObjective?: string;
}

type Mode = 'ai' | 'manual';

const TABS: { id: Mode; label: string; description: string }[] = [
  {
    id: 'ai',
    label: 'AI Suggestions',
    description: 'Review inventory-driven offer recommendations',
  },
  {
    id: 'manual',
    label: 'Manual Entry',
    description: 'Enter a custom marketing objective',
  },
];

export function ModeSelectorTabs({ suggestions, initialObjective }: ModeSelectorTabsProps) {
  const [mode, setMode] = useState<Mode>(initialObjective ? 'manual' : 'ai');

  return (
    <div className="space-y-6">
      {/* Tab navigation */}
      <div
        className="flex gap-1 rounded-lg bg-gray-100 p-1"
        role="tablist"
        aria-label="Offer creation mode"
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={mode === tab.id}
            aria-controls={`panel-${tab.id}`}
            onClick={() => setMode(tab.id)}
            className={`flex-1 rounded-md px-4 py-2.5 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset ${
              mode === tab.id
                ? 'bg-white text-blue-700 shadow-sm border-b-2 border-blue-600'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab description */}
      <p className="text-sm text-gray-500">
        {TABS.find((t) => t.id === mode)?.description}
      </p>

      {/* Tab panels */}
      <div
        id={`panel-ai`}
        role="tabpanel"
        aria-labelledby="tab-ai"
        hidden={mode !== 'ai'}
      >
        <AISuggestionsPanel suggestions={suggestions} />
      </div>

      <div
        id={`panel-manual`}
        role="tabpanel"
        aria-labelledby="tab-manual"
        hidden={mode !== 'manual'}
      >
        <ManualEntryForm initialObjective={initialObjective} />
      </div>
    </div>
  );
}
