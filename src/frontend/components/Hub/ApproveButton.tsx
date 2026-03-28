'use client';

/**
 * COMP-011: ApproveButton — Client Component.
 * Calls approveOffer Server Action via useTransition.
 * Disables during pending state. Refreshes page on success via useRouter.
 */

import { useState, useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { approveOffer } from '@/app/hub/actions';

interface ApproveButtonProps {
  offerId: string;
}

export function ApproveButton({ offerId }: ApproveButtonProps) {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  function handleApprove() {
    setError(null);
    startTransition(async () => {
      const result = await approveOffer(offerId);
      if (result.success) {
        router.refresh();
      } else {
        setError(result.error ?? 'Approval failed. Please try again.');
      }
    });
  }

  return (
    <div>
      <button
        onClick={handleApprove}
        disabled={isPending}
        aria-label={`Approve offer ${offerId}`}
        className={`rounded px-3 py-1.5 text-sm font-medium transition ${
          isPending
            ? 'cursor-not-allowed bg-gray-300 text-gray-500'
            : 'bg-blue-600 text-white hover:bg-blue-700'
        }`}
      >
        {isPending ? 'Approving…' : 'Approve'}
      </button>
      {error && (
        <p className="mt-1 text-xs text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
