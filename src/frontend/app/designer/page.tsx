import { Suspense } from 'react';
import { Breadcrumb } from '../../components/Shell/Breadcrumb';
import { ModeSelectorTabs } from '../../components/Designer/ModeSelectorTabs';
import type { InventorySuggestion } from '../../../shared/types/offer-brief';
import { SERVER_API_BASE } from '../../lib/config';

async function fetchInventorySuggestions(): Promise<InventorySuggestion[]> {
  try {
    const response = await fetch(`${SERVER_API_BASE}/api/designer/suggestions?limit=20`, {
      headers: {
        Authorization: `Bearer ${process.env.MARKETER_JWT ?? ''}`,
      },
      next: { revalidate: 300 },
    });
    if (!response.ok) return [];
    return response.json();
  } catch {
    return [];
  }
}

async function fetchExistingOfferObjectives(): Promise<string[]> {
  try {
    const res = await fetch(`${SERVER_API_BASE}/api/hub/offers`, {
      headers: { Authorization: `Bearer ${process.env.MARKETER_JWT ?? ''}` },
      next: { revalidate: 0 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return ((data.offers ?? []) as Array<{ objective: string }>).map((o) => o.objective);
  } catch {
    return [];
  }
}

async function DesignerContent({ initialObjective }: { initialObjective?: string }) {
  const [suggestions, existingObjectives] = await Promise.all([
    fetchInventorySuggestions(),
    fetchExistingOfferObjectives(),
  ]);
  return (
    <ModeSelectorTabs
      suggestions={suggestions}
      initialObjective={initialObjective}
      existingObjectives={existingObjectives}
    />
  );
}

export default async function DesignerPage({
  searchParams,
}: {
  searchParams: Promise<{ objective?: string }>;
}) {
  const { objective: initialObjective } = await searchParams;
  return (
    <>
      <Breadcrumb
        items={['TriStar', 'Designer']}
        trailing={
          <span className="flex items-center gap-1.5 text-gray-400">
            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">
              auto_awesome
            </span>
            Powered by Claude AI
          </span>
        }
      />

      <div className="mb-6">
        <h1 className="text-headline text-gray-900">Marketer Copilot</h1>
        <p className="mt-1 text-sm text-gray-500 max-w-xl">
          Generate Triangle Rewards offers from business objectives or inventory signals.
        </p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-4 mb-6 text-xs text-gray-400">
        <span className="flex items-center gap-1.5">
          <span className="flex items-center justify-center w-5 h-5 rounded-full bg-ct-red text-white text-[10px] font-bold">1</span>
          <span className="text-gray-700 font-medium">Generate</span>
        </span>
        <span className="w-8 h-px bg-gray-200" />
        <span className="flex items-center gap-1.5">
          <span className="flex items-center justify-center w-5 h-5 rounded-full bg-gray-200 text-gray-500 text-[10px] font-bold">2</span>
          Review & Adjust
        </span>
        <span className="w-8 h-px bg-gray-200" />
        <span className="flex items-center gap-1.5">
          <span className="flex items-center justify-center w-5 h-5 rounded-full bg-gray-200 text-gray-500 text-[10px] font-bold">3</span>
          Approve to Hub
        </span>
      </div>

      <Suspense
        fallback={
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-ct-red border-t-transparent" />
              <p className="mt-3 text-sm text-gray-400">Loading inventory signals...</p>
            </div>
          </div>
        }
      >
        <DesignerContent initialObjective={initialObjective} />
      </Suspense>
    </>
  );
}
