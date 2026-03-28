/**
 * Designer page — Server Component.
 *
 * Fetches inventory suggestions server-side and renders the mode selector.
 * Uses Suspense for loading state while inventory data loads.
 */

import { Suspense } from 'react';
import { ModeSelectorTabs } from '../../components/Designer/ModeSelectorTabs';
import type { InventorySuggestion } from '../../../shared/types/offer-brief';
import { SERVER_API_BASE } from '../../lib/config';

async function fetchInventorySuggestions(): Promise<InventorySuggestion[]> {
  try {
    const response = await fetch(`${SERVER_API_BASE}/api/designer/suggestions?limit=3`, {
      headers: {
        Authorization: `Bearer ${process.env.MARKETER_JWT ?? ''}`,
      },
      next: { revalidate: 300 }, // Cache for 5 minutes
    });
    if (!response.ok) return [];
    return response.json();
  } catch {
    return [];
  }
}

async function DesignerContent({ initialObjective }: { initialObjective?: string }) {
  const suggestions = await fetchInventorySuggestions();
  return <ModeSelectorTabs suggestions={suggestions} initialObjective={initialObjective} />;
}

export default function DesignerPage({
  searchParams,
}: {
  searchParams: { objective?: string };
}) {
  const initialObjective = searchParams.objective;
  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900">Marketer Copilot</h1>
          <p className="mt-2 text-gray-600">
            Generate AI-powered loyalty offers from business objectives or inventory analysis.
          </p>
        </div>

        <Suspense
          fallback={
            <div className="flex items-center justify-center py-16">
              <div className="text-center">
                <div className="mx-auto h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
                <p className="mt-3 text-sm text-gray-500">Loading suggestions...</p>
              </div>
            </div>
          }
        >
          <DesignerContent initialObjective={initialObjective} />
        </Suspense>
      </div>
    </main>
  );
}
