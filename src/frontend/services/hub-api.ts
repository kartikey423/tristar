/**
 * Hub API client — server-side typed HTTP calls for Hub offer state.
 *
 * COMP-014: Used by Server Components and Server Actions only (no 'use client').
 * F-003 FIX: Uses MARKETER_JWT env var via getAuthHeaders() — NOT HUB_SERVICE_TOKEN.
 *
 * next: { revalidate: 0 } ensures fresh SSR data on every request.
 */

import type { OfferBrief } from '@/../../shared/types/offer-brief';
import { SERVER_API_BASE, getAuthHeaders } from '@/lib/config';

export interface FetchOffersParams {
  status?: string;
  trigger_type?: string;
  since?: string;
}

export interface ListOffersResponse {
  offers: OfferBrief[];
  count: number;
}

/**
 * Fetch all offers from Hub with optional filters.
 * Called from Server Components — uses NODE_ENV auth via MARKETER_JWT.
 */
export async function fetchOffers(params: FetchOffersParams = {}): Promise<ListOffersResponse> {
  const url = new URL(`${SERVER_API_BASE}/api/hub/offers`);

  if (params.status) url.searchParams.set('status', params.status);
  if (params.trigger_type) url.searchParams.set('trigger_type', params.trigger_type);
  if (params.since) url.searchParams.set('since', params.since);

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    next: { revalidate: 0 }, // Always fresh — no caching for Hub state
  });

  if (!response.ok) {
    throw new Error(`Hub fetchOffers failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<ListOffersResponse>;
}

/**
 * Fetch a single offer by ID from Hub.
 */
export async function fetchOffer(offerId: string): Promise<OfferBrief> {
  const response = await fetch(`${SERVER_API_BASE}/api/hub/offers/${offerId}`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    next: { revalidate: 0 },
  });

  if (response.status === 404) {
    throw new Error(`Offer ${offerId} not found`);
  }

  if (!response.ok) {
    throw new Error(`Hub fetchOffer failed: ${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<OfferBrief>;
}
