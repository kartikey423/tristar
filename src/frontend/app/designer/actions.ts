'use server';

import { redirect } from 'next/navigation';
import type { OfferBrief } from '../../../shared/types/offer-brief';
import { GenerateOfferInputSchema } from '../../../shared/types/offer-brief';
import { SERVER_API_BASE } from '../../lib/config';

function getServiceHeaders(): HeadersInit {
  // Ensure token is read from environment
  let token = process.env.MARKETER_JWT;

  // Fallback: use hardcoded dev token if env var is not set
  // This token has 'marketing' role: {'sub': 'marketer-demo', 'role': 'marketing'}
  if (!token) {
    token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJtYXJrZXRlci1kZW1vIiwicm9sZSI6Im1hcmtldGluZyJ9.AIro1O38GcdY4sFzsvVwm-OJ7qosv1Q9f13vkxaDGGY';
    console.warn('⚠️  MARKETER_JWT env var not set, using fallback dev token');
  }

  console.log('🔐 Using authorization token');

  return {
    'Content-Type': 'application/json',
    // In production: read from server-side session/cookie
    Authorization: `Bearer ${token}`,
  };
}

export async function generateOfferAction(
  formData: FormData,
): Promise<{ success: true; offer: OfferBrief } | { success: false; error: string }> {
  const raw = {
    objective: formData.get('objective') as string,
    segment_hints: formData.get('segment_hints')
      ? (formData.get('segment_hints') as string).split(',').map((s) => s.trim())
      : undefined,
  };

  const parsed = GenerateOfferInputSchema.safeParse(raw);
  if (!parsed.success) {
    const first = parsed.error.errors[0];
    return { success: false, error: first.message };
  }

  try {
    const response = await fetch(`${SERVER_API_BASE}/api/designer/generate`, {
      method: 'POST',
      headers: getServiceHeaders(),
      body: JSON.stringify(parsed.data),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = (body as Record<string, unknown>)?.detail;

      // Specific handling for authentication errors
      if (response.status === 401) {
        console.error('❌ Authentication failed (401):', detail);
        console.error('   MARKETER_JWT:', process.env.MARKETER_JWT ? 'SET' : 'NOT SET');
        return {
          success: false,
          error: 'Authentication failed. The JWT token may be invalid or expired. Please check the configuration.'
        };
      }

      if (response.status === 403) {
        console.error('❌ Permission denied (403):', detail);
        return {
          success: false,
          error: 'Permission denied. User role may not be authorized for offer generation.'
        };
      }

      // Return only known safe string messages; reject complex error objects
      const error =
        typeof detail === 'string' && detail.length < 200
          ? detail
          : 'Offer generation failed. Please try again.';
      return { success: false, error };
    }

    const offer = (await response.json()) as OfferBrief;
    return { success: true, offer };
  } catch (error) {
    return { success: false, error: 'Failed to connect to TriStar API. Please try again.' };
  }
}

export async function approveOfferAction(
  offerId: string,
): Promise<{ success: true; message: string } | { success: false; error: string }> {
  try {
    const response = await fetch(`${SERVER_API_BASE}/api/designer/approve/${offerId}`, {
      method: 'POST',
      headers: getServiceHeaders(),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = (body as Record<string, unknown>)?.detail;

      // Specific handling for authentication errors
      if (response.status === 401) {
        console.error('❌ Authentication failed (401):', detail);
        return {
          success: false,
          error: 'Authentication failed. Please ensure the API is properly configured.'
        };
      }

      if (response.status === 403) {
        console.error('❌ Permission denied (403):', detail);
        return {
          success: false,
          error: 'Permission denied. User may not be authorized to approve offers.'
        };
      }

      const error =
        typeof detail === 'string' && detail.length < 200
          ? detail
          : 'Offer approval failed. Please try again.';
      return { success: false, error };
    }

    return { success: true, message: 'Offer saved to Hub' };
  } catch (error) {
    console.error('Error in approveOfferAction:', error);
    return { success: false, error: 'Failed to connect to TriStar API. Please try again.' };
  }
}

export async function rejectOfferAction(
  offerId: string,
): Promise<{ success: true } | { success: false; error: string }> {
  try {
    const response = await fetch(`${SERVER_API_BASE}/api/hub/offers/${offerId}`, {
      method: 'DELETE',
      headers: getServiceHeaders(),
    });

    if (!response.ok && response.status !== 204) {
      const body = await response.json().catch(() => ({}));
      const detail = (body as Record<string, unknown>)?.detail;
      const error =
        typeof detail === 'string' && detail.length < 200
          ? detail
          : 'Failed to reject offer. Please try again.';
      return { success: false, error };
    }

    return { success: true };
  } catch {
    return { success: false, error: 'Failed to connect to TriStar API. Please try again.' };
  }
}

export async function updateConstructValueAction(
  offerId: string,
  value: number,
): Promise<{ success: true } | { success: false; error: string }> {
  try {
    const response = await fetch(`${SERVER_API_BASE}/api/hub/offers/${offerId}/construct`, {
      method: 'PATCH',
      headers: getServiceHeaders(),
      body: JSON.stringify({ value }),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = (body as Record<string, unknown>)?.detail;
      const error =
        typeof detail === 'string' && detail.length < 200
          ? detail
          : 'Failed to update discount. Please try again.';
      return { success: false, error };
    }

    return { success: true };
  } catch {
    return { success: false, error: 'Failed to connect to TriStar API. Please try again.' };
  }
}

/**
 * Pre-fill the ManualEntryForm with a suggested objective from InventorySuggestionCard.
 * Redirects to /designer?objective=... so the page picks up the value via searchParams.
 */
export async function prefillObjectiveAction(formData: FormData): Promise<never> {
  const objective = (formData.get('objective') as string | null) ?? '';
  const sourceProductId = (formData.get('source_product_id') as string | null) ?? '';

  const params = new URLSearchParams({ objective });
  if (sourceProductId) {
    params.set('sourceProductId', sourceProductId);
  }

  redirect(`/designer?${params.toString()}`);
}
