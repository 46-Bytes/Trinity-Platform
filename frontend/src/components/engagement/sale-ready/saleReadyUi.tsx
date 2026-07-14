/**
 * Shared visual language for the Sale Ready program UI.
 *
 * Single source of truth for status pills, per-stage icons, and progress bars so
 * every view (roadmap, rail, stage detail, master DD) stays consistent and uses
 * the platform's semantic design tokens (.status-* / accent) rather than ad-hoc
 * colors.
 */
import {
  Circle,
  Clock,
  CheckCircle2,
  UserPlus,
  ClipboardCheck,
  Calculator,
  ListOrdered,
  CalendarClock,
  BarChart3,
  Scale,
  Cog,
  Users,
  ShoppingCart,
  Sparkles,
  Landmark,
  FolderCheck,
  ArrowLeftRight,
  Handshake,
  LayoutGrid,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { Task } from '@/store/slices/tasksReducer';
import type { SaleReadyStage, StageStatus } from '@/store/slices/saleReadyReducer';

export type { SaleReadyStage };

type Status = StageStatus;

export const STAGE_STATUS_META: Record<Status, {
  label: string;
  pillClass: string;
  dotClass: string;
  icon: LucideIcon;
}> = {
  not_started: {
    label: 'Not Started',
    pillClass: 'bg-muted text-muted-foreground',
    dotClass: 'bg-muted-foreground/40',
    icon: Circle,
  },
  in_progress: {
    label: 'In Progress',
    pillClass: 'bg-warning/10 text-warning',
    dotClass: 'bg-warning',
    icon: Clock,
  },
  complete: {
    label: 'Complete',
    pillClass: 'bg-success/10 text-success',
    dotClass: 'bg-success',
    icon: CheckCircle2,
  },
};

/** Status pill matching the platform `.status-badge` convention. */
export function StatusPill({ status, className }: { status: Status; className?: string }) {
  const meta = STAGE_STATUS_META[status] ?? STAGE_STATUS_META.not_started;
  const Icon = meta.icon;
  return (
    <span className={cn('status-badge', meta.pillClass, className)}>
      <Icon className="h-3.5 w-3.5" />
      {meta.label}
    </span>
  );
}

/** Small status dot (used in the stage rail). */
export function StatusDot({ status, className }: { status: Status; className?: string }) {
  const meta = STAGE_STATUS_META[status] ?? STAGE_STATUS_META.not_started;
  return <span className={cn('h-2 w-2 rounded-full flex-shrink-0', meta.dotClass, className)} />;
}

/** Per-stage lucide icon, keyed by stage_code, with a sensible default. */
export const STAGE_ICON: Record<string, LucideIcon> = {
  ONBOARD: UserPlus,
  DIAG: ClipboardCheck,
  APPRAISAL: Calculator,
  PRIORITISE: ListOrdered,
  PLANNING: CalendarClock,
  M_FIN: BarChart3,
  M_LEGAL: Scale,
  M_OWNER: Cog,
  M_PEOPLE: Users,
  M_CUSTOMER: ShoppingCart,
  M_BRAND: Sparkles,
  M_TAX: Landmark,
  M_DD: FolderCheck,
  TRANSITION: ArrowLeftRight,
  SALE_PLANNER: Handshake,
};

export function stageIcon(stageCode: string): LucideIcon {
  return STAGE_ICON[stageCode] ?? LayoutGrid;
}

/** Task-completion progress for a stage, derived from the shared task store. */
export function stageTaskProgress(tasks: Task[], engagementId: string, stageCode: string): {
  done: number;
  total: number;
  pct: number;
} {
  const relevant = tasks.filter((t) => t.engagementId === engagementId && t.moduleReference === stageCode);
  const total = relevant.length;
  const done = relevant.filter((t) => t.status === 'completed').length;
  const pct = total === 0 ? 0 : Math.round((done / total) * 100);
  return { done, total, pct };
}

/** Thin progress bar using the platform `.progress-trinity` utilities. */
export function ProgressBar({ pct, className }: { pct: number; className?: string }) {
  return (
    <div className={cn('progress-trinity', className)}>
      <div className="progress-trinity-bar" style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
    </div>
  );
}

/** Reusable eyebrow section label (uppercase, primary, leading icon). */
export function SectionLabel({ icon: Icon, children }: { icon: LucideIcon; children: React.ReactNode }) {
  return (
    <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary mb-2">
      <Icon className="h-3.5 w-3.5" />
      {children}
    </p>
  );
}

/** Consistent dashed-border empty state. */
export function EmptyState({ icon: Icon, children }: { icon?: LucideIcon; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground flex flex-col items-center gap-2">
      {Icon && <Icon className="h-5 w-5 opacity-60" />}
      <span>{children}</span>
    </div>
  );
}
