/**
 * Shared display vocabulary for the Program Guide.
 *
 * Status, RAG and input-source each appear in more than one place - a module row
 * and its detail header both show status, for instance - and a mapping that
 * lives in two components is a mapping that eventually disagrees with itself.
 * Every one of them is defined once, here.
 *
 * Class strings are written out in full rather than composed, because Tailwind
 * scans source text and cannot see a class name assembled at runtime.
 */
import {
  Circle,
  Clock,
  CheckCircle2,
  Database,
  Upload,
  CornerUpRight,
  type LucideIcon,
} from 'lucide-react';

import type { ModuleStatus } from '@/store/slices/deliverablesReducer';
import type { ModuleNote, ModuleTable } from '@/store/slices/programGuideReducer';

/** The eyebrow above every card section. */
export const SECTION_LABEL_CLASS =
  'flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary mb-2';

/** The smaller label used to mark where a block of content came from. */
export const SOURCE_LABEL_CLASS =
  'inline-flex items-center gap-1.5 rounded px-2 py-1 text-[10px] font-bold uppercase tracking-wider';

export const STATUS_CONFIG: Record<ModuleStatus, { label: string; icon: LucideIcon; badgeClass: string }> = {
  not_started: {
    label: 'Not started',
    icon: Circle,
    badgeClass: 'bg-muted text-muted-foreground',
  },
  in_progress: {
    label: 'In progress',
    icon: Clock,
    badgeClass: 'bg-info/10 text-info',
  },
  completed: {
    label: 'Complete',
    icon: CheckCircle2,
    badgeClass: 'bg-success/10 text-success',
  },
};

/**
 * A module with no deliverables at all is absent from the deliverables view
 * rather than present with an empty list, so callers resolve status through
 * this instead of indexing the response directly.
 */
export function statusOf(status: ModuleStatus | undefined): ModuleStatus {
  return status ?? 'not_started';
}

/** Backend RAG literals are capitalised: 'Red' | 'Amber' | 'Green'. */
export const RAG_CLASS: Record<string, string> = {
  Red: 'bg-destructive/10 text-destructive',
  Amber: 'bg-warning/10 text-warning',
  Green: 'bg-success/10 text-success',
};

/**
 * The three authored input sources, verbatim from the specification.
 *
 * Keyed by the exact string the backend stores - these are authored content,
 * not an enum, so a fixture typo should fall through to a neutral tag rather
 * than crash a card.
 */
export const INPUT_SOURCE_CONFIG: Record<string, { icon: LucideIcon; className: string }> = {
  'Held in Trinity': { icon: Database, className: 'bg-info/10 text-info' },
  'Advisor to upload': { icon: Upload, className: 'bg-warning/10 text-warning' },
  'From an earlier module': { icon: CornerUpRight, className: 'bg-muted text-muted-foreground' },
};

export const DEFAULT_INPUT_SOURCE = { icon: Database, className: 'bg-muted text-muted-foreground' };

export function inputSourceConfig(source: string) {
  return INPUT_SOURCE_CONFIG[source] ?? DEFAULT_INPUT_SOURCE;
}

/**
 * A tool whose `status` says it has not been built yet.
 *
 * Six of the eleven modules name a generator that does not exist. The card
 * shows those as pending rather than dropping them, which is what the guide
 * used to do - an unbuilt tool silently vanished from its own module.
 */
export function isToolPending(status?: string | null): boolean {
  return Boolean(status && status.toLowerCase().startsWith('to build'));
}

/**
 * Notes carrying no `section`, which belong to the module as a whole.
 *
 * `title` and `section` are independently optional, so this deliberately tests
 * only `section` - a titled note with no section is still module-level.
 */
export function moduleLevelNotes(notes?: ModuleNote[] | null): ModuleNote[] {
  return (notes ?? []).filter((note) => !note.section);
}

/** Notes attached to one named section of the card. */
export function notesForSection(notes: ModuleNote[] | null | undefined, section: string): ModuleNote[] {
  return (notes ?? []).filter((note) => note.section === section);
}

/** Reference matrices attached to one named section. */
export function tablesForSection(tables: ModuleTable[] | null | undefined, section: string): ModuleTable[] {
  return (tables ?? []).filter((table) => table.section === section);
}

/**
 * Tables with no section, which have no named home to render under.
 *
 * Returned separately so the detail view can still show them rather than
 * dropping authored content on the floor.
 */
export function unsectionedTables(tables?: ModuleTable[] | null): ModuleTable[] {
  return (tables ?? []).filter((table) => !table.section);
}

/**
 * Join an owner and a duration into one line, tolerating either being absent.
 * Returns null when there is nothing to show, so the caller can skip the row.
 */
export function ownerAndDuration(owner?: string | null, duration?: string | null): string | null {
  return [owner, duration].filter(Boolean).join(' · ') || null;
}

/** Scores are 0-5 with one decimal. Renders an em dash when nothing was measured. */
export function formatScore(score?: number | null): string {
  return typeof score === 'number' ? score.toFixed(1) : '—';
}
