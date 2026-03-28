/**
 * Scout page — Server Component shell.
 *
 * Renders the ContextDashboard Client Component for the demo.
 * REQ-007 / AC-019: ContextDashboard with 5 demo member presets and
 * preset location dropdowns (no raw GPS input in production UI).
 */

import { ContextDashboard } from '@/components/Scout/ContextDashboard';

export const metadata = {
  title: 'Scout — TriStar Activation Engine',
};

export default function ScoutPage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-8 space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">Scout</h1>
        <p className="mt-1 text-sm text-gray-500">
          Real-time context matching — score Hub-approved offers against purchase signals.
        </p>
      </header>

      <ContextDashboard />
    </main>
  );
}
