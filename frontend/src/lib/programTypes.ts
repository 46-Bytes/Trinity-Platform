/**
 * The advisory programs the Program Guide serves.
 *
 * Mirrors backend/app/services/program_registry.py. The backend is the
 * authority - it refuses an unsupported tool with a 400 either way - but the
 * tab has to decide whether to render before any request is made, so the list
 * is stated here too. Keep the two in step when a program is added.
 */
export const PROGRAM_GUIDE_TOOLS = ['value_builder', 'sale_ready'] as const;

export type ProgramGuideTool = (typeof PROGRAM_GUIDE_TOOLS)[number];

const PROGRAM_LABELS: Record<ProgramGuideTool, string> = {
  value_builder: 'Value Builder',
  sale_ready: 'Sale Ready',
};

/** True when this engagement.tool is a module-based advisory program. */
export function isProgramGuideTool(tool?: string | null): tool is ProgramGuideTool {
  return PROGRAM_GUIDE_TOOLS.includes(tool as ProgramGuideTool);
}

/**
 * Display name for a program, used as the tab label and in its copy.
 * Falls back to a neutral word so an unknown tool never renders "undefined".
 */
export function programLabel(tool?: string | null): string {
  return isProgramGuideTool(tool) ? PROGRAM_LABELS[tool] : 'Program';
}
