'use client';

/**
 * MobileNotificationPreview — iPhone-style phone mockup with lock-screen push notifications.
 *
 * Shown in the Scout phase after a match is returned. Gives a realistic preview
 * of how the Triangle Rewards notification looks on the customer's phone.
 */

import { useEffect, useState, useCallback } from 'react';
import type { ScoutMatchResult } from '@/lib/scout-api';
import { isMatchResponse, customerAcceptOffer } from '@/lib/scout-api';
import type { OfferBrief } from '../../../shared/types/offer-brief';

// ── Helpers ────────────────────────────────────────────────────────────────────

function useLiveTime() {
  const [time, setTime] = useState(() => {
    const now = new Date();
    return now.toLocaleTimeString('en-CA', { hour: '2-digit', minute: '2-digit', hour12: false });
  });
  useEffect(() => {
    const id = setInterval(() => {
      const now = new Date();
      setTime(now.toLocaleTimeString('en-CA', { hour: '2-digit', minute: '2-digit', hour12: false }));
    }, 10_000);
    return () => clearInterval(id);
  }, []);
  return time;
}

function formatLockDate() {
  return new Date().toLocaleDateString('en-CA', { weekday: 'long', month: 'long', day: 'numeric' });
}

// ── Sub-components ─────────────────────────────────────────────────────────────

interface NotifCardProps {
  appIcon: React.ReactNode;
  appName: string;
  timeLabel: string;
  title: string;
  body: string;
  accent?: string; // tailwind bg class for icon background
  actionLabel?: string;
  onActionClick?: () => void;
  highlight?: boolean;
  delay?: number; // animation delay ms
}

function LockNotifCard({
  appIcon,
  appName,
  timeLabel,
  title,
  body,
  accent = 'bg-gray-700',
  actionLabel,
  onActionClick,
  highlight,
  delay = 0,
}: NotifCardProps) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => setVisible(true), delay);
    return () => clearTimeout(id);
  }, [delay]);

  return (
    <div
      className={`
        transition-all duration-500 ease-out
        ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}
        rounded-2xl backdrop-blur-md bg-white/20 border border-white/30 shadow-lg overflow-hidden
        ${highlight ? 'ring-2 ring-[#E4003A]/70' : ''}
      `}
    >
      {/* Notification header */}
      <div className="flex items-center gap-2 px-3 pt-2.5 pb-1">
        <div className={`w-6 h-6 rounded-[8px] ${accent} flex items-center justify-center flex-shrink-0`}>
          {appIcon}
        </div>
        <span className="text-white/90 text-[11px] font-semibold tracking-wide flex-1">{appName}</span>
        <span className="text-white/55 text-[10px]">{timeLabel}</span>
      </div>
      {/* Content */}
      <div className="px-3 pb-2.5">
        <p className="text-white text-[13px] font-semibold leading-tight">{title}</p>
        <p className="text-white/80 text-[12px] leading-snug mt-0.5 line-clamp-3">{body}</p>
      </div>
      {/* Action row */}
      {actionLabel && (
        <div className="border-t border-white/20 flex">
          <button
            onClick={onActionClick}
            className="flex-1 text-[12px] text-blue-300 font-medium py-2 hover:bg-white/10 transition-colors active:bg-white/20"
          >
            {actionLabel}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Swipe-to-dismiss visual hint ───────────────────────────────────────────────

function SwipeHint() {
  return (
    <div className="flex flex-col items-center mt-3 gap-1">
      <div className="w-10 h-1 rounded-full bg-white/30" />
      <p className="text-white/40 text-[10px]">swipe to dismiss</p>
    </div>
  );
}

// ── Main export ────────────────────────────────────────────────────────────────

interface MobileNotificationPreviewProps {
  memberFirstName: string;
  storeName: string;
  itemName: string;
  purchaseAmount: number;
  pointsEarned: number;
  totalRewardsPoints: number;
  result: ScoutMatchResult;
  // For partner-triggered cross-sell
  isPartnerTrigger?: boolean;
  partnerBrandName?: string;
  partnerGeneratedOffer?: OfferBrief | null;
  // Recommendation items for smart cross-sell
  recommendedItemName?: string | null;
  recommendedItemPrice?: number | null;
  recommendedItemDiscountPct?: number | null;
  // Net price after rewards for recommended item
  netPriceAfterRewards?: number | null;
}

export function MobileNotificationPreview({
  memberFirstName,
  storeName,
  itemName,
  purchaseAmount,
  pointsEarned,
  totalRewardsPoints,
  result,
  isPartnerTrigger = false,
  partnerBrandName,
  partnerGeneratedOffer,
  recommendedItemName = null,
  recommendedItemPrice = null,
  recommendedItemDiscountPct = null,
  netPriceAfterRewards = null,
}: MobileNotificationPreviewProps) {
  const time = useLiveTime();
  const lockDate = formatLockDate();
  const hasMatch = isMatchResponse(result);

  // ── Customer notification accept state ──────────────────────────────────────
  type AcceptState = 'idle' | 'loading' | 'accepted' | 'error';
  const [acceptState, setAcceptState] = useState<AcceptState>('idle');
  const [acceptMsg, setAcceptMsg] = useState('');

  // Reset when a new result arrives
  useEffect(() => { setAcceptState('idle'); setAcceptMsg(''); }, [result]);

  const handleAccept = useCallback(async () => {
    const offerId = hasMatch ? (result as { offer_id: string }).offer_id : null;
    const partnerOfferId = partnerGeneratedOffer?.offer_id ?? null;
    const id = partnerOfferId ?? offerId;
    if (!id) return;

    setAcceptState('loading');
    const { success, message } = await customerAcceptOffer(id);
    if (success) {
      setAcceptState('accepted');
      setAcceptMsg('Offer activated! Check the Hub for your active deal.');
    } else {
      setAcceptState('error');
      setAcceptMsg(message);
    }
  }, [hasMatch, result, partnerGeneratedOffer]);
  const rewardsValue = (totalRewardsPoints * 0.01).toFixed(2);

  // 75/25 Triangle Rewards rule for partner-generated offer
  const partnerDiscountPct = partnerGeneratedOffer?.construct?.value ?? 15;
  const partnerOfferValue = purchaseAmount * (partnerDiscountPct / 100);
  const partnerMaxPoints = partnerOfferValue * 0.75;
  const partnerMinCard = partnerOfferValue * 0.25;
  const partnerNetPay = purchaseAmount - partnerMaxPoints;

  // Build notification text for CTC match
  const notifTitle = hasMatch
    ? result.outcome === 'queued'
      ? 'Offer Scheduled for 8:00 AM'
      : result.outcome === 'rate_limited'
        ? 'New Canadian Tire Offer Ready'
        : `Exclusive offer for you, ${memberFirstName}!`
    : 'Triangle Rewards Update';

  const notifBody = hasMatch && result.notification_text
    ? result.notification_text
    : hasMatch
      ? `You just earned ${pointsEarned.toLocaleString()} points at ${storeName}. Balance: ${totalRewardsPoints.toLocaleString()} pts ($${rewardsValue}).`
      : result.message ?? 'No matching offer right now.';

  // Smart recommendation body — shows recommended items + net price after rewards
  const recommendationBody = recommendedItemName && recommendedItemDiscountPct
    ? `Since you got ${itemName}, we recommend: ${recommendedItemName} at ${recommendedItemDiscountPct}% off. You'll pay $${(netPriceAfterRewards ?? recommendedItemPrice ?? 0).toFixed(2)} (with Triangle Points applied).`
    : notifBody;

  // Partner cross-sell notification body — includes payment split
  const pushChannel = partnerGeneratedOffer?.channels?.find((c) => c.channel_type === 'push');
  const partnerBaseMsg = pushChannel?.message_template
    ?? partnerGeneratedOffer?.objective
    ?? `Exclusive Canadian Tire offer from your visit to ${partnerBrandName ?? 'our partner'}!`;
  const partnerNotifBody = partnerGeneratedOffer
    ? `${partnerBaseMsg} Use up to $${partnerMaxPoints.toFixed(2)} in Triangle Points (75%) — pay min $${partnerMinCard.toFixed(2)} by card. Est. you pay: $${partnerNetPay.toFixed(2)}.`
    : `Check out an exclusive Canadian Tire offer nearby. ${partnerDiscountPct}% off — pay with Triangle Points!`;

  return (
    <div className="flex flex-col items-center">
      {/* Label */}
      <p className="text-xs text-gray-400 uppercase tracking-widest mb-3 font-medium">
        Customer&rsquo;s Phone Preview
      </p>

      {/* ── Phone frame ── */}
      <div
        className="relative rounded-[44px] bg-[#1a1a1a] shadow-[0_25px_60px_rgba(0,0,0,0.5),inset_0_0_0_1.5px_rgba(255,255,255,0.08)] overflow-hidden select-none"
        style={{ width: 300, height: 618 }}
      >
        {/* Side buttons (volume, power) — decorative */}
        <div className="absolute -left-[3px] top-24 w-[3px] h-8 bg-[#2a2a2a] rounded-l" />
        <div className="absolute -left-[3px] top-36 w-[3px] h-12 bg-[#2a2a2a] rounded-l" />
        <div className="absolute -left-[3px] top-52 w-[3px] h-12 bg-[#2a2a2a] rounded-l" />
        <div className="absolute -right-[3px] top-32 w-[3px] h-16 bg-[#2a2a2a] rounded-r" />

        {/* Screen */}
        <div
          className="absolute inset-0 overflow-hidden rounded-[44px]"
          style={{
            background: 'linear-gradient(160deg, #0f2027 0%, #203a43 45%, #2c5364 100%)',
          }}
        >
          {/* Subtle light leak */}
          <div className="absolute inset-0 bg-gradient-to-b from-white/5 to-transparent pointer-events-none" />

          {/* Dynamic island */}
          <div className="absolute top-3 left-1/2 -translate-x-1/2 w-[100px] h-[34px] bg-black rounded-full z-10" />

          {/* Status bar */}
          <div className="flex items-center justify-between px-7 pt-4 pb-1 relative z-20">
            <span className="text-white text-[13px] font-semibold tracking-tight">{time}</span>
            <div className="flex items-center gap-1.5">
              {/* Signal */}
              <svg width="17" height="12" viewBox="0 0 17 12" fill="none">
                <rect x="0" y="9" width="3" height="3" rx="0.5" fill="white" />
                <rect x="4.5" y="6" width="3" height="6" rx="0.5" fill="white" />
                <rect x="9" y="3" width="3" height="9" rx="0.5" fill="white" />
                <rect x="13.5" y="0" width="3" height="12" rx="0.5" fill="white" opacity="0.35" />
              </svg>
              {/* Wifi */}
              <svg width="16" height="12" viewBox="0 0 16 12" fill="white">
                <path d="M8 9.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3z" />
                <path d="M4.22 6.78a5.25 5.25 0 0 1 7.56 0" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                <path d="M1.76 4.32a8.75 8.75 0 0 1 12.48 0" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
              </svg>
              {/* Battery */}
              <div className="flex items-center gap-0.5">
                <div className="w-6 h-3 rounded-[3px] border border-white/70 p-[2px] flex items-center">
                  <div className="w-4 h-full rounded-[1.5px] bg-white" />
                </div>
                <div className="w-[2px] h-1.5 bg-white/60 rounded-r-sm" />
              </div>
            </div>
          </div>

          {/* Lock screen time + date */}
          <div className="text-center mt-4 mb-4 px-4">
            <p className="text-white font-thin text-[60px] leading-none tracking-tight">{time}</p>
            <p className="text-white/80 text-[15px] mt-2 font-light">{lockDate}</p>
          </div>

          {/* ── Notifications panel ── */}
          <div className="px-3 space-y-2.5 overflow-y-auto" style={{ maxHeight: 340 }}>

            {/* Purchase receipt notification — partner store or CTC */}
            <LockNotifCard
              delay={100}
              accent={isPartnerTrigger ? 'bg-[#c8102e]' : 'bg-[#E4003A]'}
              appName={isPartnerTrigger && partnerBrandName ? partnerBrandName : 'Canadian Tire'}
              timeLabel="now"
              appIcon={
                isPartnerTrigger && partnerBrandName
                  ? <span className="text-white text-[9px] font-bold leading-none">{partnerBrandName.slice(0, 2).toUpperCase()}</span>
                  : <span className="text-white text-[9px] font-bold leading-none">CT</span>
              }
              title={`Purchase at ${storeName}`}
              body={`${itemName} — $${purchaseAmount.toFixed(2)} · +${pointsEarned.toLocaleString()} pts earned`}
            />

            {/* Triangle Rewards offer notification — only when activated */}
            {hasMatch && result.outcome !== 'rate_limited' && (
              <LockNotifCard
                delay={600}
                highlight
                accent="bg-[#E4003A]"
                appName="Triangle Rewards"
                timeLabel="now"
                appIcon={
                  <svg viewBox="0 0 20 20" fill="white" className="w-3.5 h-3.5">
                    <polygon points="10,2 18,17 2,17" />
                  </svg>
                }
                title={notifTitle}
                body={recommendationBody}
                actionLabel={acceptState === 'loading' ? 'Activating…' : acceptState === 'accepted' ? '✓ Activated!' : 'View Offer →'}
                onActionClick={acceptState === 'idle' ? handleAccept : undefined}
              />
            )}

            {/* Queued notification */}
            {hasMatch && result.outcome === 'queued' && result.delivery_time && (
              <LockNotifCard
                delay={900}
                accent="bg-amber-600"
                appName="Triangle Rewards"
                timeLabel={`Scheduled ${result.delivery_time}`}
                appIcon={
                  <svg viewBox="0 0 20 20" fill="white" className="w-3.5 h-3.5">
                    <circle cx="10" cy="10" r="8" stroke="white" strokeWidth="2" fill="none" />
                    <polyline points="10,5 10,10 14,12" stroke="white" strokeWidth="1.5" fill="none" strokeLinecap="round" />
                  </svg>
                }
                title="Offer Scheduled"
                body={`Your exclusive offer will be delivered at ${result.delivery_time}. We respect quiet hours 🌙`}
              />
            )}

            {/* Rate-limited — soft reminder */}
            {hasMatch && result.outcome === 'rate_limited' && (
              <LockNotifCard
                delay={600}
                accent="bg-gray-600"
                appName="Triangle Rewards"
                timeLabel="earlier"
                appIcon={
                  <svg viewBox="0 0 20 20" fill="white" className="w-3.5 h-3.5">
                    <polygon points="10,2 18,17 2,17" />
                  </svg>
                }
                title="You already have an active offer!"
                body={`Balance: ${totalRewardsPoints.toLocaleString()} pts ($${rewardsValue}) · Check the app for your current deal.`}
              />
            )}

            {/* Partner — Triangle Rewards points earned notification */}
            {isPartnerTrigger && (
              <LockNotifCard
                delay={300}
                accent="bg-[#E4003A]"
                appName="Triangle Rewards"
                timeLabel="now"
                appIcon={
                  <svg viewBox="0 0 20 20" fill="white" className="w-3.5 h-3.5">
                    <polygon points="10,2 18,17 2,17" />
                  </svg>
                }
                title={`+${pointsEarned.toLocaleString()} pts earned at ${storeName}`}
                body={`Balance: ${totalRewardsPoints.toLocaleString()} pts ($${rewardsValue}). A Canadian Tire offer is ready nearby!`}
              />
            )}

            {isPartnerTrigger && partnerGeneratedOffer && (
              <LockNotifCard
                delay={1100}
                highlight
                accent="bg-[#E4003A]"
                appName="Canadian Tire"
                timeLabel="now"
                appIcon={
                  <span className="text-white text-[9px] font-bold leading-none">CT</span>
                }
                title="Exclusive offer near you!"
                body={partnerNotifBody}
                actionLabel={acceptState === 'loading' ? 'Activating…' : acceptState === 'accepted' ? '✓ Activated!' : 'View Offer →'}
                onActionClick={acceptState === 'idle' ? handleAccept : undefined}
              />
            )}

            {/* No match */}
            {!hasMatch && !isPartnerTrigger && (
              <LockNotifCard
                delay={300}
                accent="bg-gray-600"
                appName="Triangle Rewards"
                timeLabel="now"
                appIcon={
                  <svg viewBox="0 0 20 20" fill="white" className="w-3.5 h-3.5">
                    <polygon points="10,2 18,17 2,17" />
                  </svg>
                }
                title="Points Recorded"
                body={`+${pointsEarned.toLocaleString()} pts · Balance: ${totalRewardsPoints.toLocaleString()} pts ($${rewardsValue})`}
              />
            )}
          </div>

          {/* Swipe hint */}
          <SwipeHint />

          {/* ── Accepted overlay — full screen "offer activated" confirmation ── */}
          {acceptState === 'accepted' && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 backdrop-blur-sm z-30 rounded-[44px] px-6 text-center">
              <div className="w-16 h-16 rounded-full bg-emerald-500 flex items-center justify-center mb-4 shadow-lg">
                <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="w-8 h-8">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              </div>
              <p className="text-white text-[18px] font-bold mb-1">Offer Activated!</p>
              <p className="text-white/80 text-[13px] leading-snug">{acceptMsg}</p>
              <div className="mt-4 rounded-full bg-white/20 px-4 py-1.5">
                <p className="text-white/70 text-[11px]">Check the Hub tab to see your active offer</p>
              </div>
            </div>
          )}

          {/* ── Error overlay ── */}
          {acceptState === 'error' && (
            <div className="absolute bottom-20 left-3 right-3 z-30 rounded-2xl bg-red-500/90 backdrop-blur-sm px-4 py-3 text-center">
              <p className="text-white text-[12px] font-semibold">Could not activate offer</p>
              <p className="text-white/80 text-[11px] mt-0.5">{acceptMsg}</p>
            </div>
          )}

          {/* Home indicator */}
          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 w-28 h-1 bg-white/30 rounded-full" />
        </div>
      </div>

      {/* Reflection / glow under phone */}
      <div
        className="mt-2 rounded-full blur-xl opacity-30"
        style={{
          width: 200,
          height: 20,
          background: 'radial-gradient(ellipse, rgba(228,0,58,0.8) 0%, transparent 70%)',
        }}
      />
    </div>
  );
}
