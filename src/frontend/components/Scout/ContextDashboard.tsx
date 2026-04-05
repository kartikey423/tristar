'use client';

/**
 * ContextDashboard — CTC purchase-event simulation for Scout demo.
 *
 * Simulates a customer completing a transaction at a CTC or partner store.
 * Derives GPS, category, and rewards from the store + item selection.
 * Date picker auto-derives day context (weekday/weekend/long_weekend) and
 * detects Canadian statutory holidays, special occasions, and sports days.
 * Clearance suggestions are personalised based on the selected member's
 * purchase history preferences.
 */

import { useState, useRef, useEffect } from 'react';
import type { MatchRequest, ScoutMatchResult, ScoutMatchError, PartnerPurchaseEvent, PartnerTriggerApiResponse } from '@/lib/scout-api';
import { callScoutMatch, callPartnerTrigger, isMatchResponse } from '@/lib/scout-api';
import type { OfferBrief } from '../../../shared/types/offer-brief';
import { ActivationFeed } from './ActivationFeed';
import { MobileNotificationPreview } from './MobileNotificationPreview';
import type { RecommendedItem } from './MobileNotificationPreview';

// ── Store fixtures ─────────────────────────────────────────────────────────────

interface StoreFixture {
  id: string;
  name: string;
  brand:
    | 'canadian_tire'
    | 'sport_chek'
    | 'marks'
    | 'petro_canada'
    | 'party_city'
    | 'tim_hortons'
    | 'westside'
    | 'sports_experts'
    | 'pro_hockey_life';
  lat: number;
  lon: number;
  category: string;
  branch: string;
}

const CTC_PARTNER_STORES: StoreFixture[] = [
  { id: 'ctc-001', name: 'Canadian Tire — Queen St W', brand: 'canadian_tire', lat: 43.6488, lon: -79.3981, category: 'general', branch: 'Queen St W' },
  { id: 'ctc-002', name: 'Canadian Tire — Yonge & Eglinton', brand: 'canadian_tire', lat: 43.7060, lon: -79.3985, category: 'general', branch: 'Yonge & Eglinton' },
  { id: 'ctc-007', name: 'Canadian Tire — Scarborough', brand: 'canadian_tire', lat: 43.7731, lon: -79.2576, category: 'general', branch: 'Scarborough Town Centre' },
  { id: 'ctc-003', name: 'Sport Chek — Eaton Centre', brand: 'sport_chek', lat: 43.6544, lon: -79.3807, category: 'sporting_goods', branch: 'Eaton Centre' },
  { id: 'ctc-004', name: 'Sport Chek — Yorkdale', brand: 'sport_chek', lat: 43.7243, lon: -79.4508, category: 'sporting_goods', branch: 'Yorkdale Mall' },
  { id: 'ctc-006', name: "Mark's — King St W", brand: 'marks', lat: 43.6450, lon: -79.4012, category: 'apparel', branch: 'King St W' },
  { id: 'pca-001', name: 'Petro-Canada — Queensway', brand: 'petro_canada', lat: 43.6325, lon: -79.5020, category: 'fuel', branch: 'Queensway' },
  { id: 'pca-002', name: 'Petro-Canada — Lawrence Ave', brand: 'petro_canada', lat: 43.7241, lon: -79.4318, category: 'fuel', branch: 'Lawrence Ave E' },
  { id: 'pca-003', name: 'Petro-Canada — Yonge & Finch', brand: 'petro_canada', lat: 43.7800, lon: -79.4141, category: 'fuel', branch: 'Yonge & Finch' },
  { id: 'pcy-001', name: 'Party City — North York', brand: 'party_city', lat: 43.7624, lon: -79.4147, category: 'seasonal', branch: 'North York' },
  { id: 'pcy-002', name: 'Party City — Mississauga', brand: 'party_city', lat: 43.5890, lon: -79.6440, category: 'seasonal', branch: 'Mississauga' },
  { id: 'th-001', name: 'Tim Hortons — Front St', brand: 'tim_hortons', lat: 43.6456, lon: -79.3790, category: 'quick_meal', branch: 'Front St' },
  { id: 'th-002', name: 'Tim Hortons — Bloor & Bathurst', brand: 'tim_hortons', lat: 43.6655, lon: -79.4111, category: 'quick_meal', branch: 'Bloor & Bathurst' },
  { id: 'th-bm-001', name: 'Tim Hortons — Blue Mountain', brand: 'tim_hortons', lat: 44.50, lon: -80.31, category: 'quick_meal', branch: 'Blue Mountain Resort' },
  { id: 'th-wh-001', name: 'Tim Hortons — Whistler Village', brand: 'tim_hortons', lat: 50.11, lon: -122.95, category: 'quick_meal', branch: 'Whistler Village' },
  { id: 'ws-001', name: 'Westside — Queen West', brand: 'westside', lat: 43.6478, lon: -79.4068, category: 'home_living', branch: 'Queen West' },
  { id: 'ws-002', name: 'Westside — North York', brand: 'westside', lat: 43.7620, lon: -79.4131, category: 'home_living', branch: 'North York' },
  { id: 'se-001', name: 'Sports Experts — Toronto Eaton', brand: 'sports_experts', lat: 43.6541, lon: -79.3804, category: 'sporting_goods', branch: 'Eaton' },
  { id: 'phl-001', name: 'Pro Hockey Life — Vaughan', brand: 'pro_hockey_life', lat: 43.8372, lon: -79.5080, category: 'sporting_goods', branch: 'Vaughan' },
];

// ── Store items ────────────────────────────────────────────────────────────────

interface StoreItem {
  name: string;
  price: number;
  category: string;
}

const STORE_ITEMS: Record<StoreFixture['brand'], StoreItem[]> = {
  canadian_tire: [
    { name: 'Ergonomic Snow Shovel', price: 39.99, category: 'hardware' },
    { name: 'Motor Oil 5W-30 (5L)', price: 38.99, category: 'automotive' },
    { name: 'Windshield Wipers (pair)', price: 24.99, category: 'automotive' },
    { name: 'Car Battery (Group 24)', price: 129.99, category: 'automotive' },
    { name: 'Power Drill Kit', price: 79.99, category: 'hardware' },
    { name: 'Smoke Detector', price: 29.99, category: 'hardware' },
  ],
  sport_chek: [
    { name: 'Trail Running Shoes', price: 129.99, category: 'sporting_goods' },
    { name: 'Hockey Stick (Senior)', price: 89.99, category: 'sporting_goods' },
    { name: 'Yoga Mat (6mm)', price: 49.99, category: 'sporting_goods' },
    { name: 'Cycling Helmet', price: 79.99, category: 'sporting_goods' },
    { name: 'Camping Tent (2-person)', price: 199.99, category: 'outdoor' },
    { name: 'Walking Poles (pair)', price: 79.99, category: 'outdoor' },
  ],
  marks: [
    { name: 'Winter Boots (insulated)', price: 149.99, category: 'apparel' },
    { name: 'Fleece-Lined Jacket', price: 89.99, category: 'apparel' },
    { name: 'Work Gloves (pack of 3)', price: 29.99, category: 'apparel' },
    { name: 'Steel-Toe Safety Shoes', price: 119.99, category: 'apparel' },
    { name: 'Thermal Underwear Set', price: 49.99, category: 'apparel' },
  ],
  petro_canada: [
    { name: 'Regular Unleaded (fill-up ~50L)', price: 72.00, category: 'fuel' },
    { name: 'Premium Unleaded (fill-up ~50L)', price: 85.00, category: 'fuel' },
    { name: 'Car Wash (Deluxe)', price: 14.99, category: 'automotive' },
    { name: 'Windshield Washer Fluid (4L)', price: 3.99, category: 'automotive' },
  ],
  party_city: [
    { name: 'Birthday Party Pack (30-pc)', price: 29.99, category: 'seasonal' },
    { name: 'Balloon Bundle (25 latex)', price: 19.99, category: 'seasonal' },
    { name: 'Halloween Costume (adult)', price: 49.99, category: 'seasonal' },
    { name: 'Party Supplies Bundle', price: 39.99, category: 'seasonal' },
  ],
  tim_hortons: [
    { name: 'Double-Double + Breakfast Wrap Combo', price: 9.49, category: 'quick_meal' },
    { name: 'French Vanilla + Bagel Combo', price: 7.49, category: 'quick_meal' },
    { name: 'Family Timbits Pack (20)', price: 8.99, category: 'quick_meal' },
    { name: 'Iced Capp + Sandwich Combo', price: 10.99, category: 'quick_meal' },
  ],
  westside: [
    { name: 'Air Fryer 5L', price: 89.99, category: 'home_living' },
    { name: 'Cotton Bedsheet Set (Queen)', price: 39.99, category: 'home_living' },
    { name: 'Kitchen Storage Container Set', price: 24.99, category: 'home_living' },
    { name: 'LED Floor Lamp', price: 59.99, category: 'home_living' },
  ],
  sports_experts: [
    { name: 'Running Shoes Pro', price: 139.99, category: 'sporting_goods' },
    { name: 'Training Tee (men)', price: 29.99, category: 'sporting_goods' },
    { name: 'Gym Duffel Bag', price: 49.99, category: 'sporting_goods' },
    { name: 'Smart Fitness Watch', price: 179.99, category: 'sporting_goods' },
  ],
  pro_hockey_life: [
    { name: 'Composite Hockey Stick Elite', price: 179.99, category: 'sporting_goods' },
    { name: 'Hockey Gloves Pro', price: 99.99, category: 'sporting_goods' },
    { name: 'Skates Performance', price: 249.99, category: 'sporting_goods' },
    { name: 'Stick Tape Bundle', price: 12.99, category: 'sporting_goods' },
  ],
};

// ── Per-store inventory overrides (branch-specific items & prices) ────────────

const STORE_INVENTORY: Record<string, StoreItem[]> = {
  'ctc-001': [ // Canadian Tire — Queen St W (downtown: more urban/auto focus)
    { name: 'Motor Oil 5W-30 (5L)', price: 38.99, category: 'automotive' },
    { name: 'Windshield Wipers (pair)', price: 24.99, category: 'automotive' },
    { name: 'Power Drill Kit', price: 84.99, category: 'hardware' },
    { name: 'Smoke Detector', price: 27.99, category: 'hardware' },
    { name: 'LED Desk Lamp', price: 34.99, category: 'hardware' },
  ],
  'ctc-002': [ // Canadian Tire — Yonge & Eglinton (midtown: balanced mix)
    { name: 'Ergonomic Snow Shovel', price: 42.99, category: 'hardware' },
    { name: 'Car Battery (Group 24)', price: 134.99, category: 'automotive' },
    { name: 'Power Drill Kit', price: 79.99, category: 'hardware' },
    { name: 'Smoke Detector', price: 29.99, category: 'hardware' },
    { name: 'Portable Air Compressor', price: 59.99, category: 'automotive' },
  ],
  'ctc-007': [ // Canadian Tire — Scarborough (suburban: more outdoor/seasonal)
    { name: 'Ergonomic Snow Shovel', price: 37.99, category: 'hardware' },
    { name: 'Motor Oil 5W-30 (5L)', price: 36.99, category: 'automotive' },
    { name: 'Car Battery (Group 24)', price: 124.99, category: 'automotive' },
    { name: 'Snow Blower (electric)', price: 249.99, category: 'hardware' },
    { name: 'Patio Heater', price: 159.99, category: 'hardware' },
    { name: 'BBQ Propane Tank (20lb)', price: 32.99, category: 'hardware' },
  ],
  'ctc-003': [ // Sport Chek — Eaton Centre (urban flagship: full range)
    { name: 'Trail Running Shoes', price: 134.99, category: 'sporting_goods' },
    { name: 'Hockey Stick (Senior)', price: 94.99, category: 'sporting_goods' },
    { name: 'Yoga Mat (6mm)', price: 49.99, category: 'sporting_goods' },
    { name: 'Cycling Helmet', price: 79.99, category: 'sporting_goods' },
    { name: 'Resistance Bands Set', price: 29.99, category: 'sporting_goods' },
  ],
  'ctc-004': [ // Sport Chek — Yorkdale (suburban: more outdoor gear)
    { name: 'Camping Tent (2-person)', price: 189.99, category: 'outdoor' },
    { name: 'Walking Poles (pair)', price: 74.99, category: 'outdoor' },
    { name: 'Trail Running Shoes', price: 129.99, category: 'sporting_goods' },
    { name: 'Hiking Backpack (40L)', price: 119.99, category: 'outdoor' },
    { name: 'Sleeping Bag (-10C)', price: 99.99, category: 'outdoor' },
  ],
  'ctc-006': [ // Mark's — King St W (downtown: workwear + casual)
    { name: 'Winter Boots (insulated)', price: 154.99, category: 'apparel' },
    { name: 'Fleece-Lined Jacket', price: 94.99, category: 'apparel' },
    { name: 'Work Gloves (pack of 3)', price: 29.99, category: 'apparel' },
    { name: 'Steel-Toe Safety Shoes', price: 124.99, category: 'apparel' },
    { name: 'Thermal Underwear Set', price: 44.99, category: 'apparel' },
    { name: 'Waterproof Parka', price: 179.99, category: 'apparel' },
  ],
  'pcy-001': [ // Party City — North York
    { name: 'Birthday Party Pack (30-pc)', price: 29.99, category: 'seasonal' },
    { name: 'Balloon Bundle (25 latex)', price: 19.99, category: 'seasonal' },
    { name: 'Halloween Costume (adult)', price: 49.99, category: 'seasonal' },
    { name: 'Graduation Decor Kit', price: 34.99, category: 'seasonal' },
  ],
  'pcy-002': [ // Party City — Mississauga
    { name: 'Party Supplies Bundle', price: 39.99, category: 'seasonal' },
    { name: 'Balloon Bundle (25 latex)', price: 17.99, category: 'seasonal' },
    { name: 'Birthday Party Pack (30-pc)', price: 27.99, category: 'seasonal' },
    { name: 'Pinata (assorted)', price: 24.99, category: 'seasonal' },
  ],
  'th-001': [ // Tim Hortons — Front St
    { name: 'Double-Double + Breakfast Wrap Combo', price: 9.49, category: 'quick_meal' },
    { name: 'Family Timbits Pack (20)', price: 8.99, category: 'quick_meal' },
    { name: 'Iced Capp + Sandwich Combo', price: 10.99, category: 'quick_meal' },
    { name: 'Farmer\'s Breakfast Sandwich', price: 6.49, category: 'quick_meal' },
  ],
  'th-002': [ // Tim Hortons — Bloor & Bathurst
    { name: 'French Vanilla + Bagel Combo', price: 7.49, category: 'quick_meal' },
    { name: 'Steeped Tea + Donut Combo', price: 5.99, category: 'quick_meal' },
    { name: 'Chicken Wrap Combo', price: 11.49, category: 'quick_meal' },
    { name: 'Cold Brew + Muffin Combo', price: 7.99, category: 'quick_meal' },
  ],
  'th-bm-001': [ // Tim Hortons — Blue Mountain (ski resort, outdoor context)
    { name: 'Hot Chocolate + Muffin Combo', price: 8.49, category: 'quick_meal' },
    { name: 'Double-Double + Breakfast Wrap', price: 9.49, category: 'quick_meal' },
    { name: 'Large Coffee (to-go)', price: 3.49, category: 'quick_meal' },
    { name: 'Iced Capp (Large)', price: 5.49, category: 'quick_meal' },
  ],
  'th-wh-001': [ // Tim Hortons — Whistler Village (mountain resort)
    { name: 'Hot Chocolate + Donut', price: 7.49, category: 'quick_meal' },
    { name: 'Steeped Tea + Bagel Combo', price: 7.99, category: 'quick_meal' },
    { name: 'Double-Double + Timbits (10)', price: 8.49, category: 'quick_meal' },
    { name: 'French Vanilla (Large)', price: 4.49, category: 'quick_meal' },
  ],
  'ws-001': [ // Westside — Queen West
    { name: 'Air Fryer 5L', price: 89.99, category: 'home_living' },
    { name: 'Cotton Bedsheet Set (Queen)', price: 39.99, category: 'home_living' },
    { name: 'Kitchen Storage Container Set', price: 24.99, category: 'home_living' },
    { name: 'Aroma Diffuser', price: 34.99, category: 'home_living' },
  ],
  'ws-002': [ // Westside — North York
    { name: 'LED Floor Lamp', price: 59.99, category: 'home_living' },
    { name: 'Bathroom Organizer Rack', price: 29.99, category: 'home_living' },
    { name: 'Dinnerware Set (16-pc)', price: 74.99, category: 'home_living' },
    { name: 'Throw Blanket', price: 22.99, category: 'home_living' },
  ],
  'se-001': [ // Sports Experts — Toronto Eaton
    { name: 'Running Shoes Pro', price: 139.99, category: 'sporting_goods' },
    { name: 'Gym Duffel Bag', price: 49.99, category: 'sporting_goods' },
    { name: 'Smart Fitness Watch', price: 179.99, category: 'sporting_goods' },
    { name: 'Yoga Block Set', price: 24.99, category: 'sporting_goods' },
  ],
  'phl-001': [ // Pro Hockey Life — Vaughan
    { name: 'Composite Hockey Stick Elite', price: 179.99, category: 'sporting_goods' },
    { name: 'Hockey Gloves Pro', price: 99.99, category: 'sporting_goods' },
    { name: 'Skates Performance', price: 249.99, category: 'sporting_goods' },
    { name: 'Shoulder Pads Senior', price: 149.99, category: 'sporting_goods' },
  ],
};

// ── Triangle Points rates (pts per $1 spent) ───────────────────────────────────

const TIER_RATES: Record<string, number> = {
  gold: 15,
  platinum: 20,
  silver: 12,
  standard: 10,
};

const MEMBER_REWARDS_BALANCE: Record<string, number> = {
  'demo-001': 4620,
  'demo-002': 2780,
  'demo-003': 1930,
  'demo-004': 7340,
  'demo-005': 3210,
};

// ── Demo members ───────────────────────────────────────────────────────────────

const DEMO_MEMBERS = [
  { id: 'demo-001', label: 'Alice Chen — Outdoor/Gold', tier: 'gold', firstName: 'Alice' },
  { id: 'demo-002', label: 'Marcus Singh — Urban Commuter/Silver', tier: 'silver', firstName: 'Marcus' },
  { id: 'demo-003', label: 'Helen Park — Seasonal Home/Standard', tier: 'standard', firstName: 'Helen' },
  { id: 'demo-004', label: 'James Okoro — Family Shopper/Platinum', tier: 'platinum', firstName: 'James' },
  { id: 'demo-005', label: 'Raj Patel — Auto Parts/Standard', tier: 'standard', firstName: 'Raj' },
];

// ── Past purchase history per customer ────────────────────────────────────────

const MEMBER_PURCHASE_HISTORY: Record<string, Array<{
  item: string;
  store: string;
  date: string;
  amount: number;
}>> = {
  'demo-001': [
    { item: 'Camping Tent (2-person)', store: 'Sport Chek — Yorkdale', date: '2026-03-15', amount: 199.99 },
    { item: 'Walking Poles (pair)', store: 'Sport Chek — Eaton Centre', date: '2026-03-01', amount: 79.99 },
    { item: 'Trail Running Shoes', store: 'Sport Chek — Yorkdale', date: '2026-02-20', amount: 129.99 },
  ],
  'demo-002': [
    { item: 'Motor Oil 5W-30 (5L)', store: 'Canadian Tire — Queen St W', date: '2026-03-22', amount: 38.99 },
    { item: 'Windshield Wipers (pair)', store: 'Canadian Tire — Queen St W', date: '2026-03-10', amount: 24.99 },
    { item: 'Regular Unleaded (fill-up ~50L)', store: 'Petro-Canada — Queensway', date: '2026-02-28', amount: 72.00 },
    { item: 'Cycling Helmet', store: 'Sport Chek — Eaton Centre', date: '2026-02-14', amount: 79.99 },
  ],
  'demo-003': [
    { item: 'Ergonomic Snow Shovel', store: 'Canadian Tire — Scarborough', date: '2026-03-18', amount: 39.99 },
    { item: 'Birthday Party Pack (30-pc)', store: 'Party City — North York', date: '2026-03-05', amount: 29.99 },
    { item: 'Smoke Detector', store: 'Canadian Tire — Yonge & Eglinton', date: '2026-02-22', amount: 29.99 },
  ],
  'demo-004': [
    { item: 'Hockey Stick (Senior)', store: 'Sport Chek — Yorkdale', date: '2026-03-20', amount: 89.99 },
    { item: 'Yoga Mat (6mm)', store: 'Sport Chek — Eaton Centre', date: '2026-03-08', amount: 49.99 },
    { item: 'Fleece-Lined Jacket', store: "Mark's — King St W", date: '2026-02-25', amount: 89.99 },
    { item: 'Trail Running Shoes', store: 'Sport Chek — Yorkdale', date: '2026-02-10', amount: 129.99 },
    { item: 'Balloon Bundle (25 latex)', store: 'Party City — Mississauga', date: '2026-01-30', amount: 19.99 },
  ],
  'demo-005': [
    { item: 'Car Battery (Group 24)', store: 'Canadian Tire — Scarborough', date: '2026-03-25', amount: 129.99 },
    { item: 'Motor Oil 5W-30 (5L)', store: 'Canadian Tire — Queen St W', date: '2026-03-12', amount: 38.99 },
    { item: 'Power Drill Kit', store: 'Canadian Tire — Yonge & Eglinton', date: '2026-02-18', amount: 79.99 },
    { item: 'Premium Unleaded (fill-up ~50L)', store: 'Petro-Canada — Lawrence Ave', date: '2026-02-05', amount: 85.00 },
  ],
};

// ── Member clearance preferences (derived from purchase history) ───────────────

const MEMBER_CLEARANCE_PREFERENCES: Record<string, string[]> = {
  'demo-001': ['outdoor', 'hardware', 'sport'],      // Alice — outdoor gear
  'demo-002': ['automotive', 'hardware'],             // Marcus — commuter/auto
  'demo-003': ['seasonal', 'apparel', 'hardware'],   // Helen — home/seasonal
  'demo-004': ['sport', 'outdoor', 'apparel'],       // James — family/sport
  'demo-005': ['automotive', 'hardware'],             // Raj — auto parts
};

// ── Clearance suggestions ──────────────────────────────────────────────────────

interface ClearanceSuggestion {
  name: string;
  storeName: string;
  storeLat: number;
  storeLon: number;
  clearancePrice: number;
  originalPrice: number;
  marketplacePrice: number;
  unitsLeft: number;
  daysLeft: number;
  discountPct: number;
  tags: string[]; // For preference matching
}

const CLEARANCE_ITEMS: ClearanceSuggestion[] = [
  {
    name: 'Ergonomic Snow Shovel',
    storeName: 'Canadian Tire — Queen St W',
    storeLat: 43.6488, storeLon: -79.3981,
    clearancePrice: 27.99, originalPrice: 39.99, marketplacePrice: 54.99,
    unitsLeft: 400, daysLeft: 14, discountPct: 30,
    tags: ['outdoor', 'hardware', 'seasonal'],
  },
  {
    name: 'AAA Batteries 20-Pack',
    storeName: 'Canadian Tire — Yonge & Eglinton',
    storeLat: 43.7060, storeLon: -79.3985,
    clearancePrice: 12.99, originalPrice: 18.99, marketplacePrice: 22.99,
    unitsLeft: 350, daysLeft: 12, discountPct: 32,
    tags: ['hardware', 'seasonal', 'general'],
  },
  {
    name: 'Insulated Walking Poles',
    storeName: 'Sport Chek — Yorkdale',
    storeLat: 43.7243, storeLon: -79.4508,
    clearancePrice: 47.99, originalPrice: 79.99, marketplacePrice: 89.99,
    unitsLeft: 180, daysLeft: 18, discountPct: 40,
    tags: ['outdoor', 'sport', 'apparel'],
  },
  {
    name: 'Snow Blower (electric)',
    storeName: 'Canadian Tire — Scarborough',
    storeLat: 43.7731, storeLon: -79.2576,
    clearancePrice: 174.99, originalPrice: 249.99, marketplacePrice: 299.99,
    unitsLeft: 85, daysLeft: 15, discountPct: 30,
    tags: ['outdoor', 'hardware', 'seasonal'],
  },
];

const CATEGORY_COMPLEMENTS: Record<string, string[]> = {
  automotive: ['hardware', 'fuel'],
  hardware: ['automotive', 'seasonal'],
  sporting_goods: ['outdoor', 'apparel'],
  outdoor: ['sporting_goods', 'apparel'],
  apparel: ['sporting_goods', 'outdoor'],
  seasonal: ['hardware', 'apparel'],
  fuel: ['automotive'],
  quick_meal: ['fuel', 'automotive', 'home_living'],
  home_living: ['seasonal', 'hardware', 'quick_meal'],
};

const ITEM_COMPLEMENTS: Array<{ keyword: string; relatedKeywords: string[] }> = [
  { keyword: 'motor oil', relatedKeywords: ['wiper', 'battery', 'compressor'] },
  { keyword: 'battery', relatedKeywords: ['oil', 'compressor', 'wiper'] },
  { keyword: 'trail running shoes', relatedKeywords: ['poles', 'backpack', 'helmet'] },
  { keyword: 'camping tent', relatedKeywords: ['sleeping bag', 'backpack', 'poles'] },
  { keyword: 'hockey stick', relatedKeywords: ['helmet', 'gloves', 'shoes'] },
  { keyword: 'snow shovel', relatedKeywords: ['blower', 'boots', 'heater'] },
  { keyword: 'birthday', relatedKeywords: ['balloon', 'supplies', 'pinata'] },
  { keyword: 'double-double', relatedKeywords: ['breakfast', 'bagel', 'sandwich'] },
  { keyword: 'air fryer', relatedKeywords: ['storage', 'dinnerware', 'organizer'] },
];

// ── Petro-Canada stations ──────────────────────────────────────────────────────

const PETRO_STATIONS = [
  { name: 'Petro-Canada — Queensway', lat: 43.6325, lon: -79.5020 },
  { name: 'Petro-Canada — Lawrence Ave', lat: 43.7241, lon: -79.4318 },
  { name: 'Petro-Canada — Yonge & Finch', lat: 43.7800, lon: -79.4141 },
];

// ── External partner brands (non-CTC family — use partner trigger endpoint) ───

const EXTERNAL_PARTNER_BRANDS = new Set<StoreFixture['brand']>([
  'tim_hortons',
  'petro_canada',
  'party_city',
  'westside',
  'sports_experts',
  'pro_hockey_life',
]);

// ── Haversine distance ─────────────────────────────────────────────────────────

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.asin(Math.sqrt(a));
}

function getRelevantClearanceItem(
  memberId: string,
  storeLat: number,
  storeLon: number,
  purchaseCategory: string,
): (ClearanceSuggestion & { distanceKm: number }) | null {
  const prefs = MEMBER_CLEARANCE_PREFERENCES[memberId] ?? [];
  const scored = CLEARANCE_ITEMS.map((c) => {
    const distanceKm = haversineKm(storeLat, storeLon, c.storeLat, c.storeLon);
    const prefMatch = prefs.some((p) => c.tags.includes(p));
    const purchaseMatch = c.tags.includes(purchaseCategory);
    return { ...c, distanceKm, prefMatch, purchaseMatch };
  }).sort((a, b) => {
    if (a.purchaseMatch && !b.purchaseMatch) return -1;
    if (!a.purchaseMatch && b.purchaseMatch) return 1;
    if (a.prefMatch && !b.prefMatch) return -1;
    if (!a.prefMatch && b.prefMatch) return 1;
    return a.distanceKm - b.distanceKm;
  });
  return scored[0] ?? null;
}

function nearestPetro(lat: number, lon: number): { name: string; distanceKm: number } | null {
  const scored = PETRO_STATIONS.map((p) => ({
    name: p.name,
    distanceKm: haversineKm(lat, lon, p.lat, p.lon),
  })).sort((a, b) => a.distanceKm - b.distanceKm);
  return scored[0] ?? null;
}

function normalizeText(value: string): string {
  return value.toLowerCase().trim();
}

function findCategoryForItemName(itemName: string): string | null {
  const normalizedItemName = normalizeText(itemName);
  const allItems = [...Object.values(STORE_ITEMS).flat(), ...Object.values(STORE_INVENTORY).flat()];
  const matched = allItems.find((item) => normalizeText(item.name) === normalizedItemName);
  return matched?.category ?? null;
}

function getMemberCategoryAffinity(memberId: string): Record<string, number> {
  const history = MEMBER_PURCHASE_HISTORY[memberId] ?? [];
  return history.reduce<Record<string, number>>((acc, purchase) => {
    const category = findCategoryForItemName(purchase.item);
    if (!category) return acc;
    acc[category] = (acc[category] ?? 0) + 1;
    return acc;
  }, {});
}

interface NextBestItemSuggestion {
  item: StoreItem;
  reason: string;
  confidence: number;
  predictedDiscountPct: number;
}

function predictNextBestItem(
  memberId: string,
  availableItems: StoreItem[],
  purchasedItem: StoreItem,
): NextBestItemSuggestion | null {
  const affinity = getMemberCategoryAffinity(memberId);
  const purchasedCategory = purchasedItem.category;
  const complementaryCategories = CATEGORY_COMPLEMENTS[purchasedCategory] ?? [];
  const purchasedName = normalizeText(purchasedItem.name);

  const relatedItemKeywords =
    ITEM_COMPLEMENTS.find((rule) => purchasedName.includes(rule.keyword))?.relatedKeywords ?? [];

  const candidates = availableItems
    .filter((item) => item.name !== purchasedItem.name)
    .map((item) => {
      const itemName = normalizeText(item.name);
      const sameCategoryScore = item.category === purchasedCategory ? 30 : 0;
      const complementaryCategoryScore = complementaryCategories.includes(item.category) ? 26 : 0;
      const affinityScore = (affinity[item.category] ?? 0) * 12;
      const relatedItemScore = relatedItemKeywords.some((kw) => itemName.includes(kw)) ? 24 : 0;
      const priceBandScore = item.price >= purchasedItem.price * 0.6 && item.price <= purchasedItem.price * 1.6
        ? 8
        : 0;
      const totalScore =
        sameCategoryScore +
        complementaryCategoryScore +
        affinityScore +
        relatedItemScore +
        priceBandScore;

      return { item, totalScore, sameCategoryScore, complementaryCategoryScore, relatedItemScore };
    })
    .sort((a, b) => b.totalScore - a.totalScore);

  const best = candidates[0];
  if (!best) return null;

  let reason = 'Predicted from purchase pattern and member history';
  if (best.relatedItemScore > 0) {
    reason = `Frequently paired with ${purchasedItem.name.toLowerCase()}`;
  } else if (best.complementaryCategoryScore > 0) {
    reason = `Likely next need from ${best.item.category.replace('_', ' ')} category`;
  } else if (best.sameCategoryScore > 0) {
    reason = 'Strong same-category continuation signal';
  }

  return {
    item: best.item,
    reason,
    confidence: Math.min(99, Math.max(42, Math.round(best.totalScore))),
    predictedDiscountPct: best.relatedItemScore > 0 ? 22 : 15,
  };
}

// ── Canadian date context derivation ─────────────────────────────────────────

function getToday(): string {
  return new Date().toISOString().split('T')[0];
}

/** Easter Sunday using Meeus/Jones/Butcher algorithm */
function getEaster(year: number): Date {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31) - 1;
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(year, month, day);
}

/** Nth occurrence of a weekday in a month (0=Sun … 6=Sat, nth=1-based) */
function nthWeekday(year: number, month: number, weekday: number, nth: number): Date {
  const first = new Date(year, month, 1);
  const offset = (weekday - first.getDay() + 7) % 7;
  return new Date(year, month, 1 + offset + (nth - 1) * 7);
}

/** Last occurrence of a weekday in a month */
function lastWeekday(year: number, month: number, weekday: number): Date {
  const lastDay = new Date(year, month + 1, 0).getDate();
  const d = new Date(year, month, lastDay);
  const offset = (d.getDay() - weekday + 7) % 7;
  return new Date(year, month, lastDay - offset);
}

function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

interface DateContext {
  dayContext: 'weekday' | 'weekend' | 'long_weekend';
  occasion: string | null;
}

function deriveDateContext(dateStr: string): DateContext {
  // Use noon to avoid any DST/timezone boundary issues
  const date = new Date(`${dateStr}T12:00:00`);
  const year = date.getFullYear();
  const month = date.getMonth();
  const dow = date.getDay(); // 0=Sun, 6=Sat
  const isWeekend = dow === 0 || dow === 6;

  const easter = getEaster(year);
  const goodFriday = new Date(easter.getFullYear(), easter.getMonth(), easter.getDate() - 2);
  const easterMonday = new Date(easter.getFullYear(), easter.getMonth(), easter.getDate() + 1);

  // Victoria Day: last Monday on or before May 24 (= Monday before May 25)
  const may25 = new Date(year, 4, 25);
  const may25dow = may25.getDay();
  const victoriaDay = new Date(year, 4, 25 - (may25dow === 1 ? 7 : (may25dow + 6) % 7));

  const canadaDay = new Date(year, 6, 1);
  // Canada Day observed on Monday if it falls on Sunday
  const canadaDayObserved =
    canadaDay.getDay() === 0 ? new Date(year, 6, 2) : canadaDay;

  const labourDay = nthWeekday(year, 8, 1, 1);   // First Monday in September
  const thanksgiving = nthWeekday(year, 9, 1, 2); // Second Monday in October
  const familyDay = nthWeekday(year, 1, 1, 3);    // Third Monday in February (Ontario)
  const civicHoliday = nthWeekday(year, 7, 1, 1); // First Monday in August

  const statHolidays: Array<{ date: Date; name: string }> = [
    { date: new Date(year, 0, 1), name: "New Year's Day" },
    { date: familyDay, name: 'Family Day' },
    { date: goodFriday, name: 'Good Friday' },
    { date: easterMonday, name: 'Easter Monday' },
    { date: victoriaDay, name: 'Victoria Day' },
    { date: canadaDayObserved, name: 'Canada Day' },
    { date: civicHoliday, name: 'Civic Holiday' },
    { date: labourDay, name: 'Labour Day' },
    { date: thanksgiving, name: 'Thanksgiving' },
    { date: new Date(year, 10, 11), name: 'Remembrance Day' },
    { date: new Date(year, 11, 25), name: 'Christmas Day' },
    { date: new Date(year, 11, 26), name: 'Boxing Day' },
    { date: new Date(year, 11, 31), name: "New Year's Eve" },
  ];

  const specialOccasions: Array<{ date: Date; name: string }> = [
    { date: new Date(year, 1, 14), name: "Valentine's Day" },
    { date: new Date(year, 2, 17), name: "St. Patrick's Day" },
    { date: new Date(year, 9, 31), name: 'Halloween' },
    { date: nthWeekday(year, 4, 0, 2), name: "Mother's Day" },    // 2nd Sun May
    { date: nthWeekday(year, 5, 0, 3), name: "Father's Day" },    // 3rd Sun June
    { date: lastWeekday(year, 10, 0), name: 'Grey Cup' },          // Last Sun Nov
    { date: nthWeekday(year, 1, 0, 1), name: 'Super Bowl Sunday' }, // 1st Sun Feb
    { date: nthWeekday(year, 0, 0, 1), name: 'New Year Deals Weekend' }, // 1st Sun Jan
  ];

  // Long weekend: stat holiday falls on Mon or Fri, making 3-day weekend
  const isLongWeekend = statHolidays.some((h) => {
    const hdow = h.date.getDay();
    if (hdow === 1) {
      // Monday holiday → Sat + Sun before it are part of long weekend
      const sat = new Date(h.date.getFullYear(), h.date.getMonth(), h.date.getDate() - 2);
      const sun = new Date(h.date.getFullYear(), h.date.getMonth(), h.date.getDate() - 1);
      return isSameDay(h.date, date) || isSameDay(sat, date) || isSameDay(sun, date);
    }
    if (hdow === 5) {
      // Friday holiday → Sat + Sun after it are part of long weekend
      const sat = new Date(h.date.getFullYear(), h.date.getMonth(), h.date.getDate() + 1);
      const sun = new Date(h.date.getFullYear(), h.date.getMonth(), h.date.getDate() + 2);
      return isSameDay(h.date, date) || isSameDay(sat, date) || isSameDay(sun, date);
    }
    return isSameDay(h.date, date);
  });

  // Seasonal fallback label
  const seasonalLabel = (() => {
    if (month === 11 || month === 0) return 'Holiday Shopping Season';
    if (month === 1 || month === 2) return 'Winter Clearance Season';
    if (month === 3 || month === 4) return 'Spring Promotions';
    if (month === 5 || month === 6) return 'Summer Deals';
    if (month === 3 || (month === 4 || month === 5)) return 'NHL Playoffs Season';
    return 'NHL Regular Season';
  })();

  const holiday = statHolidays.find((h) => isSameDay(h.date, date));
  const special = specialOccasions.find((h) => isSameDay(h.date, date));
  const occasion = holiday?.name ?? special?.name ?? seasonalLabel;

  let dayContext: 'weekday' | 'weekend' | 'long_weekend';
  if (isLongWeekend) {
    dayContext = 'long_weekend';
  } else if (isWeekend) {
    dayContext = 'weekend';
  } else {
    dayContext = 'weekday';
  }

  return { dayContext, occasion };
}

// ── Personalized notification message generator ───────────────────────────────

function generatePersonalizedMessage(
  memberFirstName: string,
  itemName: string,
  occasion: string | null,
  nextItemName: string | null,
  nextItemDiscountPct: number | null,
): string {
  const greeting = occasion
    ? (() => {
        if (occasion.includes('Victoria Day')) return `Happy Victoria Day weekend, ${memberFirstName}!`;
        if (occasion.includes('Canada Day')) return `Happy Canada Day, ${memberFirstName}!`;
        if (occasion.includes('Christmas')) return `Merry Christmas, ${memberFirstName}!`;
        if (occasion.includes('Boxing Day')) return `Happy Boxing Day, ${memberFirstName}!`;
        if (occasion.includes("Valentine")) return `Happy Valentine's Day, ${memberFirstName}!`;
        if (occasion.includes('Halloween')) return `Happy Halloween, ${memberFirstName}!`;
        if (occasion.includes("Mother's")) return `Happy Mother's Day, ${memberFirstName}!`;
        if (occasion.includes("Father's")) return `Happy Father's Day, ${memberFirstName}!`;
        if (occasion.includes('Thanksgiving')) return `Happy Thanksgiving, ${memberFirstName}!`;
        if (occasion.includes('Winter Clearance')) return `Hey ${memberFirstName}! Winter is winding down --`;
        if (occasion.includes('Spring')) return `Spring is here, ${memberFirstName}!`;
        if (occasion.includes('Summer')) return `Summer vibes, ${memberFirstName}!`;
        if (occasion.includes('Holiday Shopping')) return `'Tis the season, ${memberFirstName}!`;
        return `Hey ${memberFirstName}!`;
      })()
    : `Hey ${memberFirstName}!`;

  const purchaseContext = `Since you picked up a ${itemName}`;

  if (nextItemName && nextItemDiscountPct != null) {
    return `${greeting} ${purchaseContext}, your next best offer is ${nextItemName} at ${nextItemDiscountPct}% off.`;
  }

  return `${greeting} ${purchaseContext}, check out exclusive Triangle deals nearby.`;
}

// ── Outcome badge colours ───────────────────────────────────────────────────────

const OUTCOME_STYLES: Record<string, string> = {
  activated: 'badge-success',
  queued: 'badge-warning',
  rate_limited: 'badge-danger',
};

// ── Component ──────────────────────────────────────────────────────────────────

export function ContextDashboard() {
  const [storeId, setStoreId] = useState(CTC_PARTNER_STORES[0].id);
  const [itemIndex, setItemIndex] = useState(0);
  const [memberId, setMemberId] = useState(DEMO_MEMBERS[0].id);
  const [selectedDate, setSelectedDate] = useState(getToday());

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScoutMatchResult | null>(null);
  const [isPartnerTrigger, setIsPartnerTrigger] = useState(false);
  const [partnerTriggerResponse, setPartnerTriggerResponse] = useState<PartnerTriggerApiResponse | null>(null);
  const [partnerGeneratedOffer, setPartnerGeneratedOffer] = useState<OfferBrief | null>(null);
  const [partnerPollStatus, setPartnerPollStatus] = useState<'idle' | 'polling' | 'found' | 'timeout'>('idle');
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [purchaseSummary, setPurchaseSummary] = useState<{
    store: StoreFixture;
    item: StoreItem;
    pointsEarned: number;
    currentRewardsPoints: number;
    totalRewardsPoints: number;
    memberId: string;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshCount, setRefreshCount] = useState(0);

  const store = CTC_PARTNER_STORES.find((s) => s.id === storeId) ?? CTC_PARTNER_STORES[0];
  const items = STORE_INVENTORY[store.id] ?? STORE_ITEMS[store.brand];
  const safeItemIndex = Math.min(itemIndex, items.length - 1);
  const item = items[safeItemIndex];
  const member = DEMO_MEMBERS.find((m) => m.id === memberId) ?? DEMO_MEMBERS[0];
  const currentRewardsPoints = MEMBER_REWARDS_BALANCE[member.id] ?? 0;
  const pointsEarned = Math.round(item.price * (TIER_RATES[member.tier] ?? 10));
  const totalRewardsPoints = currentRewardsPoints + pointsEarned;

  const { dayContext, occasion } = deriveDateContext(selectedDate);

  // Cleanup poll timer on unmount
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, []);

  function startPartnerOfferPoll(preIds: Set<string>) {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    setPartnerPollStatus('polling');
    let attempts = 0;
    const maxAttempts = 15; // 30 seconds at 2s intervals

    pollTimerRef.current = setInterval(async () => {
      attempts++;
      try {
        const res = await fetch('/api/hub-offers', { cache: 'no-store' });
        if (res.ok) {
          const data = await res.json();
          const newOffer = (data.offers ?? []).find(
            (o: OfferBrief) => !preIds.has(o.offer_id) && o.trigger_type === 'partner_triggered',
          );
          if (newOffer) {
            if (pollTimerRef.current) clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
            setPartnerGeneratedOffer(newOffer as OfferBrief);
            setPartnerPollStatus('found');
            return;
          }
        }
      } catch { /* keep polling */ }

      if (attempts >= maxAttempts) {
        if (pollTimerRef.current) clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
        setPartnerPollStatus('timeout');
      }
    }, 2000);
  }

  function handleStoreChange(newStoreId: string) {
    setStoreId(newStoreId);
    setItemIndex(0);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setPartnerTriggerResponse(null);
    setPartnerGeneratedOffer(null);
    setPartnerPollStatus('idle');
    if (pollTimerRef.current) { clearInterval(pollTimerRef.current); pollTimerRef.current = null; }
    setError(null);

    const summary = {
      store,
      item,
      pointsEarned,
      currentRewardsPoints,
      totalRewardsPoints,
      memberId: member.id,
    };

    try {
      if (EXTERNAL_PARTNER_BRANDS.has(store.brand)) {
        // Partner store — call partner trigger endpoint
        setIsPartnerTrigger(true);
        const eventId = `${store.id}-${member.id}-${Date.now()}`;
        const partnerEvent: PartnerPurchaseEvent = {
          event_id: eventId,
          partner_id: store.brand,
          partner_name: store.name,
          purchase_amount: item.price,
          purchase_category: item.category,
          member_id: member.id,
          timestamp: new Date(selectedDate + 'T12:00:00Z').toISOString(),
          location: { lat: store.lat, lon: store.lon },
          store_name: store.name,
        };

        // Snapshot existing offer IDs before firing so we can detect the new one
        let preIds = new Set<string>();
        try {
          const preRes = await fetch('/api/hub-offers', { cache: 'no-store' });
          if (preRes.ok) {
            const preData = await preRes.json();
            preIds = new Set((preData.offers ?? []).map((o: { offer_id: string }) => o.offer_id));
          }
        } catch { /* use empty set — polling will still work */ }

        const res = await callPartnerTrigger(partnerEvent);
        setPartnerTriggerResponse(res);
        // Synthetic no-match result so PushNotificationCard still renders purchase receipt
        setResult({ matches: [], message: res.message });

        // Start polling Hub for the newly generated CTC offer
        startPartnerOfferPoll(preIds);
      } else {
        // CTC family store — regular match scoring
        setIsPartnerTrigger(false);
        const request: MatchRequest = {
          member_id: member.id,
          purchase_location: { lat: store.lat, lon: store.lon },
          purchase_category: item.category,
          rewards_earned: pointsEarned,
          day_context: dayContext,
        };
        const res = await callScoutMatch(request);
        setResult(res);
      }
      setPurchaseSummary(summary);
      setRefreshCount((c) => c + 1);
    } catch (err) {
      const apiErr = err as ScoutMatchError;
      setError(apiErr?.detail ?? 'Unexpected error contacting Scout API');
    } finally {
      setLoading(false);
    }
  }

  // Compute recommended item for phone preview (mirrors PushNotificationCard logic)
  const _phoneStoreItems = purchaseSummary
    ? (STORE_INVENTORY[purchaseSummary.store.id] ?? STORE_ITEMS[purchaseSummary.store.brand])
    : null;
  const _phonePurchasedItem = purchaseSummary
    ? { name: purchaseSummary.item.name, price: purchaseSummary.item.price, category: purchaseSummary.item.category }
    : null;
  const _phoneNextBest = (_phoneStoreItems && _phonePurchasedItem && purchaseSummary)
    ? predictNextBestItem(purchaseSummary.memberId, _phoneStoreItems, _phonePurchasedItem)
    : null;
  const _phoneOfferPrice = _phoneNextBest
    ? _phoneNextBest.item.price * (1 - _phoneNextBest.predictedDiscountPct / 100)
    : null;
  const _phoneMaxRedeem = _phoneOfferPrice != null ? _phoneOfferPrice * 0.75 : null;
  const _phoneRewardsVal = purchaseSummary ? purchaseSummary.totalRewardsPoints * 0.01 : 0;
  const _phoneRedeem = _phoneOfferPrice != null && _phoneMaxRedeem != null
    ? Math.min(_phoneRewardsVal, _phoneMaxRedeem)
    : null;
  const _phoneYouPay = _phoneOfferPrice != null && _phoneRedeem != null
    ? Math.max(_phoneOfferPrice * 0.25, _phoneOfferPrice - _phoneRedeem)
    : null;
  const recommendedItemForPhone: RecommendedItem | null =
    (_phoneNextBest && _phoneOfferPrice != null && _phoneRedeem != null && _phoneYouPay != null && purchaseSummary)
      ? {
          name: _phoneNextBest.item.name,
          originalPrice: _phoneNextBest.item.price,
          offerPrice: _phoneOfferPrice,
          discountPct: _phoneNextBest.predictedDiscountPct,
          confidence: _phoneNextBest.confidence,
          reason: _phoneNextBest.reason,
          rewardsRedeemable: _phoneRedeem,
          youPay: _phoneYouPay,
          totalPointsAfter: purchaseSummary.totalRewardsPoints,
        }
      : null;
  const recommendationMsgForPhone = (purchaseSummary && result && isMatchResponse(result))
    ? generatePersonalizedMessage(
        member.firstName,
        purchaseSummary.item.name,
        occasion,
        _phoneNextBest?.item.name ?? null,
        _phoneNextBest?.predictedDiscountPct ?? null,
      )
    : undefined;

  return (
    <div className="space-y-6">
      {/* ── Purchase event form ── */}
      <form
        onSubmit={handleSubmit}
        className="card p-6 space-y-4"
      >
        <div>
          <h2 className="text-title text-gray-900">Purchase Event Simulator</h2>
          <p className="text-sm text-gray-400 mt-0.5">
            Simulate a CTC customer transaction to test context-based offer matching.
          </p>
        </div>

        {/* Customer */}
        <div>
          <label htmlFor="member" className="input-label flex items-center">
            <span className="material-symbols-outlined text-[16px] text-gray-400 mr-1" aria-hidden="true">person</span>
            Customer
          </label>
          <select
            id="member"
            value={memberId}
            onChange={(e) => setMemberId(e.target.value)}
            className="input"
          >
            {DEMO_MEMBERS.map((m) => (
              <option key={m.id} value={m.id}>{m.label}</option>
            ))}
          </select>
          {/* Past purchase history */}
          {MEMBER_PURCHASE_HISTORY[memberId] && (
            <div className="mt-2 rounded-md border border-gray-100 bg-gray-50/60 px-3 py-2">
              <p className="text-xs font-medium text-gray-500 mb-1.5">Recent purchases</p>
              <ul className="space-y-1">
                {MEMBER_PURCHASE_HISTORY[memberId].map((p, idx) => (
                  <li key={idx} className="flex items-center justify-between text-xs">
                    <span className="text-gray-700 truncate mr-2">{p.item}</span>
                    <span className="flex items-center gap-2 shrink-0">
                      <span className="text-gray-400">{p.store}</span>
                      <span className="text-gray-300">|</span>
                      <span className="text-gray-400">{p.date}</span>
                      <span className="font-medium text-gray-600">${p.amount.toFixed(2)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Store */}
        <div>
          <label htmlFor="store" className="input-label flex items-center">
            <span className="material-symbols-outlined text-[16px] text-gray-400 mr-1" aria-hidden="true">store</span>
            Store &amp; Branch
          </label>
          <select
            id="store"
            value={storeId}
            onChange={(e) => handleStoreChange(e.target.value)}
            className="input"
          >
            {(() => {
              const BRAND_LABELS: Record<StoreFixture['brand'], string> = {
                canadian_tire: 'Canadian Tire',
                sport_chek: 'Sport Chek',
                marks: "Mark's",
                petro_canada: 'Petro-Canada',
                party_city: 'Party City',
                tim_hortons: 'Tim Hortons',
                westside: 'Westside',
                sports_experts: 'Sports Experts',
                pro_hockey_life: 'Pro Hockey Life',
              };
              const groups: Partial<Record<StoreFixture['brand'], StoreFixture[]>> = {};
              for (const s of CTC_PARTNER_STORES) {
                if (!groups[s.brand]) groups[s.brand] = [];
                groups[s.brand]!.push(s);
              }
              return (Object.entries(groups) as [StoreFixture['brand'], StoreFixture[]][]).map(([brand, stores]) => (
                <optgroup key={brand} label={BRAND_LABELS[brand] ?? brand}>
                  {stores.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </optgroup>
              ));
            })()}
          </select>
        </div>

        {/* Item */}
        <div>
          <label htmlFor="item" className="input-label flex items-center">
            <span className="material-symbols-outlined text-[16px] text-gray-400 mr-1" aria-hidden="true">shopping_cart</span>
            Item Being Purchased
          </label>
          <select
            id="item"
            value={safeItemIndex}
            onChange={(e) => setItemIndex(Number(e.target.value))}
            className="input"
          >
            {items.map((it, i) => (
              <option key={i} value={i}>
                {it.name} — ${it.price.toFixed(2)}
              </option>
            ))}
          </select>
        </div>

        {/* Date picker + points preview */}
        <div className="grid grid-cols-2 gap-4">
          {/* Points earned preview */}
          <div className="rounded-md bg-emerald-50/50 border border-emerald-100 px-3 py-2.5">
            <p className="text-xs text-green-600 font-medium">Triangle Points earned</p>
            <p className="text-xl font-bold text-green-800 mt-0.5">
              +{pointsEarned.toLocaleString()} pts
              <span className="text-sm font-semibold text-green-600 ml-1">
                (~${(pointsEarned * 0.01).toFixed(2)} value)
              </span>
            </p>
            <p className="text-xs text-green-600 font-medium mt-1">
              Purchase total: ${item.price.toFixed(2)}
            </p>
            <p className="text-xs text-green-500 mt-0.5">
              {TIER_RATES[member.tier]} pts/$1 · {member.tier} tier
            </p>
            <p className="text-xs text-green-700 mt-1">
              Current balance: {currentRewardsPoints.toLocaleString()} pts
            </p>
            <p className="text-xs font-semibold text-green-800 mt-0.5">
              Total after purchase: {totalRewardsPoints.toLocaleString()} pts
            </p>
          </div>

          {/* Date picker */}
          <div>
            <label htmlFor="purchase-date" className="input-label flex items-center">
              <span className="material-symbols-outlined text-[16px] text-gray-400 mr-1" aria-hidden="true">calendar_today</span>
              Purchase Date
            </label>
            <input
              id="purchase-date"
              type="date"
              value={selectedDate}
              max={getToday()}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="input"
            />
            {occasion && (
              <p className="mt-1 text-xs font-medium text-red-600">{occasion}</p>
            )}
            <p className="mt-0.5 text-xs text-gray-400 capitalize">
              Day type: <span className="font-medium text-gray-600">{dayContext.replace('_', ' ')}</span>
            </p>
          </div>
        </div>

        <button
          type="submit"
          disabled={loading}
          className="btn-primary w-full"
        >
          {loading
            ? 'Processing Transaction...'
            : EXTERNAL_PARTNER_BRANDS.has(store.brand)
              ? 'Trigger Partner Cross-Sell'
              : 'Run Match Scoring'}
        </button>
      </form>

      {/* ── Error ── */}
      {error && (
        <div
          role="alert"
          className="card border-l-2 border-red-500 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {/* ── Partner trigger confirmation + inline offer ── */}
      {isPartnerTrigger && partnerTriggerResponse && (
        <div className="card overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-2 border-l-4 border-green-500 bg-green-50 px-4 py-3">
            <span className="material-symbols-outlined text-[16px] text-green-600" aria-hidden="true">bolt</span>
            <p className="text-sm font-semibold text-green-800">Partner Cross-Sell Triggered</p>
          </div>
          <div className="bg-green-50/50 px-4 py-2 border-b border-green-100">
            <p className="text-xs text-green-700">
              Purchase at <strong>{purchaseSummary?.store.name}</strong> received. Claude Haiku is classifying
              the purchase context and generating a personalised Canadian Tire offer.
            </p>
          </div>

          {/* Polling status */}
          {partnerPollStatus === 'polling' && (
            <div className="flex items-center gap-2 px-4 py-3 text-sm text-amber-700 bg-amber-50 border-b border-amber-100">
              <span className="inline-block animate-spin text-base leading-none">↻</span>
              Generating your Canadian Tire offer&hellip;
            </div>
          )}

          {/* Offer found — display inline */}
          {partnerPollStatus === 'found' && partnerGeneratedOffer && (
            <PartnerOfferCard offer={partnerGeneratedOffer} purchaseAmount={item.price} />
          )}

          {/* Timed out */}
          {partnerPollStatus === 'timeout' && (
            <div className="px-4 py-3 text-xs text-gray-500 border-t border-gray-100">
              Offer generation is taking longer than usual. Check the <strong>Hub</strong> for the generated offer.
            </div>
          )}
        </div>
      )}

      {/* ── Context signal indicators ── */}
      {result && purchaseSummary && (
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 border border-blue-200 px-2.5 py-1 text-xs font-medium text-blue-700">
            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">location_on</span>
            GPS: {haversineKm(
              purchaseSummary.store.lat, purchaseSummary.store.lon,
              purchaseSummary.store.lat + 0.005, purchaseSummary.store.lon + 0.003
            ).toFixed(1)} km proximity
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-purple-50 border border-purple-200 px-2.5 py-1 text-xs font-medium text-purple-700">
            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">schedule</span>
            {dayContext.replace('_', ' ')}
          </span>
          {occasion && (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-50 border border-red-200 px-2.5 py-1 text-xs font-medium text-red-700">
              <span className="material-symbols-outlined text-[14px]" aria-hidden="true">celebration</span>
              {occasion}
            </span>
          )}
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2.5 py-1 text-xs font-medium text-amber-700">
            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">workspace_premium</span>
            {member.tier} tier
          </span>
          <span className="inline-flex items-center gap-1 rounded-full bg-green-50 border border-green-200 px-2.5 py-1 text-xs font-medium text-green-700">
            <span className="material-symbols-outlined text-[14px]" aria-hidden="true">category</span>
            {purchaseSummary.item.category}
          </span>
        </div>
      )}

      {/* ── Two-column layout: mobile phone preview + detailed card ── */}
      {result && purchaseSummary && (
        <div className="flex flex-col xl:flex-row gap-6 items-start">

          {/* Left: iPhone mockup */}
          <div className="xl:sticky xl:top-6 flex-shrink-0 self-center xl:self-start">
            <MobileNotificationPreview
              memberFirstName={member.firstName}
              storeName={purchaseSummary.store.name}
              itemName={purchaseSummary.item.name}
              purchaseAmount={purchaseSummary.item.price}
              pointsEarned={purchaseSummary.pointsEarned}
              totalRewardsPoints={purchaseSummary.totalRewardsPoints}
              result={result}
              isPartnerTrigger={isPartnerTrigger}
              partnerBrandName={isPartnerTrigger ? purchaseSummary.store.name : undefined}
              partnerGeneratedOffer={partnerGeneratedOffer}
              recommendationMsg={recommendationMsgForPhone}
              recommendedItem={recommendedItemForPhone}
            />
          </div>

          {/* Right: rich detail card */}
          <div className="flex-1 min-w-0">
            <PushNotificationCard
              storeId={purchaseSummary.store.id}
              storeBrand={purchaseSummary.store.brand}
              storeName={purchaseSummary.store.name}
              itemName={purchaseSummary.item.name}
              itemCategory={purchaseSummary.item.category}
              purchaseAmount={purchaseSummary.item.price}
              pointsEarned={purchaseSummary.pointsEarned}
              currentRewardsPoints={purchaseSummary.currentRewardsPoints}
              totalRewardsPoints={purchaseSummary.totalRewardsPoints}
              storeLat={purchaseSummary.store.lat}
              storeLon={purchaseSummary.store.lon}
              memberId={purchaseSummary.memberId}
              memberFirstName={member.firstName}
              occasion={occasion}
              result={result}
            />
          </div>
        </div>
      )}

      {/* ── Activation history ── */}
      <ActivationFeed memberId={memberId} refreshTrigger={refreshCount} />
    </div>
  );
}

// ── Partner Offer Inline Card ─────────────────────────────────────────────────

function PartnerOfferCard({ offer, purchaseAmount }: { offer: OfferBrief; purchaseAmount?: number }) {
  const pushChannel = offer.channels.find((c) => c.channel_type === 'push');

  // Payment split calculation — 75/25 Triangle Rewards rule
  const discountPct = offer.construct.value ?? 15;
  // Use purchase amount for savings context; fallback to a representative $50 if not provided
  const baseAmount = purchaseAmount ?? 50;
  const offerValue = baseAmount * (discountPct / 100);
  const maxPoints = offerValue * 0.75;
  const minCard = offerValue * 0.25;
  const netYouPay = baseAmount - maxPoints; // base - max points redeemable toward this offer

  return (
    <div className="px-4 py-4 bg-white">
      <div className="flex items-center gap-1.5 mb-2">
        <span className="material-symbols-outlined text-[16px] text-ct-red" aria-hidden="true">local_offer</span>
        <p className="text-sm font-semibold text-gray-900">Canadian Tire Offer Generated</p>
        <span className="badge badge-success capitalize text-[10px]">{offer.status}</span>
        <code className="text-[10px] text-gray-400 font-mono ml-auto">{offer.offer_id.slice(0, 8)}</code>
      </div>
      <p className="text-sm text-gray-700 leading-snug">{offer.objective}</p>

      {/* Offer headline */}
      <div className="mt-2 flex items-center gap-3">
        <span className="text-xl font-bold text-ct-red">{discountPct}% off</span>
        <span className="text-xs text-gray-500">{offer.construct.description}</span>
      </div>

      {/* Push message */}
      {pushChannel?.message_template && (
        <p className="mt-2 rounded bg-gray-50 px-3 py-2 text-xs italic leading-snug text-gray-600">
          &ldquo;{pushChannel.message_template}&rdquo;
        </p>
      )}

      {/* 75/25 Payment breakdown */}
      <div className="mt-3 rounded-lg border border-emerald-100 bg-emerald-50/60 px-3 py-2.5 space-y-1">
        <p className="text-[11px] font-semibold text-gray-500 uppercase tracking-wide mb-1.5">
          How to pay with Triangle Rewards
        </p>
        <div className="flex items-center justify-between text-[12px]">
          <span className="text-gray-600">Savings on <span className="font-medium text-gray-800">{offer.construct.description.replace('15% off ', '').replace(' at Canadian Tire', '')}</span></span>
          <span className="font-semibold text-gray-800">−${offerValue.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between text-[12px]">
          <span className="text-green-700">Triangle Points (max 75%)</span>
          <span className="font-medium text-green-700">up to −${maxPoints.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between text-[12px]">
          <span className="text-gray-500">Card (min 25%)</span>
          <span className="text-gray-500">min ${minCard.toFixed(2)}</span>
        </div>
        <div className="flex items-center justify-between text-[12px] border-t border-emerald-100 pt-1.5 mt-0.5">
          <span className="font-bold text-emerald-800">You pay (estimated)</span>
          <span className="text-base font-bold text-emerald-800">${netYouPay.toFixed(2)}</span>
        </div>
        <p className="text-[10px] text-gray-400 mt-0.5">
          Price calculated for <span className="font-medium">{offer.construct.description.replace('15% off ', '').replace(' at Canadian Tire', '')}</span> · Based on ${baseAmount.toFixed(2)} spend · Min 25% by card per Triangle Rewards rules.
        </p>
      </div>

      {offer.valid_until && (
        <p className="mt-2 text-[11px] text-gray-400">
          Valid until {new Date(offer.valid_until).toLocaleString()}
        </p>
      )}
    </div>
  );
}

// ── Push Notification Card ─────────────────────────────────────────────────────

interface PushNotificationCardProps {
  storeId: string;
  storeBrand: StoreFixture['brand'];
  storeName: string;
  itemName: string;
  itemCategory: string;
  purchaseAmount: number;
  pointsEarned: number;
  currentRewardsPoints: number;
  totalRewardsPoints: number;
  storeLat: number;
  storeLon: number;
  memberId: string;
  memberFirstName: string;
  occasion: string | null;
  result: ScoutMatchResult;
}

function PushNotificationCard({
  storeId,
  storeBrand,
  storeName,
  itemName,
  itemCategory,
  purchaseAmount,
  pointsEarned,
  currentRewardsPoints,
  totalRewardsPoints,
  storeLat,
  storeLon,
  memberId,
  memberFirstName,
  occasion,
  result,
}: PushNotificationCardProps) {
  const storeItems = STORE_INVENTORY[storeId] ?? STORE_ITEMS[storeBrand];
  const purchasedItem: StoreItem = {
    name: itemName,
    price: purchaseAmount,
    category: itemCategory,
  };
  const nextBestItem = predictNextBestItem(memberId, storeItems, purchasedItem);
  const petro = nearestPetro(storeLat, storeLon);
  const hasMatch = isMatchResponse(result);
  const totalRewardsValue = totalRewardsPoints * 0.01;
  const discountedNextItemPrice = nextBestItem
    ? nextBestItem.item.price * (1 - nextBestItem.predictedDiscountPct / 100)
    : null;
  // Triangle Rewards rule: max 75% of any transaction payable in points, min 25% by card
  const maxRedeemable =
    discountedNextItemPrice != null ? discountedNextItemPrice * 0.75 : null;
  const redeemValue =
    discountedNextItemPrice != null && maxRedeemable != null
      ? Math.min(totalRewardsValue, maxRedeemable)
      : null;
  const amountAfterRewards =
    discountedNextItemPrice != null && redeemValue != null
      ? Math.max(discountedNextItemPrice * 0.25, discountedNextItemPrice - redeemValue)
      : null;
  const personalizedMsg = generatePersonalizedMessage(
    memberFirstName,
    itemName,
    occasion,
    nextBestItem?.item.name ?? null,
    nextBestItem?.predictedDiscountPct ?? null,
  );

  return (
    <div className="card overflow-hidden">
      {/* Notification header */}
      <div className="bg-ct-red px-4 py-3 flex items-center gap-3">
        <div className="flex-shrink-0 w-7 h-7 bg-white rounded flex items-center justify-center">
          <span className="text-ct-red text-[10px] font-bold">CT</span>
        </div>
        <div>
          <p className="text-white font-semibold text-sm">Canadian Tire</p>
          <p className="text-red-200 text-xs">Triangle Rewards</p>
        </div>
        <span className="ml-auto text-red-200 text-xs">now</span>
      </div>

      {/* Transaction receipt */}
      <div className="px-4 py-3 border-b border-gray-100">
        <p className="text-xs text-gray-400 mb-1">Purchase recorded at {storeName}</p>
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-gray-900">{itemName}</p>
            <p className="text-sm text-gray-500 mt-0.5">${purchaseAmount.toFixed(2)}</p>
          </div>
          <div className="text-right">
            <p className="text-xs text-gray-400">Points earned</p>
            <p className="text-lg font-bold text-green-700">+{pointsEarned.toLocaleString()}</p>
            <p className="text-xs text-green-500">
              ~${(pointsEarned * 0.01).toFixed(2)} value · Triangle Points™
            </p>
            <p className="mt-1 text-xs text-gray-500">
              Total balance: {totalRewardsPoints.toLocaleString()} pts (${totalRewardsValue.toFixed(2)})
            </p>
          </div>
        </div>
      </div>

      {/* ── Smart Recommendation — combines personalized offer + AI next-item ── */}
      {hasMatch && (
        <div className="px-4 py-3 border-b border-gray-100 bg-gradient-to-br from-emerald-50/60 to-white">
          {/* Header */}
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <span className="material-symbols-outlined text-[16px] text-emerald-600" aria-hidden="true">smart_toy</span>
              <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide">Smart Recommendation for You</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-gray-400">
                AI confidence&nbsp;
                <span className={result.score > 80 ? 'font-semibold text-green-700' : result.score > 60 ? 'font-semibold text-yellow-700' : 'font-semibold text-red-600'}>
                  {result.score.toFixed(0)}/100
                </span>
              </span>
              <span className={`badge capitalize ${OUTCOME_STYLES[result.outcome] ?? 'badge-neutral'}`}>
                {result.outcome.replace('_', ' ')}
              </span>
            </div>
          </div>

          {/* Personalized message */}
          <p className="text-sm text-gray-800 leading-snug font-medium">{personalizedMsg}</p>
          {result.notification_text && (
            <p className="text-xs text-gray-500 mt-1 italic leading-snug">{result.notification_text}</p>
          )}

          {/* Status notices */}
          {result.outcome === 'queued' && result.delivery_time && (
            <div className="mt-2 flex items-center gap-1 rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">
              <span className="material-symbols-outlined text-[13px]" aria-hidden="true">schedule</span>
              Scheduled for delivery at {result.delivery_time} (outside notification hours)
            </div>
          )}
          {result.outcome === 'rate_limited' && result.retry_after_seconds != null && (
            <div className="mt-2 flex items-center gap-1 rounded bg-orange-50 px-2 py-1 text-xs text-orange-700">
              <span className="material-symbols-outlined text-[13px]" aria-hidden="true">info</span>
              {result.retry_after_seconds < 120
                ? 'A notification was sent very recently — will refresh momentarily'
                : `Notification already sent recently — next available in ${Math.ceil(result.retry_after_seconds / 60)} min`}
            </div>
          )}

          {/* AI next-item prediction with pricing breakdown */}
          {nextBestItem && discountedNextItemPrice != null && redeemValue != null && amountAfterRewards != null && (
            <div className="mt-3 border-t border-emerald-100 pt-3">
              <div className="mb-2 flex items-center gap-1.5">
                <span className="material-symbols-outlined text-[14px] text-emerald-600" aria-hidden="true">psychology</span>
                <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">You might also need…</p>
                <span className="rounded-full border border-emerald-100 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">
                  {nextBestItem.confidence}/100 match · {nextBestItem.predictedDiscountPct}% off
                </span>
              </div>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900">{nextBestItem.item.name}</p>
                  <p className="mt-0.5 text-xs leading-snug text-gray-600">{nextBestItem.reason}</p>
                  <div className="mt-1.5 flex items-center gap-1 text-xs text-emerald-700">
                    <span className="material-symbols-outlined text-[12px]" aria-hidden="true">stars</span>
                    {currentRewardsPoints.toLocaleString()} + {pointsEarned.toLocaleString()} pts = {totalRewardsPoints.toLocaleString()} pts total
                  </div>
                </div>
                {/* Offer pricing breakdown */}
                <div className="min-w-[136px] shrink-0 space-y-0.5 rounded-lg border border-emerald-100 bg-white px-3 py-2 text-right shadow-sm">
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-[11px] text-gray-400">Original</span>
                    <span className="text-[11px] text-gray-400 line-through">${nextBestItem.item.price.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-[11px] text-gray-600">Offer price</span>
                    <span className="text-[11px] font-semibold text-gray-800">${discountedNextItemPrice.toFixed(2)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-[11px] text-green-600">Rewards (max 75%)</span>
                    <span className="text-[11px] font-medium text-green-600">-${redeemValue.toFixed(2)}</span>
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-4 border-t border-emerald-100 pt-1">
                    <span className="text-xs font-bold text-emerald-800">You pay (min 25%)</span>
                    <span className="text-sm font-bold text-emerald-800">${amountAfterRewards.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {!hasMatch && (
        <div className="border-b border-gray-100 bg-gray-50 px-4 py-3">
          <div className="flex items-center gap-1.5">
            <span className="material-symbols-outlined text-[15px] text-gray-400" aria-hidden="true">info</span>
            <p className="text-sm italic text-gray-500">{result.message}</p>
          </div>
        </div>
      )}

      {/* Petro-Canada fuel redemption */}
      {petro && (
        <div className="px-4 py-3 bg-blue-50">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
            Fuel savings — redeem points
          </p>
          <p className="text-sm text-blue-900 font-medium">Save $0.03/L at Petro-Canada</p>
          <p className="text-xs text-blue-700 mt-0.5">
            Nearest: {petro.name} — {petro.distanceKm.toFixed(1)} km away
          </p>
          <p className="text-xs text-blue-600 mt-0.5">
            {totalRewardsPoints >= 1000
              ? `${totalRewardsPoints.toLocaleString()} pts = ~$${(totalRewardsPoints / 1000 * 0.03 * 50).toFixed(2)} saved on a 50L fill-up`
              : 'Accumulate more points for maximum fuel discount'}
          </p>
        </div>
      )}
    </div>
  );
}
