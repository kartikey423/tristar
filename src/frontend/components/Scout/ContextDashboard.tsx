'use client';

/**
 * ContextDashboard — interactive Scout demo panel.
 *
 * Client Component: form state, fetch, and dynamic result rendering.
 * Members and preset locations are hardcoded for demo (REQ-008 / AC-019).
 * Calls POST /api/scout/match via callScoutMatch().
 */

import { useState } from 'react';
import type {
  MatchRequest,
  ScoutMatchResult,
  ScoutMatchError,
} from '@/lib/scout-api';
import { callScoutMatch, isMatchResponse } from '@/lib/scout-api';
import { ActivationFeed } from './ActivationFeed';

// ── Demo data ──────────────────────────────────────────────────────────────────

const DEMO_MEMBERS = [
  { id: 'demo-001', label: 'demo-001 — Outdoor/Gold (high score)' },
  { id: 'demo-002', label: 'demo-002 — Urban Commuter/Silver' },
  { id: 'demo-003', label: 'demo-003 — Seasonal Home/Standard' },
  { id: 'demo-004', label: 'demo-004 — Family Shopper/Platinum' },
  { id: 'demo-005', label: 'demo-005 — Auto Parts/Standard (low score)' },
];

const DEMO_LOCATIONS = [
  { label: 'Near Canadian Tire Queen St W', lat: 43.6490, lon: -79.3980 },
  { label: 'Near Sport Chek Eaton Centre', lat: 43.6545, lon: -79.3808 },
  { label: 'Near Marks King St W', lat: 43.6451, lon: -79.4013 },
  { label: 'Mississauga (no nearby store)', lat: 43.5200, lon: -79.7000 },
];

const PURCHASE_CATEGORIES = [
  'food_beverage',
  'general',
  'sporting_goods',
  'apparel',
  'automotive',
  'hardware',
];

const WEATHER_CONDITIONS = [
  { value: '', label: 'Live (API call)' },
  { value: 'clear', label: 'Clear' },
  { value: 'rain', label: 'Rain' },
  { value: 'snow', label: 'Snow' },
  { value: 'cloudy', label: 'Cloudy' },
];

// ── Shared constants ───────────────────────────────────────────────────────────

const OUTCOME_STYLES: Record<string, string> = {
  activated: 'bg-green-100 text-green-800',
  queued: 'bg-yellow-100 text-yellow-800',
  rate_limited: 'bg-red-100 text-red-800',
};

// ── Component ──────────────────────────────────────────────────────────────────

interface FormState {
  memberId: string;
  locationIndex: number;
  purchaseCategory: string;
  rewardsEarned: number;
  dayContext: 'weekday' | 'weekend' | 'long_weekend';
  weatherCondition: string;
}

export function ContextDashboard() {
  const [form, setForm] = useState<FormState>({
    memberId: 'demo-001',
    locationIndex: 0,
    purchaseCategory: 'food_beverage',
    rewardsEarned: 120,
    dayContext: 'weekday',
    weatherCondition: '',
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScoutMatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshCount, setRefreshCount] = useState(0);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setError(null);

    const loc = DEMO_LOCATIONS[form.locationIndex];
    const request: MatchRequest = {
      member_id: form.memberId,
      purchase_location: { lat: loc.lat, lon: loc.lon },
      purchase_category: form.purchaseCategory,
      rewards_earned: form.rewardsEarned,
      day_context: form.dayContext,
      ...(form.weatherCondition ? { weather_condition: form.weatherCondition } : {}),
    };

    try {
      const res = await callScoutMatch(request);
      setResult(res);
      setRefreshCount((c) => c + 1);
    } catch (err) {
      const apiErr = err as ScoutMatchError;
      setError(apiErr?.detail ?? 'Unexpected error contacting Scout API');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* ── Context input form ── */}
      <form
        onSubmit={handleSubmit}
        className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm space-y-4"
      >
        <h2 className="text-lg font-semibold text-gray-900">Context Signals</h2>

        {/* Member */}
        <div>
          <label htmlFor="member" className="block text-sm font-medium text-gray-700 mb-1">
            Member
          </label>
          <select
            id="member"
            value={form.memberId}
            onChange={(e) => setForm({ ...form, memberId: e.target.value })}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {DEMO_MEMBERS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </div>

        {/* Location */}
        <div>
          <label htmlFor="location" className="block text-sm font-medium text-gray-700 mb-1">
            Purchase Location (preset)
          </label>
          <select
            id="location"
            value={form.locationIndex}
            onChange={(e) => setForm({ ...form, locationIndex: Number(e.target.value) })}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {DEMO_LOCATIONS.map((l, i) => (
              <option key={i} value={i}>
                {l.label}
              </option>
            ))}
          </select>
        </div>

        {/* Row: Category + Rewards */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="category"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Purchase Category
            </label>
            <select
              id="category"
              value={form.purchaseCategory}
              onChange={(e) => setForm({ ...form, purchaseCategory: e.target.value })}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {PURCHASE_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label
              htmlFor="rewards"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Rewards Earned (pts)
            </label>
            <input
              id="rewards"
              type="number"
              min={0}
              value={form.rewardsEarned}
              onChange={(e) => setForm({ ...form, rewardsEarned: Number(e.target.value) })}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Row: Day context + Weather */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label
              htmlFor="day"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Day Context
            </label>
            <select
              id="day"
              value={form.dayContext}
              onChange={(e) =>
                setForm({
                  ...form,
                  dayContext: e.target.value as FormState['dayContext'],
                })
              }
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="weekday">Weekday</option>
              <option value="weekend">Weekend</option>
              <option value="long_weekend">Long Weekend</option>
            </select>
          </div>
          <div>
            <label
              htmlFor="weather"
              className="block text-sm font-medium text-gray-700 mb-1"
            >
              Weather Override
            </label>
            <select
              id="weather"
              value={form.weatherCondition}
              onChange={(e) => setForm({ ...form, weatherCondition: e.target.value })}
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {WEATHER_CONDITIONS.map((w) => (
                <option key={w.value} value={w.value}>
                  {w.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {loading ? 'Matching…' : 'Match Offers'}
        </button>
      </form>

      {/* ── Error ── */}
      {error && (
        <div
          role="alert"
          className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
        >
          {error}
        </div>
      )}

      {/* ── Match result ── */}
      {result && <ScoutResultCard result={result} />}

      {/* ── Activation history ── */}
      <ActivationFeed memberId={form.memberId} refreshTrigger={refreshCount} />
    </div>
  );
}

// ── Match result card ──────────────────────────────────────────────────────────

function ScoutResultCard({ result }: { result: ScoutMatchResult }) {
  if (!isMatchResponse(result)) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <p className="text-sm font-medium text-gray-500">No match</p>
        <p className="mt-1 text-gray-700">{result.message}</p>
      </div>
    );
  }

  const scoreColor =
    result.score > 80 ? 'text-green-700' : result.score > 60 ? 'text-yellow-700' : 'text-red-700';

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">Offer {result.offer_id}</h3>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${OUTCOME_STYLES[result.outcome] ?? 'bg-gray-100 text-gray-700'}`}
        >
          {result.outcome.replace('_', ' ')}
        </span>
      </div>

      {/* Score */}
      <div className="flex items-baseline gap-1">
        <span className={`text-3xl font-bold ${scoreColor}`}>{result.score.toFixed(1)}</span>
        <span className="text-sm text-gray-500">/ 100</span>
        <span className="ml-2 text-xs text-gray-400">via {result.scoring_method}</span>
      </div>

      {/* Notification preview */}
      {result.notification_text && (
        <div className="rounded-lg bg-gray-50 border border-gray-100 p-3">
          <p className="text-xs font-medium text-gray-500 mb-1">Push notification</p>
          <p className="text-sm text-gray-800">{result.notification_text}</p>
        </div>
      )}

      {/* Rationale */}
      <p className="text-sm text-gray-600">{result.rationale}</p>

      {/* Extra info */}
      {result.outcome === 'queued' && result.delivery_time && (
        <p className="text-xs text-yellow-700">Queued for delivery at {result.delivery_time} UTC</p>
      )}
      {result.outcome === 'rate_limited' && result.retry_after_seconds != null && (
        <p className="text-xs text-red-700">
          Retry after {Math.ceil(result.retry_after_seconds / 60)} minutes
        </p>
      )}
    </div>
  );
}
