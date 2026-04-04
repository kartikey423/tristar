/**
 * Designer API client — typed HTTP calls to the TriStar FastAPI backend.
 *
 * All functions include the JWT Bearer token from storage and throw typed
 * errors for 401, 403, 422, and 503 response codes.
 */

import type { GenerateOfferInput, InventorySuggestion, OfferBrief } from '../../shared/types/offer-brief';

// ─── Error Types ──────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public statusCode: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class AuthError extends ApiError {
  constructor(message = 'Authentication required') {
    super(401, message);
    this.name = 'AuthError';
  }
}

export class ForbiddenError extends ApiError {
  constructor(message = 'Insufficient permissions') {
    super(403, message);
    this.name = 'ForbiddenError';
  }
}

export class FraudBlockedError extends ApiError {
  constructor(
    public severity: string,
    public warnings: string[],
    public offerId?: string,
  ) {
    super(422, `Offer blocked: ${severity} fraud risk`);
    this.name = 'FraudBlockedError';
  }
}

export class ServiceUnavailableError extends ApiError {
  constructor(message = 'Service temporarily unavailable') {
    super(503, message);
    this.name = 'ServiceUnavailableError';
  }
}

// ─── Token Management ─────────────────────────────────────────────────────────

function getAuthToken(): string | null {
  if (typeof document === 'undefined') return null;
  // Use httpOnly cookie in production; localStorage for dev convenience
  // In production, the token should be set as an httpOnly cookie by the auth flow
  return localStorage.getItem('tristar_token');
}

function buildHeaders(contentType = true): HeadersInit {
  const headers: Record<string, string> = {};
  if (contentType) {
    headers['Content-Type'] = 'application/json';
  }
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// ─── Response Handler ─────────────────────────────────────────────────────────

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return response.json() as Promise<T>;
  }

  let errorBody: unknown;
  const rawText = await response.text();
  try {
    errorBody = JSON.parse(rawText);
  } catch {
    errorBody = rawText;
  }

  switch (response.status) {
    case 401:
      throw new AuthError();
    case 403:
      throw new ForbiddenError();
    case 422: {
      const detail = (errorBody as Record<string, unknown>)?.detail ?? errorBody;
      if (typeof detail === 'object' && detail !== null && 'error' in detail) {
        const d = detail as Record<string, unknown>;
        if (d.error === 'FraudBlocked') {
          throw new FraudBlockedError(
            d.severity as string,
            d.warnings as string[],
            d.offer_id as string | undefined,
          );
        }
      }
      throw new ApiError(422, 'Validation error', detail);
    }
    case 503:
      throw new ServiceUnavailableError();
    default:
      throw new ApiError(response.status, `API error ${response.status}`, errorBody);
  }
}

// ─── API Client ───────────────────────────────────────────────────────────────

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

/**
 * Generate an OfferBrief from a marketer's objective.
 * Returns a draft offer with risk_flags attached.
 */
export async function generateOffer(
  objective: string,
  segmentHints?: string[],
): Promise<OfferBrief> {
  const body: GenerateOfferInput = { objective, segment_hints: segmentHints };
  const response = await fetch(`${BASE_URL}/api/designer/generate`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(body),
  });
  return handleResponse<OfferBrief>(response);
}

/**
 * Approve a draft offer — saves to Hub with status=approved.
 */
export async function approveOffer(
  offerId: string,
  offer: OfferBrief,
): Promise<{ offer_id: string; status: string; hub_saved: boolean; message: string }> {
  const response = await fetch(`${BASE_URL}/api/designer/approve/${offerId}`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(offer),
  });
  return handleResponse(response);
}

/**
 * Fetch AI-driven inventory suggestions for offer creation.
 */
export async function getInventorySuggestions(limit?: number): Promise<InventorySuggestion[]> {
  const params = limit !== undefined ? `?limit=${limit}` : '';
  const response = await fetch(`${BASE_URL}/api/designer/suggestions${params}`, {
    method: 'GET',
    headers: buildHeaders(false),
  });
  return handleResponse<InventorySuggestion[]>(response);
}

/**
 * Generate a purchase-triggered offer (system use — called by Scout internally).
 * Exposed here for testing/demo purposes.
 */
export async function generateFromPurchaseContext(ctx: {
  member_id: string;
  event_id: string;
  purchase_amount: number;
  store_name: string;
  context_score: number;
}): Promise<OfferBrief> {
  const response = await fetch(`${BASE_URL}/api/designer/generate-purchase`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(ctx),
  });
  return handleResponse<OfferBrief>(response);
}
