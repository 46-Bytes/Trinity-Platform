import type { GapSummary, RoadmapProgress } from './types';

interface SaleReadyProgressCardProps {
  progress: RoadmapProgress;
  gaps: GapSummary;
  leadAdvisorName?: string | null;
}

/**
 * Program progress, as in the mockup: phases, modules, must-do tasks and DD
 * items, a gaps line when any DD item is marked No, and a bar over must-do tasks.
 */
export function SaleReadyProgressCard({ progress, gaps, leadAdvisorName }: SaleReadyProgressCardProps) {
  const stats = [
    { label: 'Phases complete', value: `${progress.phases_completed} / ${progress.phases_total}` },
    { label: 'Modules complete', value: `${progress.modules_completed} / ${progress.modules_total}` },
    { label: 'Must-do tasks done', value: `${progress.must_do_resolved} / ${progress.must_do_total}` },
    { label: 'DD items complete', value: `${progress.dd_yes} / ${progress.dd_total}` },
  ];

  return (
    <div className="card-trinity p-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-heading text-lg font-semibold">Program progress</h2>
        {leadAdvisorName && <p className="text-xs text-muted-foreground">Lead advisor {leadAdvisorName}</p>}
      </div>

      <div className="mb-5 grid grid-cols-2 gap-6 lg:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label}>
            <p className="font-heading text-2xl font-bold tracking-tight sm:text-3xl">{stat.value}</p>
            <p className="mt-0.5 text-sm text-muted-foreground">{stat.label}</p>
          </div>
        ))}
      </div>

      {gaps.total > 0 && (
        <p className="mb-3 text-xs text-muted-foreground">
          Gaps found: {gaps.total} · fix in Sale Ready {gaps.fix} · disclose {gaps.disclose} · referred to
          Value Builder {gaps.refer} · unhandled {gaps.unhandled}
        </p>
      )}

      <div
        className="progress-trinity"
        role="progressbar"
        aria-valuenow={progress.percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Must-do tasks done"
      >
        <div className="progress-trinity-bar" style={{ width: `${progress.percent}%` }} />
      </div>
    </div>
  );
}
