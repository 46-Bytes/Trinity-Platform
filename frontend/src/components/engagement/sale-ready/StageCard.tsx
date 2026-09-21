import { cn } from '@/lib/utils';
import { STATUS_CONFIG, stageMetaLine } from './saleReadyDisplay';
import type { RoadmapStage } from './types';

interface StageCardProps {
  stage: RoadmapStage;
  /** Omitted in read-only mode: the owner sees the roadmap but cannot open stages. */
  onOpen?: (stageCode: string) => void;
  /** Extra progress for stages with their own screen, e.g. Sale Planner issues. */
  extraMeta?: string;
}

/** A phase card from the mockup's "Before the modules" and "After the modules" rows. */
export function StageCard({ stage, onOpen, extraMeta }: StageCardProps) {
  const status = STATUS_CONFIG[stage.status];
  const meta = [stageMetaLine(stage), extraMeta].filter(Boolean).join(' · ');
  const body = (
    <>
      <p className="mb-1.5 text-[11px] font-bold tracking-wide text-muted-foreground">{stage.display_code}</p>
      <p className="mb-2.5 min-h-[2.25rem] text-sm font-semibold leading-snug">{stage.title}</p>
      <span className={cn('status-badge', status.badgeClass)}>
        <status.icon className="h-3 w-3" />
        {status.label}
      </span>
      {meta && <p className="mt-2 text-xs text-muted-foreground">{meta}</p>}
    </>
  );

  const className = cn(
    'rounded-xl border border-border p-4 text-left transition-all',
    stage.status === 'completed' && 'border-success/30 bg-success/5'
  );

  if (!onOpen) return <div className={className}>{body}</div>;

  return (
    <button
      type="button"
      onClick={() => onOpen(stage.stage_code)}
      className={cn(className, 'hover:border-accent/50 hover:shadow-trinity-md')}
      aria-label={`Open ${stage.title}`}
    >
      {body}
    </button>
  );
}
