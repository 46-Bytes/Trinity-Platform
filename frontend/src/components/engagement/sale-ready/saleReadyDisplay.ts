/**
 * Display helpers for the Sale Ready roadmap.
 *
 * Status chips reuse the Program Guide's STATUS_CONFIG: the three statuses are
 * the same words with the same meaning, and one mapping cannot disagree with itself.
 */
import type { RoadmapStage } from './types';

export { STATUS_CONFIG } from '../program-guide/moduleDisplay';

/** "12 Sep" from an ISO date; null when there is no date. */
export function formatShortDate(value: string | null | undefined): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' });
}

/** Whole-number percentage, 0 when there is nothing to count. */
export function percentOf(done: number, total: number): number {
  return total > 0 ? Math.round((done / total) * 100) : 0;
}

/** The small meta line under a phase card: tasks, DD items, due date. */
export function stageMetaLine(stage: RoadmapStage): string {
  const parts: string[] = [];
  if (stage.must_do_total > 0) parts.push(`${stage.must_do_resolved} of ${stage.must_do_total} tasks`);
  if (stage.dd_total > 0) parts.push(`${stage.dd_yes} of ${stage.dd_total} DD items`);
  const due = formatShortDate(stage.due_date);
  if (due && stage.status !== 'completed') parts.push(`due ${due}`);
  return parts.join(' · ');
}

/**
 * Move `code` to sit where `target` is, keeping pinned codes at the end.
 * Returns null when the move is not allowed (pinned row, or no change).
 */
export function reorderModules(
  modules: RoadmapStage[],
  code: string,
  target: string
): string[] | null {
  if (code === target) return null;
  const pinned = modules.filter((m) => m.is_pinned_last).map((m) => m.stage_code);
  if (pinned.includes(code) || pinned.includes(target)) return null;

  const movable = modules.filter((m) => !m.is_pinned_last).map((m) => m.stage_code);
  const from = movable.indexOf(code);
  const to = movable.indexOf(target);
  if (from === -1 || to === -1) return null;

  const next = [...movable];
  next.splice(from, 1);
  next.splice(to, 0, code);
  return [...next, ...pinned];
}
