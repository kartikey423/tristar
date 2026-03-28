'use server';

/**
 * COMP-013: Server Actions for Hub offer management.
 *
 * F-002 FIX: Uses getAuthHeaders() with MARKETER_JWT (consistent with designer pattern).
 * Called from ApproveButton Client Component via useTransition.
 */

import { SERVER_API_BASE, getAuthHeaders } from '../../lib/config';

/**
 * Approve a draft offer — transitions it from draft → approved in Hub.
 * Calls PUT /api/hub/offers/{id}/status?new_status=approved.
 */
export async function approveOffer(
  offerId: string,
): Promise<{ success: true; message: string } | { success: false; error: string }> {
  try {
    const response = await fetch(
      `${SERVER_API_BASE}/api/hub/offers/${offerId}/status?new_status=approved`,
      {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(),
        },
      },
    );

    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const detail = (body as Record<string, unknown>)?.detail;
      const error =
        typeof detail === 'string' && detail.length < 200
          ? detail
          : `Approval failed (${response.status})`;
      return { success: false, error };
    }

    return { success: true, message: 'Offer approved' };
  } catch {
    return { success: false, error: 'Failed to connect to Hub API' };
  }
}
