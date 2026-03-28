import { z } from 'zod';

// ─── Enumerations ────────────────────────────────────────────────────────────

export type TriggerType = 'marketer_initiated' | 'purchase_triggered';
export type OfferStatus = 'draft' | 'approved' | 'active' | 'expired';

export const TRIGGER_TYPES: TriggerType[] = ['marketer_initiated', 'purchase_triggered'];
export const OFFER_STATUSES: OfferStatus[] = ['draft', 'approved', 'active', 'expired'];

// ─── Nested Type Interfaces ──────────────────────────────────────────────────

export interface Segment {
  name: string;
  definition: string;
  estimated_size: number;
  criteria: string[];
}

export interface Construct {
  type: string;
  value: number;
  description: string;
}

export interface Channel {
  channel_type: 'push' | 'email' | 'sms' | 'in_app';
  priority: number;
  message_template?: string;
}

export interface KPIs {
  expected_redemption_rate: number;
  expected_uplift_pct: number;
  target_segment_size?: number;
}

export interface RiskFlags {
  over_discounting: boolean;
  cannibalization: boolean;
  frequency_abuse: boolean;
  offer_stacking: boolean;
  severity: 'low' | 'medium' | 'critical';
  warnings: string[];
}

// ─── Core OfferBrief Interface ────────────────────────────────────────────────

export interface OfferBrief {
  offer_id: string;
  objective: string;
  segment: Segment;
  construct: Construct;
  channels: Channel[];
  kpis: KPIs;
  risk_flags: RiskFlags;
  status: OfferStatus;
  trigger_type: TriggerType;
  created_at: string; // ISO 8601
  valid_until?: string; // ISO 8601 — only for purchase_triggered offers
}

// ─── Inventory Suggestion (AI mode) ──────────────────────────────────────────

export interface InventorySuggestion {
  product_id: string;
  product_name: string;
  category: string;
  store: string;
  units_in_stock: number;
  urgency: 'high' | 'medium' | 'low';
  suggested_objective: string;
  stale?: boolean;
}

// ─── Zod Schemas ─────────────────────────────────────────────────────────────

export const SegmentSchema = z.object({
  name: z.string().min(1, 'Segment name is required'),
  definition: z.string().min(1, 'Segment definition is required'),
  estimated_size: z.number().int().nonnegative(),
  criteria: z.array(z.string()).min(1, 'At least one segment criterion is required'),
});

export const ConstructSchema = z.object({
  type: z.string().min(1, 'Construct type is required'),
  value: z.number().nonnegative(),
  description: z.string().min(1, 'Construct description is required'),
});

export const ChannelSchema = z.object({
  channel_type: z.enum(['push', 'email', 'sms', 'in_app']),
  priority: z.number().int().min(1),
  message_template: z.string().optional(),
});

export const KPIsSchema = z.object({
  expected_redemption_rate: z.number().min(0).max(1),
  expected_uplift_pct: z.number().min(0),
  target_segment_size: z.number().int().nonnegative().optional(),
});

export const RiskFlagsSchema = z.object({
  over_discounting: z.boolean(),
  cannibalization: z.boolean(),
  frequency_abuse: z.boolean(),
  offer_stacking: z.boolean(),
  severity: z.enum(['low', 'medium', 'critical']),
  warnings: z.array(z.string()),
});

export const OfferBriefSchema = z.object({
  offer_id: z.string().uuid('offer_id must be a valid UUID'),
  objective: z
    .string()
    .min(10, 'Objective must be at least 10 characters')
    .max(500, 'Objective must not exceed 500 characters'),
  segment: SegmentSchema,
  construct: ConstructSchema,
  channels: z.array(ChannelSchema).min(1, 'At least one channel is required'),
  kpis: KPIsSchema,
  risk_flags: RiskFlagsSchema,
  status: z.enum(['draft', 'approved', 'active', 'expired']),
  trigger_type: z.enum(['marketer_initiated', 'purchase_triggered']),
  created_at: z.string().datetime({ message: 'created_at must be ISO 8601' }),
  valid_until: z.string().datetime({ message: 'valid_until must be ISO 8601' }).optional(),
});

// ─── Input Schema for Offer Generation ───────────────────────────────────────

export const GenerateOfferInputSchema = z.object({
  objective: z
    .string()
    .min(10, 'Objective must be at least 10 characters')
    .max(500, 'Objective must not exceed 500 characters'),
  segment_hints: z.array(z.string()).optional(),
});

export type GenerateOfferInput = z.infer<typeof GenerateOfferInputSchema>;
export type OfferBriefValidated = z.infer<typeof OfferBriefSchema>;
