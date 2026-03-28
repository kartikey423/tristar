'use client';

/**
 * ApproveButton — Client Component.
 *
 * Disabled when risk_flags.severity === 'critical'.
 * Uses useOptimistic for instant status update in the UI.
 * Shows "Saved to Hub" toast on success, error message with retry on failure.
 */

import { startTransition, useOptimistic, useState } from 'react';
import { approveOfferAction } from '../../app/designer/actions';
import type { OfferBrief } from '../../../shared/types/offer-brief';
import { Spinner } from './Spinner';

interface ApproveButtonProps {
  offer: OfferBrief;
}

type ApproveState = 'idle' | 'pending' | 'success' | 'error';

export function ApproveButton({ offer }: ApproveButtonProps) {
  const [state, setState] = useState<ApproveState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const isCritical = offer.risk_flags.severity === 'critical';
  const isAlreadyApproved = offer.status === 'approved' || offer.status === 'active';

  // Optimistic: show "Saved to Hub" immediately, revert on error
  const [optimisticStatus, addOptimistic] = useOptimistic(
    offer.status,
    (_current: string, next: string) => next,
  );

  async function handleApprove() {
    if (isCritical || isAlreadyApproved) return;

    setState('pending');
    startTransition(() => addOptimistic('approved'));

    const result = await approveOfferAction(offer.offer_id, offer);

    if (result.success) {
      setState('success');
    } else {
      setState('error');
      setErrorMessage(result.error);
    }
  }

  if (isAlreadyApproved || optimisticStatus === 'approved') {
    return (
      <div
        className="flex items-center gap-2 rounded-md bg-green-50 border border-green-200 px-4 py-2.5"
        role="status"
        aria-live="polite"
      >
        <span aria-hidden="true">✅</span>
        <span className="text-sm font-medium text-green-700">Saved to Hub</span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={handleApprove}
        disabled={isCritical || state === 'pending'}
        title={isCritical ? 'Critical risk detected — cannot approve' : undefined}
        aria-disabled={isCritical}
        aria-label={isCritical ? 'Cannot approve — critical risk detected' : 'Approve offer and save to Hub'}
        className={`w-full rounded-md px-4 py-2.5 text-sm font-medium transition focus:outline-none focus:ring-2 focus:ring-offset-2 ${
          isCritical
            ? 'cursor-not-allowed bg-gray-100 text-gray-400 border border-gray-200'
            : state === 'pending'
              ? 'cursor-wait bg-green-500 text-white'
              : 'bg-green-600 text-white hover:bg-green-700 focus:ring-green-500'
        }`}
      >
        {state === 'pending' ? (
          <span className="flex items-center justify-center gap-2">
            <Spinner />
            Saving to Hub...
          </span>
        ) : isCritical ? (
          'Blocked — Critical Risk'
        ) : (
          'Approve & Save to Hub'
        )}
      </button>

      {isCritical && (
        <p className="text-xs text-red-600" role="alert">
          This offer cannot be approved due to critical fraud risk flags. Review and adjust
          the offer construct before re-generating.
        </p>
      )}

      {state === 'error' && errorMessage && (
        <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2" role="alert">
          <p className="text-sm text-red-700">{errorMessage}</p>
          <button
            onClick={() => {
              setState('idle');
              setErrorMessage(null);
            }}
            className="mt-1 text-xs text-red-600 underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
