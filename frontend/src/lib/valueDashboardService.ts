/**
 * Value / General Dashboard data access.
 *
 * IMPORTANT: value figures are produced by the value-uplift algorithm or written
 * by the assigned advisor after a re-appraisal. They are never editable from the
 * dashboard UI - this module is read-only by design and exposes no write path.
 *
 * The uplift algorithm and its endpoints do not exist yet, so every function here
 * resolves from typed fixtures in ./valueDashboardMockData. The signatures are
 * already shaped like the real API (async, may reject) so components exercise
 * loading/error/empty states today and the swap is confined to this file.
 */

import type { DriverStatus } from './valueDrivers';
import { buildPortfolio } from './valueDashboardMockData';

export type { DriverStatus };

/** Who last wrote a value figure. Never the business owner. */
export type ValueSource = 'algorithm' | 'advisor';

export interface ValueDriver {
  /** Value Builder module code, e.g. 'V1'. */
  code: string;
  /** Module name, e.g. 'Financial Management'. */
  name: string;
  /** Current diagnostic score, 0-5. */
  score: number;
  previousScore: number | null;
  /** score - previousScore, or null when there is no prior diagnostic. */
  delta: number | null;
  status: DriverStatus;
  /** AUD of uplift attributed to this driver by the algorithm. */
  valueContribution: number;
}

/** A single recorded change that moved the value number. */
export interface ValueEvent {
  id: string;
  /** Human-readable description, e.g. 'Removed owner from daily operations'. */
  label: string;
  /** The value driver this change is attributed to, if any. */
  driverCode?: string;
  /** Signed AUD movement produced by this change. */
  delta: number;
  source: ValueSource;
  /** ISO date. */
  recordedAt: string;
}

/** One point on the value-over-time series, plus the changes that produced it. */
export interface ValuePoint {
  /** ISO date. */
  date: string;
  /** Business value in AUD at this point. */
  value: number;
  events: ValueEvent[];
}

export type EngagementStatus = 'draft' | 'active' | 'on-hold' | 'completed' | 'cancelled';

export interface BusinessValue {
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
  /** Latest calculated value, in AUD. */
  currentValue: number;
  /** currentValue - baselineValue. */
  upliftAmount: number;
  /** Uplift as a percentage of baseline, one decimal place. */
  upliftPercent: number;

  /** ISO date of the baseline appraisal. */
  baselineDate: string;
  /** ISO date the current value was last written. */
  lastRecalculatedAt: string;
  lastRecalculatedBy: ValueSource;

  /** Mean driver score, 0-5. */
  overallScore: number;
  previousOverallScore: number | null;

  drivers: ValueDriver[];
  /** Oldest to newest. */
  history: ValuePoint[];
}

export interface PortfolioDriverAverage {
  code: string;
  name: string;
  avgScore: number;
  avgPreviousScore: number;
  status: DriverStatus;
  /** How many businesses have this driver sitting in 'needs_work'. */
  businessesNeedingWork: number;
}

export interface PortfolioValue {
  totalCurrentValue: number;
  totalBaselineValue: number;
  totalUplift: number;
  /** Mean of per-business uplift percentages, one decimal place. */
  avgUpliftPercent: number;
  businessCount: number;
  /** Portfolio total value per month, oldest to newest. */
  history: Array<{ date: string; totalValue: number }>;
  driverAverages: PortfolioDriverAverage[];
  businesses: BusinessValue[];
}

/** Simulated network latency so loading states are real during development. */
const MOCK_LATENCY_MS = 350;

function settle<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), MOCK_LATENCY_MS));
}

/**
 * Value roll-up across every engagement. Superadmin scope.
 *
 * TODO(api): replace with
 *   fetch(`${API_BASE_URL}/api/value-dashboard/portfolio?months=${months}`, { headers: getAuthHeaders() })
 *
 * @param months - How much history to return. 0 returns the full series.
 */
export async function getPortfolioValue(months = 12): Promise<PortfolioValue> {
  const portfolio = buildPortfolio();
  const history =
    months > 0 ? portfolio.history.slice(Math.max(0, portfolio.history.length - (months + 1))) : portfolio.history;
  return settle({ ...portfolio, history });
}

/**
 * Value detail for a single engagement.
 *
 * TODO(api): replace with
 *   fetch(`${API_BASE_URL}/api/value-dashboard/engagements/${engagementId}`, { headers: getAuthHeaders() })
 */
export async function getBusinessValue(engagementId: string): Promise<BusinessValue> {
  const match = buildPortfolio().businesses.find((b) => b.engagementId === engagementId);
  if (!match) {
    return Promise.reject(new Error(`No value data found for engagement ${engagementId}`));
  }
  return settle(match);
}
