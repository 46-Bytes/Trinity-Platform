/**
 * Deterministic fixtures for the Value / General Dashboard.
 *
 * The value-uplift algorithm and its endpoints do not exist yet. This module
 * synthesises a full, self-consistent portfolio so the UI can be built, reviewed
 * and demoed ahead of the backend. Delete this file once the real API lands -
 * only valueDashboardService.ts imports it.
 *
 * Everything is derived from fixed seeds and fixed dates. There is no Math.random()
 * and no `new Date()`, so the numbers never change between renders or reloads, and
 * every figure reconciles: each point on a value series is the previous point plus
 * the events recorded at it, and a driver's attributed contribution is the sum of
 * its own events.
 */

import type {
  BusinessValue,
  EngagementStatus,
  PortfolioDriverAverage,
  PortfolioValue,
  ValueDriver,
  ValueEvent,
  ValuePoint,
  ValueSource,
} from './valueDashboardService';
import { VALUE_BUILDER_MODULES, VALUE_DRIVER_CODES, driverStatusFromScore } from './valueDrivers';

/** 13 month-ends, oldest to newest. Fixed so the fixtures never drift. */
const MONTHS = [
  '2025-07-01',
  '2025-08-01',
  '2025-09-01',
  '2025-10-01',
  '2025-11-01',
  '2025-12-01',
  '2026-01-01',
  '2026-02-01',
  '2026-03-01',
  '2026-04-01',
  '2026-05-01',
  '2026-06-01',
  '2026-07-01',
];

/**
 * How briskly a business is moving. Drives how often changes get recorded, how
 * large each movement is, and how much the driver scores lift.
 */
type Momentum = 'high' | 'steady' | 'flat' | 'declining';

interface MomentumProfile {
  /** Probability that a given month records at least one change. */
  eventChance: number;
  /** Movement size as a fraction of baseline value, [min, max]. */
  deltaRange: [number, number];
  /** Driver score lift per attributed change. */
  scoreLiftPerEvent: number;
}

const MOMENTUM: Record<Momentum, MomentumProfile> = {
  high: { eventChance: 0.8, deltaRange: [0.012, 0.034], scoreLiftPerEvent: 0.5 },
  steady: { eventChance: 0.55, deltaRange: [0.006, 0.018], scoreLiftPerEvent: 0.35 },
  flat: { eventChance: 0.22, deltaRange: [0.002, 0.008], scoreLiftPerEvent: 0.15 },
  declining: { eventChance: 0.5, deltaRange: [-0.02, 0.005], scoreLiftPerEvent: 0.1 },
};

/**
 * Per-module starting bias, in score points.
 *
 * Without this every driver regresses to the same portfolio average and the
 * driver chart reads as eleven identical bars. The shape here also matches what
 * the Value Builder methodology actually finds in the field: financials, systems
 * and sales get worked first, while owner independence and succession-risk
 * drivers are the ones left sitting red.
 */
const DRIVER_BASELINE_BIAS: Record<string, number> = {
  V1: 1.6,
  V2: 0.2,
  V3: -0.1,
  V4: -0.8,
  V5: 1.0,
  V6: -0.3,
  V7: 0.8,
  V8: -0.4,
  V9: -1.3,
  V10: 0.3,
  V11: -0.9,
};

/** Changes an owner or advisor might record, keyed by the driver they move. */
const EVENT_LABELS: Record<string, string[]> = {
  V1: [
    'Rebuilt the monthly management reporting pack',
    'Implemented 13-week cash flow forecasting',
    'Cleaned up the debtor ledger and tightened payment terms',
  ],
  V2: ['Completed a three-year strategic plan', 'Ran the first quarterly planning offsite'],
  V3: [
    'Established a weekly leadership meeting rhythm',
    'Rolled out a company-wide communications cadence',
  ],
  V4: [
    'Documented role scorecards for every key position',
    'Introduced a formal performance review cycle',
    'Hired an operations manager',
  ],
  V5: ['Documented the core operating procedures', 'Automated the job scheduling workflow'],
  V6: ['Migrated to a cloud ERP', 'Consolidated three systems onto one platform'],
  V7: ['Built a repeatable sales pipeline process', 'Launched a referral partner program'],
  V8: ['Registered trade marks for the core brand', 'Formalised the proprietary service method'],
  V9: [
    'Removed the owner from daily operations',
    'Handed key client relationships to the general manager',
  ],
  V10: ['Added a recurring revenue service line', 'Opened a second service territory'],
  V11: [
    'Renegotiated the premises lease to a 5+5 term',
    'Completed a compliance and insurance review',
  ],
};

interface BusinessSeed {
  engagementId: string;
  businessName: string;
  clientName: string;
  advisorName: string;
  firmName: string;
  industry: string;
  tool: 'value_builder' | 'sale_ready';
  engagementStatus: EngagementStatus;
  /** Value at the baseline appraisal, in AUD. */
  baselineValue: number;
  momentum: Momentum;
  /** Month index at which the advisor recorded a formal re-appraisal, or -1 for none. */
  reappraisalMonth: number;
  /** PRNG seed. Changing it reshuffles this business only. */
  seed: number;
}

const BUSINESS_SEEDS: BusinessSeed[] = [
  {
    engagementId: 'eng-harbourline',
    businessName: 'Harbourline Logistics',
    clientName: 'Dana Whitcombe',
    advisorName: 'Emma Thompson',
    firmName: 'Benchmark Business Advisory',
    industry: 'Transport & Logistics',
    tool: 'value_builder',
    engagementStatus: 'active',
    baselineValue: 2_100_000,
    momentum: 'high',
    reappraisalMonth: 8,
    seed: 1017,
  },
  {
    engagementId: 'eng-coastwide',
    businessName: 'Coastwide Plumbing Group',
    clientName: 'Rhys Callaghan',
    advisorName: 'Emma Thompson',
    firmName: 'Benchmark Business Advisory',
    industry: 'Trades & Construction',
    tool: 'value_builder',
    engagementStatus: 'active',
    baselineValue: 1_450_000,
    momentum: 'steady',
    reappraisalMonth: -1,
    seed: 2044,
  },
  {
    engagementId: 'eng-nova-precision',
    businessName: 'Nova Precision Engineering',
    clientName: 'Priya Raman',
    advisorName: 'Marcus Webb',
    firmName: 'Meridian Partners',
    industry: 'Manufacturing',
    tool: 'value_builder',
    engagementStatus: 'active',
    baselineValue: 5_400_000,
    momentum: 'steady',
    reappraisalMonth: 6,
    seed: 3071,
  },
  {
    engagementId: 'eng-ellerslie-dental',
    businessName: 'Ellerslie Dental Group',
    clientName: 'Dr Amara Osei',
    advisorName: 'Marcus Webb',
    firmName: 'Meridian Partners',
    industry: 'Healthcare',
    tool: 'sale_ready',
    engagementStatus: 'active',
    baselineValue: 3_200_000,
    momentum: 'high',
    reappraisalMonth: 10,
    seed: 4098,
  },
  {
    engagementId: 'eng-brightpath',
    businessName: 'Bright Path Early Learning',
    clientName: 'Tessa Nguyen',
    advisorName: 'Sarah Lindqvist',
    firmName: 'Southbank Advisory Group',
    industry: 'Education & Childcare',
    tool: 'value_builder',
    engagementStatus: 'on-hold',
    baselineValue: 2_750_000,
    momentum: 'flat',
    reappraisalMonth: -1,
    seed: 5125,
  },
  {
    engagementId: 'eng-tanner-co',
    businessName: 'Tanner & Co Accounting',
    clientName: 'Michael Tanner',
    advisorName: 'Sarah Lindqvist',
    firmName: 'Southbank Advisory Group',
    industry: 'Professional Services',
    tool: 'value_builder',
    engagementStatus: 'active',
    baselineValue: 1_850_000,
    momentum: 'steady',
    reappraisalMonth: -1,
    seed: 6152,
  },
  {
    engagementId: 'eng-redgum',
    businessName: 'Redgum Timber Supplies',
    clientName: 'Bill Arkwright',
    advisorName: 'Joel Ferreira',
    firmName: 'Kestrel Business Partners',
    industry: 'Wholesale & Distribution',
    tool: 'value_builder',
    engagementStatus: 'active',
    baselineValue: 4_100_000,
    momentum: 'declining',
    reappraisalMonth: 7,
    seed: 7179,
  },
  {
    engagementId: 'eng-pinnacle',
    businessName: 'Pinnacle Facilities Services',
    clientName: 'Grace Okonkwo',
    advisorName: 'Joel Ferreira',
    firmName: 'Kestrel Business Partners',
    industry: 'Facilities Management',
    tool: 'value_builder',
    engagementStatus: 'active',
    baselineValue: 2_950_000,
    momentum: 'high',
    reappraisalMonth: -1,
    seed: 8206,
  },
  {
    engagementId: 'eng-harvest-lane',
    businessName: 'Harvest Lane Foods',
    clientName: 'Antonio Vella',
    advisorName: 'Emma Thompson',
    firmName: 'Benchmark Business Advisory',
    industry: 'Food & Beverage',
    tool: 'sale_ready',
    engagementStatus: 'active',
    baselineValue: 6_800_000,
    momentum: 'steady',
    reappraisalMonth: 9,
    seed: 9233,
  },
  {
    engagementId: 'eng-vertex-it',
    businessName: 'Vertex IT Managed Services',
    clientName: 'Simone Bhatt',
    advisorName: 'Marcus Webb',
    firmName: 'Meridian Partners',
    industry: 'Technology',
    tool: 'value_builder',
    engagementStatus: 'active',
    baselineValue: 3_600_000,
    momentum: 'high',
    reappraisalMonth: -1,
    seed: 10_260,
  },
  {
    engagementId: 'eng-southerly-marine',
    businessName: 'Southerly Marine Services',
    clientName: 'Karl Jorgensen',
    advisorName: 'Sarah Lindqvist',
    firmName: 'Southbank Advisory Group',
    industry: 'Marine & Leisure',
    tool: 'value_builder',
    engagementStatus: 'draft',
    baselineValue: 1_250_000,
    momentum: 'flat',
    reappraisalMonth: -1,
    seed: 11_287,
  },
  {
    engagementId: 'eng-clearwater-civil',
    businessName: 'Clearwater Civil',
    clientName: 'Deb Mackenzie',
    advisorName: 'Joel Ferreira',
    firmName: 'Kestrel Business Partners',
    industry: 'Civil Construction',
    tool: 'value_builder',
    engagementStatus: 'completed',
    baselineValue: 7_400_000,
    momentum: 'steady',
    reappraisalMonth: 11,
    seed: 12_314,
  },
];

/** mulberry32 - small, fast, fully deterministic for a given seed. */
function makeRng(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = Math.imul(state ^ (state >>> 15), 1 | state);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const roundTo = (value: number, step: number) => Math.round(value / step) * step;
const oneDp = (value: number) => Math.round(value * 10) / 10;
const clampScore = (value: number) => Math.min(5, Math.max(0, value));

function buildBusiness(seed: BusinessSeed): BusinessValue {
  const rng = makeRng(seed.seed);
  const profile = MOMENTUM[seed.momentum];

  const history: ValuePoint[] = [];
  const eventsByDriver: Record<string, ValueEvent[]> = {};
  // A business should never appear to have done the same piece of work twice.
  const usedLabels = new Set<string>();
  let runningValue = seed.baselineValue;
  let lastRecalculatedAt = MONTHS[0];
  let lastRecalculatedBy: ValueSource = 'advisor';

  MONTHS.forEach((date, monthIndex) => {
    const events: ValueEvent[] = [];

    if (monthIndex === 0) {
      // The baseline appraisal itself: a real, advisor-written point worth zero movement.
      events.push({
        id: `${seed.engagementId}-baseline`,
        label: 'Baseline appraisal recorded',
        delta: 0,
        source: 'advisor',
        recordedAt: date,
      });
    } else {
      const recordsChange = rng() < profile.eventChance;
      // Busy months occasionally stack two changes.
      const changeCount = recordsChange ? (rng() < 0.25 ? 2 : 1) : 0;

      for (let n = 0; n < changeCount; n += 1) {
        // Re-draw until an unrecorded change turns up, then give up and move on
        // rather than loop forever once a business has worked through the list.
        let code = '';
        let label = '';
        for (let attempt = 0; attempt < 12; attempt += 1) {
          code = VALUE_DRIVER_CODES[Math.floor(rng() * VALUE_DRIVER_CODES.length)];
          const labels = EVENT_LABELS[code];
          label = labels[Math.floor(rng() * labels.length)];
          if (!usedLabels.has(label)) break;
        }
        if (usedLabels.has(label)) continue;
        usedLabels.add(label);

        const [minPct, maxPct] = profile.deltaRange;
        const delta = roundTo(seed.baselineValue * (minPct + rng() * (maxPct - minPct)), 1000);
        if (delta === 0) continue;

        const event: ValueEvent = {
          id: `${seed.engagementId}-${monthIndex}-${n}`,
          label,
          driverCode: code,
          delta,
          source: 'algorithm',
          recordedAt: date,
        };
        events.push(event);
        (eventsByDriver[code] ||= []).push(event);
      }

      if (monthIndex === seed.reappraisalMonth) {
        // An advisor re-appraisal is a material correction, not driver-attributed work.
        const delta = roundTo(seed.baselineValue * (rng() < 0.7 ? 0.035 : -0.02), 1000);
        events.push({
          id: `${seed.engagementId}-${monthIndex}-reappraisal`,
          label: 'Formal re-appraisal completed by advisor',
          delta,
          source: 'advisor',
          recordedAt: date,
        });
      }
    }

    runningValue += events.reduce((sum, event) => sum + event.delta, 0);
    history.push({ date, value: runningValue, events });

    if (events.some((event) => event.delta !== 0) || monthIndex === 0) {
      lastRecalculatedAt = date;
      lastRecalculatedBy = events[events.length - 1].source;
    }
  });

  const drivers: ValueDriver[] = VALUE_DRIVER_CODES.map((code) => {
    const driverEvents = eventsByDriver[code] ?? [];
    // Spread starting scores wide enough that weak drivers genuinely appear.
    const previousScore = oneDp(clampScore(0.9 + rng() * 3.4 + DRIVER_BASELINE_BIAS[code]));
    const lift = driverEvents.length * profile.scoreLiftPerEvent;
    const score = oneDp(clampScore(previousScore + lift));
    return {
      code,
      name: VALUE_BUILDER_MODULES[code],
      score,
      previousScore,
      delta: oneDp(score - previousScore),
      status: driverStatusFromScore(score),
      valueContribution: driverEvents.reduce((sum, event) => sum + event.delta, 0),
    };
  });

  const currentValue = history[history.length - 1].value;
  const upliftAmount = currentValue - seed.baselineValue;
  const mean = (values: number[]) => values.reduce((sum, v) => sum + v, 0) / values.length;

  return {
    engagementId: seed.engagementId,
    businessName: seed.businessName,
    clientName: seed.clientName,
    advisorName: seed.advisorName,
    firmName: seed.firmName,
    industry: seed.industry,
    tool: seed.tool,
    engagementStatus: seed.engagementStatus,
    baselineValue: seed.baselineValue,
    currentValue,
    upliftAmount,
    upliftPercent: oneDp((upliftAmount / seed.baselineValue) * 100),
    baselineDate: MONTHS[0],
    lastRecalculatedAt,
    lastRecalculatedBy,
    overallScore: oneDp(mean(drivers.map((d) => d.score))),
    previousOverallScore: oneDp(mean(drivers.map((d) => d.previousScore ?? 0))),
    drivers,
    history,
  };
}

function buildDriverAverages(businesses: BusinessValue[]): PortfolioDriverAverage[] {
  return VALUE_DRIVER_CODES.map((code) => {
    const perBusiness = businesses.map((b) => b.drivers.find((d) => d.code === code)!);
    const avgScore = oneDp(perBusiness.reduce((sum, d) => sum + d.score, 0) / perBusiness.length);
    return {
      code,
      name: VALUE_BUILDER_MODULES[code],
      avgScore,
      avgPreviousScore: oneDp(
        perBusiness.reduce((sum, d) => sum + (d.previousScore ?? 0), 0) / perBusiness.length,
      ),
      status: driverStatusFromScore(avgScore),
      businessesNeedingWork: perBusiness.filter((d) => d.status === 'needs_work').length,
    };
  });
}

let cached: PortfolioValue | null = null;

/** Builds the full fixture portfolio once and memoises it. */
export function buildPortfolio(): PortfolioValue {
  if (cached) return cached;

  const businesses = BUSINESS_SEEDS.map(buildBusiness);

  const history = MONTHS.map((date, monthIndex) => ({
    date,
    totalValue: businesses.reduce((sum, b) => sum + b.history[monthIndex].value, 0),
  }));

  const totalCurrentValue = businesses.reduce((sum, b) => sum + b.currentValue, 0);
  const totalBaselineValue = businesses.reduce((sum, b) => sum + b.baselineValue, 0);

  cached = {
    totalCurrentValue,
    totalBaselineValue,
    totalUplift: totalCurrentValue - totalBaselineValue,
    avgUpliftPercent: oneDp(
      businesses.reduce((sum, b) => sum + b.upliftPercent, 0) / businesses.length,
    ),
    businessCount: businesses.length,
    history,
    driverAverages: buildDriverAverages(businesses),
    businesses,
  };

  return cached;
}
