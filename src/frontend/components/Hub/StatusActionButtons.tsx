'use client';

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { approveOffer, activateOffer, expireOffer } from '@/app/hub/actions';
import type { OfferStatus } from '../../../shared/types/offer-brief';

interface StatusActionButtonsProps {
  offerId: string;
  status: OfferStatus;
}

export function StatusActionButtons({ offerId, status }: StatusActionButtonsProps) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [succeeded, setSucceeded] = useState<string | null>(null);
  const router = useRouter();

  function handleAction(action: (id: string) => Promise<{ success: boolean; error?: string }>, actionName: string) {
    setError(null);
    startTransition(async () => {
      const result = await action(offerId);
      if (result.success) {
        setSucceeded(actionName);
        router.refresh();
      } else {
        setError((result as { success: false; error: string }).error ?? 'Action failed.');
      }
    });
  }

  return (
    <div>
      <div className="flex items-center gap-1.5 justify-end flex-wrap">
        {status === 'draft' && (
          <button
            onClick={() => handleAction(approveOffer, 'approve')}
            disabled={isPending || succeeded === 'approve'}
            aria-label={`Approve offer ${offerId}`}
            className="inline-flex items-center gap-1 rounded-md bg-ct-red px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm transition hover:bg-ct-red-dark disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span className="material-symbols-outlined text-[13px]" aria-hidden="true">
              {isPending ? 'hourglass_empty' : 'thumb_up'}
            </span>
            {isPending ? 'Approving…' : 'Approve'}
          </button>
        )}

        {status === 'approved' && (
          <>
            <button
              onClick={() => handleAction(activateOffer, 'activate')}
              disabled={isPending || succeeded === 'activate'}
              aria-label={`Activate offer ${offerId}`}
              className="inline-flex items-center gap-1 rounded-md bg-emerald-600 px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-[13px]" aria-hidden="true">
                {isPending ? 'hourglass_empty' : 'rocket_launch'}
              </span>
              {isPending ? 'Activating…' : 'Activate'}
            </button>
            <button
              onClick={() => handleAction(expireOffer, 'expire')}
              disabled={isPending || succeeded === 'expire'}
              aria-label={`Close offer ${offerId}`}
              className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-[11px] font-medium text-gray-600 shadow-sm transition hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-[13px]" aria-hidden="true">block</span>
              {isPending ? 'Closing…' : 'Close'}
            </button>
          </>
        )}

        {status === 'active' && (
          <button
            onClick={() => handleAction(expireOffer, 'expire')}
            disabled={isPending || succeeded === 'expire'}
            aria-label={`Close offer ${offerId}`}
            className="inline-flex items-center gap-1 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-[11px] font-medium text-gray-600 shadow-sm transition hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span className="material-symbols-outlined text-[13px]" aria-hidden="true">block</span>
            {isPending ? 'Closing…' : 'Close Offer'}
          </button>
        )}
      </div>

      {error && (
        <p className="mt-1 text-right text-[11px] text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
