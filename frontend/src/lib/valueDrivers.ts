/**
 * Value driver definitions for the Value / General Dashboard.
 *
 * Mirrors the Value Builder module set and RAG thresholds defined in
 * backend/app/services/scoring_service.py so the dashboard speaks the same
 * language as the diagnostic scoring engine. Keep the two in sync.
 */

export type DriverStatus = 'strong' | 'improving' | 'needs_work';

/** V1-V11, mirrored from ScoringService.VALUE_BUILDER_MODULES. */
export const VALUE_BUILDER_MODULES: Record<string, string> = {
  V1: 'Financial Management',
  V2: 'Strategy & Planning',
  V3: 'Leadership & Communications',
  V4: 'People',
  V5: 'Systems & Processes',
  V6: 'Technology',
  V7: 'Sales & Marketing',
  V8: 'Brand, IP & Competitive Advantage',
  V9: 'Owner Independence',
  V10: 'Value & Growth',
  V11: 'Risk, Legal, Compliance & Property',
};

/** Module codes in canonical V1..V11 order. */
export const VALUE_DRIVER_CODES = Object.keys(VALUE_BUILDER_MODULES);

/** Diagnostic scores run 0-5. */
export const MAX_DRIVER_SCORE = 5;

/** RAG thresholds, mirrored from ScoringService. */
export const RAG_RED_THRESHOLD = 2.0;
export const RAG_AMBER_THRESHOLD = 4.0;

/**
 * Maps a 0-5 diagnostic score onto the dashboard's three driver states.
 * @param score - The module score, 0-5
 * @returns 'needs_work' below 2.0, 'improving' below 4.0, otherwise 'strong'
 */
export function driverStatusFromScore(score: number): DriverStatus {
  if (score < RAG_RED_THRESHOLD) return 'needs_work';
  if (score < RAG_AMBER_THRESHOLD) return 'improving';
  return 'strong';
}

export const DRIVER_STATUS_LABEL: Record<DriverStatus, string> = {
  strong: 'Strong',
  improving: 'Improving',
  needs_work: 'Needs work',
};

/**
 * Existing Trinity status-badge classes (see index.css @layer components).
 * Status colour is never the only channel - every pill also carries an icon
 * and a text label, because Trinity's success green and destructive red are
 * only ~5.6 apart under deuteranopia.
 */
export const DRIVER_STATUS_CLASS: Record<DriverStatus, string> = {
  strong: 'status-success',
  improving: 'status-warning',
  needs_work: 'status-error',
};
