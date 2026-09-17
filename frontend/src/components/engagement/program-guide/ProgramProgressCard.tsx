import { cn } from '@/lib/utils';
import type { DeliverableView, ModuleStatus } from '@/store/slices/deliverablesReducer';
import type { ProgramGuideModule } from '@/store/slices/programGuideReducer';
import { statusOf } from './moduleDisplay';

interface ProgramProgressCardProps {
  modules: ProgramGuideModule[];
  deliverables: DeliverableView | null;
}

/**
 * Program-wide progress: how the modules are distributed across the three
 * statuses, and how many deliverables are done.
 *
 * Both figures count only IN-SCOPE deliverables. A scoped-out deliverable is
 * excluded from completion by the same rule on the backend, so counting it in
 * the denominator would show a program that can never reach 100% - the advisor
 * having deliberately removed work would look like work outstanding.
 */
export function ProgramProgressCard({ modules, deliverables }: ProgramProgressCardProps) {
  const statusByModule = new Map<string, ModuleStatus>(
    (deliverables?.modules ?? []).map((m) => [m.module_code, m.status])
  );

  const counts: Record<ModuleStatus, number> = { not_started: 0, in_progress: 0, completed: 0 };
  modules.forEach((module) => {
    counts[statusOf(statusByModule.get(module.module_code))] += 1;
  });

  const inScope = (deliverables?.modules ?? []).flatMap((m) =>
    m.deliverables.filter((d) => d.is_in_scope)
  );
  const completeCount = inScope.filter((d) => d.is_complete).length;
  const percent = inScope.length ? Math.round((completeCount / inScope.length) * 100) : 0;

  const stats: Array<{ label: string; value: string }> = [
    { label: 'Modules complete', value: String(counts.completed) },
    { label: 'In progress', value: String(counts.in_progress) },
    { label: 'Not started', value: String(counts.not_started) },
    { label: 'Deliverables complete', value: `${completeCount} / ${inScope.length}` },
  ];

  return (
    <div className="card-trinity p-6">
      <div className="flex items-center justify-between gap-4 mb-5">
        <h2 className="font-heading font-semibold text-lg">Program progress</h2>
        <span className="text-sm text-muted-foreground">{percent}% of deliverables complete</span>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mb-5">
        {stats.map((stat) => (
          <div key={stat.label}>
            <p className="text-3xl font-heading font-bold tracking-tight text-foreground">{stat.value}</p>
            <p className="text-sm text-muted-foreground mt-0.5">{stat.label}</p>
          </div>
        ))}
      </div>

      <div
        className="progress-trinity"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Deliverables complete"
      >
        <div className={cn('progress-trinity-bar')} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
