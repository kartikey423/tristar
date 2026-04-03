import { Breadcrumb } from '@/components/Shell/Breadcrumb';
import { ContextDashboard } from '@/components/Scout/ContextDashboard';

export const metadata = {
  title: 'Scout — TriStar Real-Time Activation',
};

export default function ScoutPage() {
  return (
    <>
      <Breadcrumb
        items={['TriStar', 'Scout']}
        trailing={
          <span className="badge badge-info">
            Activation threshold: Score &gt; 60
          </span>
        }
      />

      <div className="mb-6">
        <h1 className="text-headline text-gray-900">Scout</h1>
        <p className="mt-1 text-sm text-gray-500 max-w-xl">
          Real-time activation engine — simulate a CTC purchase, score context signals
          against Hub-approved offers, and deliver personalised Triangle Rewards notifications.
        </p>
      </div>

      {/* Context signal legend */}
      <div className="flex flex-wrap gap-2 mb-6">
        {[
          { icon: 'location_on', label: 'GPS proximity' },
          { icon: 'calendar_today', label: 'Date & occasion' },
          { icon: 'shopping_cart', label: 'Purchase category' },
          { icon: 'star', label: 'Member tier' },
          { icon: 'sell', label: 'Clearance intel' },
        ].map((signal) => (
          <span
            key={signal.label}
            className="flex items-center gap-1.5 rounded-md bg-surface-low px-2.5 py-1.5 text-xs text-gray-600"
          >
            <span className="material-symbols-outlined text-[14px] text-gray-400" aria-hidden="true">
              {signal.icon}
            </span>
            {signal.label}
          </span>
        ))}
      </div>

      <div className="mx-auto max-w-2xl">
        <ContextDashboard />
      </div>
    </>
  );
}
