'use server';

import { redirect } from 'next/navigation';
import type { OfferBrief } from '../../../shared/types/offer-brief';
import { GenerateOfferInputSchema } from '../../../shared/types/offer-brief';
import { SERVER_API_BASE } from '../../lib/config';

function getServiceHeaders(): HeadersInit {
  return {
    'Content-Type': 'application/json',
    // In production: read from server-side session/cookie
    Authorization: `Bearer ${process.env.MARKETER_JWT ?? ''}`,
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
  offer: OfferBrief,
): Promise<{ success: true; message: string } | { success: false; error: string }> {
  try {
    const response = await fetch(`${SERVER_API_BASE}/api/designer/approve/${offerId}`, {
      method: 'POST',
      headers: getServiceHeaders(),
      body: JSON.stringify(offer),
    });

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = (body as Record<string, unknown>)?.detail;
      const error =
        typeof detail === 'string' && detail.length < 200
          ? detail
          : 'Offer approval failed. Please try again.';
      return { success: false, error };
    }

    return { success: true, message: 'Offer saved to Hub' };
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
  redirect(`/designer?objective=${encodeURIComponent(objective)}`);
}
