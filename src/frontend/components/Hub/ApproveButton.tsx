'use client';

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
        className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
          isPending
            ? 'cursor-not-allowed bg-gray-200 text-gray-400'
            : 'btn-primary text-xs py-1.5'
        }`}
      >
        {isPending ? 'Approving...' : 'Approve'}
      </button>
      {error && (
        <p className="mt-1 text-xs text-red-600" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
