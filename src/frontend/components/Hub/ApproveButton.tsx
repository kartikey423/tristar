'use client';

/**
 * COMP-011: ApproveButton — Client Component.
 * Calls approveOffer Server Action via useTransition.
 * Disables during pending state. Refreshes page on success via useRouter.
 */

import { useTransition } from 'react';
import { useRouter } from 'next/navigation';
import { approveOffer } from '@/app/hub/actions';

interface ApproveButtonProps {
  offerId: string;
}

export function ApproveButton({ offerId }: ApproveButtonProps) {
  const [isPending, startTransition] = useTransition();
  const router = useRouter();

  function handleApprove() {
    startTransition(async () => {
      const result = await approveOffer(offerId);
      if (result.success) {
        router.refresh();
      }
    });
  }

  return (
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
  );
}
