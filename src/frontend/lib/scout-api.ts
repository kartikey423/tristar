/**
 * Scout API client — typed HTTP calls for POST /api/scout/match.
 *
 * Runs in Client Components (browser fetch) and Server Actions.
 * No auth headers required: Scout match is an unauthenticated endpoint for demo.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

// ── Request / Response types (mirrors src/backend/models/scout_match.py) ──────

export interface GeoPoint {
  lat: number;
  lon: number;
}

export type DayContext = 'weekday' | 'weekend' | 'long_weekend';
export type ScoutOutcome = 'activated' | 'queued' | 'rate_limited';
export type ScoringMethod = 'claude' | 'fallback' | 'cached';

export interface MatchRequest {
  member_id: string;
  purchase_location: GeoPoint;
  purchase_category?: string;
  rewards_earned?: number;
  day_context?: DayContext;
  weather_condition?: string;
}

export interface MatchResponse {
  score: number;
  rationale: string;
  notification_text: string;
  offer_id: string;
  outcome: ScoutOutcome;
  scoring_method: ScoringMethod;
  queued?: boolean;
  delivery_time?: string;
  retry_after_seconds?: number;
}

export interface NoMatchResponse {
  matches: unknown[];
  message: string;
}

export type ScoutMatchResult = MatchResponse | NoMatchResponse;

/** Type guard — true when a match was found (activated / queued / rate_limited). */
export function isMatchResponse(result: ScoutMatchResult): result is MatchResponse {
  return 'offer_id' in result;
}

// ── API function ───────────────────────────────────────────────────────────────

export interface ScoutMatchError {
  status: number;
  detail: string;
}

/**
 * Call POST /api/scout/match and return the result.
 * Throws ScoutMatchError on HTTP error responses.
 */
export async function callScoutMatch(request: MatchRequest): Promise<ScoutMatchResult> {
  const url = `${API_BASE}/api/scout/match`;

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore parse error — use statusText
    }
    const err: ScoutMatchError = { status: res.status, detail };
    throw err;
  }

  return (await res.json()) as ScoutMatchResult;
}

// ── Partner trigger ────────────────────────────────────────────────────────────

export interface PartnerPurchaseEvent {
  event_id: string;
  partner_id: string;
  partner_name: string;
  purchase_amount: number;
  purchase_category: string;
  member_id: string;
  timestamp: string;
  location?: GeoPoint;
  store_name?: string;
}

export interface PartnerTriggerApiResponse {
  status: string;
  message: string;
  offer_id?: string | null;
}

/**
 * POST /api/scout/partner-trigger — send a partner purchase event.
 * Returns 202 immediately; offer generation happens in background.
 */
export async function callPartnerTrigger(
  event: PartnerPurchaseEvent,
): Promise<PartnerTriggerApiResponse> {
  const url = `${API_BASE}/api/scout/partner-trigger`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(event),
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw { status: res.status, detail } as ScoutMatchError;
  }

  return res.json() as Promise<PartnerTriggerApiResponse>;
}

// ── Customer notification acceptance — auto-approve offer ─────────────────────

/**
 * Customer tapped "View Offer →" on their phone notification.
 * Calls the Next.js server-side proxy which forwards to the backend using API_URL.
 * Routing through the proxy ensures all developers hit the same shared backend
 * regardless of whether NEXT_PUBLIC_API_URL is configured on their machine.
 */
export async function customerAcceptOffer(offerId: string): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`/api/hub-accept/${encodeURIComponent(offerId)}`, {
    method: 'POST',
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch { /* ignore */ }
    return { success: false, message: detail };
  }

  return { success: true, message: 'Offer accepted and activated!' };
}

// ── Activation log entry (from GET /api/scout/activation-log) ─────────────────

export interface ActivationLogEntry {
  member_id: string;
  offer_id: string;
  score: number;
  scoring_method: ScoringMethod;
  outcome: string;
  timestamp: string;
}

export async function fetchActivationLog(memberId: string): Promise<ActivationLogEntry[]> {
  const url = `${API_BASE}/api/scout/activation-log/${encodeURIComponent(memberId)}`;
  const res = await fetch(url, { next: { revalidate: 0 } });
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}
