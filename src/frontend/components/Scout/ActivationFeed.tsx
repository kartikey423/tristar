'use client';

/**
 * ActivationFeed — shows the last N Scout activation records for a member.
 *
 * Client Component: re-fetches when memberId or refreshTrigger changes.
 * Calls GET /api/scout/activation-log/<member_id> via fetchActivationLog().
 */

import { useEffect, useState } from 'react';
import type { ActivationLogEntry } from '@/lib/scout-api';
import { fetchActivationLog } from '@/lib/scout-api';

const OUTCOME_STYLES: Record<string, string> = {
  activated: 'bg-green-100 text-green-700',
  queued: 'bg-yellow-100 text-yellow-700',
  rate_limited: 'bg-red-100 text-red-700',
  error: 'bg-gray-100 text-gray-600',
};

interface ActivationFeedProps {
  memberId: string;
  /** Increment / change to trigger a re-fetch (e.g., pass the latest result). */
  refreshTrigger?: unknown;
}

export function ActivationFeed({ memberId, refreshTrigger }: ActivationFeedProps) {
  const [entries, setEntries] = useState<ActivationLogEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const data = await fetchActivationLog(memberId);
        if (!cancelled) setEntries(data);
      } catch {
        // network failure — leave existing entries, clear loading
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [memberId, refreshTrigger]);

  if (loading && entries.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4 text-sm text-gray-500">
        Loading activation history…
      </div>
    );
  }

  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100">
        <h3 className="text-sm font-semibold text-gray-700">
          Activation History — {memberId}
        </h3>
      </div>
      <ul className="divide-y divide-gray-100">
        {entries.map((entry) => (
          <ActivationRow key={`${entry.offer_id}-${entry.timestamp}`} entry={entry} />
        ))}
      </ul>
    </div>
  );
}

function ActivationRow({ entry }: { entry: ActivationLogEntry }) {
  const ts = new Date(entry.timestamp).toLocaleString('en-CA', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <li className="flex items-center justify-between px-5 py-3 text-sm">
      <div className="flex items-center gap-3 min-w-0">
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium capitalize ${OUTCOME_STYLES[entry.outcome] ?? 'bg-gray-100 text-gray-600'}`}
        >
          {entry.outcome.replace('_', ' ')}
        </span>
        <span className="truncate text-gray-700 font-mono text-xs">{entry.offer_id}</span>
      </div>
      <div className="flex items-center gap-3 shrink-0 ml-4">
        <span className="text-gray-500">{entry.score.toFixed(1)}</span>
        <span className="text-xs text-gray-400">{entry.scoring_method}</span>
        <span className="text-xs text-gray-400">{ts}</span>
      </div>
    </li>
  );
}
