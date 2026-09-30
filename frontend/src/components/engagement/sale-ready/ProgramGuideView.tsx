import { useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import type { RoadmapStage, SaleReadyGuide, SaleReadyRoadmap } from './types';

interface ProgramGuideViewProps {
  roadmap: SaleReadyRoadmap;
  /** The engagement's frozen guide; null until it has loaded. */
  guide?: SaleReadyGuide | null;
  isLoading?: boolean;
  /** Why the guide could not be loaded, if it could not. */
  error?: string | null;
  /** Requests the guide again. */
  onRetry: () => void;
  /** Omitted in read-only mode. */
  onOpenStage?: (stageCode: string) => void;
}

type StepState = 'done' | 'now' | '';

/** How the Sale Ready program runs, shown against this engagement, then the program rules. */
export function ProgramGuideView({ roadmap, guide, isLoading = false, error = null, onRetry, onOpenStage }: ProgramGuideViewProps) {
  const workflow = guide?.program?.workflow ?? [];
  const rules = guide?.program?.rules ?? [];
  const stages: RoadmapStage[] = [...roadmap.phases, ...roadmap.modules, ...roadmap.post_phases];
  const byCode = new Map(stages.map((s) => [s.stage_code, s]));
  const unpinned = roadmap.modules.filter((m) => !m.is_pinned_last);

  const stateOf = (code: string): StepState => {
    if (code === 'modules') {
      if (unpinned.length && unpinned.every((m) => m.status === 'completed')) return 'done';
      return unpinned.some((m) => m.status !== 'not_started') ? 'now' : '';
    }
    const status = byCode.get(code)?.status;
    return status === 'completed' ? 'done' : status === 'in_progress' ? 'now' : '';
  };

  // Nothing loaded, nothing loading and no error means no request was made: make one,
  // so the tab can never sit on the skeleton with nothing in flight.
  const idle = !guide && !isLoading && !error;
  useEffect(() => {
    if (idle) onRetry();
  }, [idle, onRetry]);

  if (!guide && error) {
    return (
      <div role="alert" className="card-trinity p-6 text-center sm:p-10">
        <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-destructive" aria-hidden />
        <p className="mb-1 font-medium text-destructive">Could not load the program guide</p>
        <p className="mb-4 text-sm text-muted-foreground">{error}</p>
        <Button variant="outline" onClick={onRetry}>
          Retry
        </Button>
      </div>
    );
  }

  if (!guide) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-64 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <section className="card-trinity p-4 sm:p-6">
        <h2 className="font-heading text-lg font-semibold">How the Sale Ready program runs</h2>
        <p className="mb-4 mt-1 text-sm text-muted-foreground">
          The workflow from the program sheet, shown against this engagement.
        </p>
        <ol className="relative border-l-2 border-border pl-6">
          {workflow.map((step) => {
            const state = stateOf(step.stage);
            const openable = onOpenStage && step.stage !== 'modules' && byCode.has(step.stage);
            return (
              <li key={step.stage} className="relative py-2">
                <span
                  className={cn(
                    'absolute -left-[1.95rem] top-3 h-3 w-3 rounded-full border-2 border-border bg-background',
                    state === 'done' && 'border-success bg-success',
                    state === 'now' && 'border-info ring-4 ring-info/15'
                  )}
                  aria-hidden
                />
                {openable ? (
                  <button
                    type="button"
                    onClick={() => onOpenStage(step.stage)}
                    className={cn('text-left text-sm text-muted-foreground hover:underline', state === 'now' && 'font-semibold text-foreground')}
                  >
                    {step.label}
                  </button>
                ) : (
                  <p className={cn('text-sm text-muted-foreground', state === 'now' && 'font-semibold text-foreground')}>
                    {step.label}
                  </p>
                )}
                {step.stage === 'modules' && (
                  <p className="text-xs text-muted-foreground">{unpinned.map((m) => m.title).join(' · ')}</p>
                )}
              </li>
            );
          })}
        </ol>
      </section>

      <section className="card-trinity p-4 sm:p-6">
        <h2 className="mb-2 font-heading text-lg font-semibold">Program rules</h2>
        {rules.map((rule, i) => (
          <div key={rule.title} className="flex gap-3 border-b border-border/60 py-3 text-sm last:border-b-0">
            <span className="grid h-6 w-6 flex-shrink-0 place-items-center rounded-md bg-success/10 text-[11px] font-bold text-success">
              {i + 1}
            </span>
            <div>
              <p className="font-semibold">{rule.title}</p>
              <p className="leading-relaxed text-muted-foreground">{rule.body}</p>
            </div>
          </div>
        ))}
      </section>
    </div>
  );
}
