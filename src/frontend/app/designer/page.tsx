import { Suspense } from 'react';
import { Breadcrumb } from '../../components/Shell/Breadcrumb';
import { ModeSelectorTabs } from '../../components/Designer/ModeSelectorTabs';
import type { InventorySuggestion } from '../../../shared/types/offer-brief';
import { SERVER_API_BASE } from '../../lib/config';

// Demo inventory suggestions for fallback/development
const DEMO_SUGGESTIONS: InventorySuggestion[] = [
  {
    product_id: 'P002',
    product_name: 'Duracell AA Batteries 20-Pack',
    category: 'electronics',
    store: 'Canadian Tire',
    units_in_stock: 580,
    urgency: 'high',
    suggested_objective:
      'Drive clearance of Duracell AA Batteries 20-Pack (580 units, 30% off recommended) at Canadian Tire before season end — target active seniors and long-tenure CTC Triangle Rewards members within 5 km of store who purchase seasonal and home-care categories regularly',
    stale: false,
  },
  {
    product_id: 'P016',
    product_name: 'Ergonomic Snow Shovel — Curved Handle',
    category: 'snow_removal',
    store: 'Canadian Tire',
    units_in_stock: 650,
    urgency: 'high',
    suggested_objective:
      'Drive clearance of Ergonomic Snow Shovel — Curved Handle (650 units, 30% off recommended) at Canadian Tire before season end — target active seniors and long-tenure CTC Triangle Rewards members within 5 km of store who purchase seasonal and home-care categories regularly',
    stale: false,
  },
  {
    product_id: 'P012',
    product_name: 'Arctic Cat Snow Blower 24"',
    category: 'snow_removal',
    store: 'Canadian Tire',
    units_in_stock: 560,
    urgency: 'high',
    suggested_objective:
      'Drive clearance of Arctic Cat Snow Blower 24" (560 units, 30% off recommended) at Canadian Tire before season end — target active seniors and long-tenure CTC Triangle Rewards members within 5 km of store who purchase seasonal and home-care categories regularly',
    stale: false,
  },
  {
    product_id: 'P004',
    product_name: 'Pennzoil 5W-30 Full Synthetic 5L',
    category: 'automotive',
    store: 'Canadian Tire',
    units_in_stock: 540,
    urgency: 'high',
    suggested_objective:
      'Drive clearance of Pennzoil 5W-30 Full Synthetic 5L (540 units, 30% off recommended) at Canadian Tire before season end — target active seniors and long-tenure CTC Triangle Rewards members within 5 km of store who purchase seasonal and home-care categories regularly',
    stale: false,
  },
];

async function fetchInventorySuggestions(): Promise<InventorySuggestion[]> {
  try {
    const token = process.env.MARKETER_JWT;
    if (!token) {
      console.warn('MARKETER_JWT not set, using demo suggestions');
      return DEMO_SUGGESTIONS;
    }
    const response = await fetch(`${SERVER_API_BASE}/api/designer/suggestions?limit=6`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      next: { revalidate: 300 },
    });
    if (!response.ok) {
      console.warn(`Suggestions fetch failed: ${response.status}, using demo data`);
      return DEMO_SUGGESTIONS;
    }
    return response.json();
  } catch (error) {
    console.warn('Suggestions fetch error:', error, 'using demo data');
    return DEMO_SUGGESTIONS;
  }
}

async function DesignerContent({
  initialObjective,
  initialSourceProductId,
}: {
  initialObjective?: string;
  initialSourceProductId?: string;
}) {
  const suggestions = await fetchInventorySuggestions();
  return (
    <ModeSelectorTabs
      suggestions={suggestions}
      initialObjective={initialObjective}
      initialSourceProductId={initialSourceProductId}
    />
  );
}

export default async function DesignerPage({
  searchParams,
}: {
  searchParams: Promise<{ objective?: string; sourceProductId?: string }>;
}) {
  const { objective: initialObjective, sourceProductId: initialSourceProductId } = await searchParams;
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
        <DesignerContent
          initialObjective={initialObjective}
          initialSourceProductId={initialSourceProductId}
        />
      </Suspense>
    </>
  );
}
