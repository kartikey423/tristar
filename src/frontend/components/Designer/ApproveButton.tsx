'use client';

import { startTransition, useOptimistic, useState } from 'react';
import { approveOfferAction, rejectOfferAction, updateConstructValueAction } from '../../app/designer/actions';
import type { OfferBrief } from '../../../shared/types/offer-brief';
import { Spinner } from './Spinner';

interface ApproveButtonProps {
  offer: OfferBrief;
}

type ApproveState = 'idle' | 'pending' | 'success' | 'error';
type RejectState = 'idle' | 'confirm' | 'pending' | 'success' | 'error';

function constructLabel(type: string): string {
  switch (type) {
    case 'points_multiplier': return 'Points Multiplier';
    case 'cashback': return 'Cashback (%)';
    case 'bonus_points': return 'Bonus Points';
    case 'discount': return 'Discount (%)';
    default: return type.replace(/_/g, ' ');
  }
}

export function ApproveButton({ offer }: ApproveButtonProps) {
  const [approveState, setApproveState] = useState<ApproveState>('idle');
  const [rejectState, setRejectState] = useState<RejectState>('idle');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [discountValue, setDiscountValue] = useState<string>(String(offer.construct.value));
  const [discountSaving, setDiscountSaving] = useState(false);
  const [discountSaved, setDiscountSaved] = useState(false);
  const [discountError, setDiscountError] = useState<string | null>(null);

  const isCritical = offer.risk_flags.severity === 'critical';
  const isAlreadyApproved = offer.status === 'approved' || offer.status === 'active';

  const [optimisticStatus, addOptimistic] = useOptimistic(
    offer.status,
    (_current: string, next: string) => next,
  );

  async function handleUpdateDiscount() {
    const num = parseFloat(discountValue);
    if (isNaN(num) || num <= 0) {
      setDiscountError('Enter a valid positive number');
      return;
    }
    setDiscountSaving(true);
    setDiscountError(null);
    setDiscountSaved(false);
    const result = await updateConstructValueAction(offer.offer_id, num);
    setDiscountSaving(false);
    if (result.success) {
      setDiscountSaved(true);
      setTimeout(() => setDiscountSaved(false), 3000);
    } else {
      setDiscountError(result.error);
    }
  }

  async function handleApprove() {
    if (isCritical || isAlreadyApproved) return;
    setApproveState('pending');
    startTransition(async () => {
      addOptimistic('approved');
      const result = await approveOfferAction(offer.offer_id);
      if (result.success) {
        setApproveState('success');
      } else {
        addOptimistic(offer.status); // Revert optimistic update on error
        setApproveState('error');
        setErrorMessage(result.error);
      }
    });
  }

  async function handleRejectConfirm() {
    setRejectState('pending');
    const result = await rejectOfferAction(offer.offer_id);
    if (result.success) {
      setRejectState('success');
    } else {
      setRejectState('error');
      setErrorMessage(result.error);
    }
  }

  // Rejected state
  if (rejectState === 'success') {
    return (
      <div className="card bg-surface-low px-4 py-3 text-center">
        <p className="text-sm font-medium text-gray-500">Offer rejected and removed</p>
        <p className="text-xs text-gray-400 mt-1">Generate a new offer to start again</p>
      </div>
    );
  }

  // Approved state
  if (isAlreadyApproved || optimisticStatus === 'approved') {
    return (
      <div
        className="flex items-center gap-2 rounded-md bg-emerald-50 border-l-2 border-emerald-500 px-4 py-2.5"
        role="status"
        aria-live="polite"
      >
        <span className="material-symbols-outlined text-[16px] text-emerald-600" aria-hidden="true">
          check_circle
        </span>
        <span className="text-sm font-medium text-emerald-700">Saved to Hub</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Discount override */}
      <div className="rounded-md bg-blue-50/50 border border-blue-100 p-3">
        <p className="text-xs font-medium text-blue-700 mb-2">
          Adjust Offer Value Before Approving
        </p>
        <div className="flex items-end gap-2">
          <div className="flex-1">
            <label htmlFor="discount-override" className="block text-xs text-blue-600 mb-1">
              {constructLabel(offer.construct.type)}
            </label>
            <input
              id="discount-override"
              type="number"
              min="0.1"
              max="10000"
              step="0.5"
              value={discountValue}
              onChange={(e) => {
                setDiscountValue(e.target.value);
                setDiscountSaved(false);
              }}
              className="input text-sm"
            />
          </div>
          <button
            type="button"
            onClick={handleUpdateDiscount}
            disabled={discountSaving}
            className="btn-secondary text-xs px-3 py-2"
          >
            {discountSaving ? 'Saving...' : discountSaved ? 'Saved' : 'Update'}
          </button>
        </div>
        {discountError && (
          <p className="text-xs text-red-600 mt-1">{discountError}</p>
        )}
        {discountSaved && (
          <p className="text-xs text-emerald-600 mt-1">Construct value updated successfully</p>
        )}
      </div>

      {/* Approve button */}
      <button
        type="button"
        onClick={handleApprove}
        disabled={isCritical || approveState === 'pending' || approveState === 'success'}
        title={isCritical ? 'Critical risk detected — cannot approve' : undefined}
        aria-disabled={isCritical}
        aria-label={isCritical ? 'Cannot approve — critical risk detected' : 'Approve offer and save to Hub'}
        className={`w-full ${isCritical ? 'btn-secondary cursor-not-allowed opacity-50' : 'btn-primary'}`}
      >
        {approveState === 'pending' ? (
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

      {approveState === 'error' && errorMessage && (
        <div className="card border-l-2 border-red-500 px-3 py-2" role="alert">
          <p className="text-sm text-red-700">{errorMessage}</p>
          <button
            onClick={() => { setApproveState('idle'); setErrorMessage(null); }}
            className="mt-1 text-xs text-red-500 hover:text-red-700"
          >
            Retry
          </button>
        </div>
      )}

      {/* Reject button */}
      {rejectState === 'confirm' ? (
        <div className="card border-l-2 border-red-500 px-3 py-2.5">
          <p className="text-sm text-red-800 font-medium mb-2">Reject this offer?</p>
          <p className="text-xs text-red-600 mb-3">This will permanently delete the draft.</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleRejectConfirm}
              className="flex-1 btn-primary bg-red-600 hover:bg-red-700 text-xs py-1.5"
            >
              Yes, Reject
            </button>
            <button
              type="button"
              onClick={() => setRejectState('idle')}
              className="flex-1 btn-secondary text-xs py-1.5"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : !isAlreadyApproved ? (
        <button
          type="button"
          onClick={() => setRejectState('confirm')}
          className="w-full btn-danger-outline"
        >
          Reject Offer
        </button>
      ) : null}

      {rejectState === 'error' && errorMessage && (
        <div className="card border-l-2 border-red-500 px-3 py-2" role="alert">
          <p className="text-sm text-red-700">{errorMessage}</p>
        </div>
      )}
    </div>
  );
}
