import { ModuleRoadmapList } from './ModuleRoadmapList';
import { SaleReadyProgressCard } from './SaleReadyProgressCard';
import { StageCard } from './StageCard';
import type { SaleReadyRoadmap } from './types';

interface RoadmapViewProps {
  roadmap: SaleReadyRoadmap;
  /**
   * Owner mode, per the brief: the roadmap is visible but read-only, with no
   * clicking into stages. Everything else an owner may do is still open (C6).
   */
  readOnly?: boolean;
  canReorder?: boolean;
  isReordering?: boolean;
  onReorder?: (order: string[]) => void;
  onResetOrder?: () => void;
  onOpenStage?: (stageCode: string) => void;
}

/**
 * The Sale Ready roadmap: scope note, program progress, the four phases, the
 * eight modules in effective order, and the three closing phases.
 */
export function RoadmapView({
  roadmap,
  readOnly = false,
  canReorder = false,
  isReordering = false,
  onReorder,
  onResetOrder,
  onOpenStage,
}: RoadmapViewProps) {
  const open = readOnly ? undefined : onOpenStage;
  const reorderable = canReorder && !readOnly;

  const { closeout, sale_planner_issues: issues } = roadmap;
  const closedOn = closeout.closed_at
    ? new Date(closeout.closed_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })
    : '';

  return (
    <div className="space-y-5">
      {closeout.is_closed && (
        <div className="card-trinity flex flex-wrap items-center justify-between gap-3 border-success/30 bg-success/5 p-4 sm:px-6">
          <div>
            <p className="font-semibold">Program closed</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Closed {closedOn}.{' '}
              {closeout.referred_to_benchmark
                ? 'Referred to Benchmark Business Sales.'
                : 'Not referred to Benchmark Business Sales.'}
            </p>
          </div>
          <span className="status-badge bg-success/10 text-success">Closed</span>
        </div>
      )}

      <div className="rounded-xl border border-border bg-muted/40 px-4 py-3.5 text-sm leading-relaxed text-muted-foreground">
        <span className="font-semibold text-foreground">Sale Ready prepares the business for sale.</span> It finds,
        verifies, documents and discloses what a buyer will ask for. Anything found that needs fixing is logged as a
        gap and the advisor decides: fix in Sale Ready, disclose as is, or refer to Value Builder.
      </div>

      <SaleReadyProgressCard
        progress={roadmap.progress}
        gaps={roadmap.gaps}
        leadAdvisorName={roadmap.lead_advisor_name}
      />

      <section className="card-trinity p-6">
        <h2 className="font-heading text-lg font-semibold">Before the modules</h2>
        <p className="mb-5 mt-1 text-sm text-muted-foreground">Always in this order. Each phase carries its own tasks.</p>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
          {roadmap.phases.map((stage) => (
            <StageCard key={stage.stage_code} stage={stage} onOpen={open} />
          ))}
        </div>
      </section>

      <ModuleRoadmapList
        modules={roadmap.modules}
        canReorder={reorderable}
        isReordering={isReordering}
        onReorder={onReorder}
        onReset={onResetOrder}
        onOpen={open}
      />

      <section className="card-trinity p-6">
        <h2 className="font-heading text-lg font-semibold">After the modules</h2>
        <p className="mb-5 mt-1 text-sm text-muted-foreground">
          Open at any time. Sale Planner and Transition are checklists rather than task modules.
        </p>
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
          {roadmap.post_phases.map((stage) => (
            <StageCard
              key={stage.stage_code}
              stage={stage}
              onOpen={open}
              extraMeta={
                stage.ui_variant === 'sale_planner' && issues.total > 0
                  ? `${issues.addressed} of ${issues.total} issues`
                  : undefined
              }
            />
          ))}
        </div>
      </section>
    </div>
  );
}
