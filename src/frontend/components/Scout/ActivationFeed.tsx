'use client';

import { useEffect, useState } from 'react';
import type { ActivationLogEntry } from '@/lib/scout-api';
import { fetchActivationLog } from '@/lib/scout-api';

const OUTCOME_STYLES: Record<string, string> = {
  activated: 'badge-success',
  queued: 'badge-warning',
  rate_limited: 'badge-danger',
  error: 'badge-neutral',
};

interface ActivationFeedProps {
  memberId: string;
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
        // network failure — leave existing entries
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
      <div className="card p-4 text-sm text-gray-400">
        Loading activation history...
      </div>
    );
  }

  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-3 bg-surface-low">
        <h3 className="text-sm font-semibold text-gray-700">
          Activation History
        </h3>
      </div>
      <ul className="divide-y divide-gray-50">
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
    <li className="flex items-center justify-between px-5 py-2.5 text-sm">
      <div className="flex items-center gap-3 min-w-0">
        <span
          className={`badge ${OUTCOME_STYLES[entry.outcome] ?? 'badge-neutral'} capitalize text-[10px]`}
        >
          {entry.outcome.replace('_', ' ')}
        </span>
        <code className="text-xs text-gray-400 font-mono truncate">{entry.offer_id}</code>
      </div>
      <div className="flex items-center gap-3 shrink-0 ml-4">
        <span className="text-sm font-medium text-gray-700">{entry.score.toFixed(1)}</span>
        <span className="text-xs text-gray-400">{entry.scoring_method}</span>
        <span className="text-xs text-gray-400">{ts}</span>
      </div>
    </li>
  );
}
