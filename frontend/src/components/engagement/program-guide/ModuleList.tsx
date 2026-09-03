import { ChevronRight } from 'lucide-react';

import { cn } from '@/lib/utils';
import type { DeliverableView, ModuleStatus } from '@/store/slices/deliverablesReducer';
import type { ProgramGuideInsights, ProgramGuideModule } from '@/store/slices/programGuideReducer';
import { ModuleReorderControls } from './ModuleReorderControls';
import { RAG_CLASS, STATUS_CONFIG, formatScore, statusOf } from './moduleDisplay';

interface ModuleListProps {
  modules: ProgramGuideModule[];
  deliverables: DeliverableView | null;
  insights: ProgramGuideInsights | null;
  canReorder?: boolean;
  isReordering?: boolean;
  onSelect: (moduleCode: string) => void;
  onMove?: (moduleCode: string, direction: -1 | 1) => void;
}

/**
 * The module list: one row per module, in the engagement's effective order.
 *
 * The order comes from the server already sorted by effective rank, so nothing
 * is sorted here. The rank badge shows `effective_rank`; a row the order does
 * not mention shows a dash rather than inventing a position for it.
 */
export function ModuleList({
  modules,
  deliverables,
  insights,
  canReorder = false,
  isReordering = false,
  onSelect,
  onMove,
}: ModuleListProps) {
  const statusByModule = new Map<string, ModuleStatus>(
    (deliverables?.modules ?? []).map((m) => [m.module_code, m.status])
  );
  const deliverablesByModule = new Map(
    (deliverables?.modules ?? []).map((m) => [m.module_code, m.deliverables])
  );
  const insightByModule = new Map((insights?.modules ?? []).map((m) => [m.module_code, m]));

  // Only the ranked modules can move, so first/last must be judged against
  // those rather than against the full list - an unranked row sitting at index
  // 0 would otherwise permanently disable "move up" on the real first module.
  const rankable = modules.filter((m) => m.effective_rank != null);

  return (
    <div className="card-trinity p-6">
      <div className="mb-5">
        <h2 className="font-heading font-semibold text-lg">Modules</h2>
        <p className="text-sm text-muted-foreground mt-1">
          In recommended advisory order. Rank is the sequence of work, not a ranking of scores.
          {canReorder ? ' Advisors can reorder as required.' : ''}
        </p>
      </div>

      <div className="space-y-2.5">
        {modules.map((module) => {
          const status = statusOf(statusByModule.get(module.module_code));
          const statusConfig = STATUS_CONFIG[status];
          const items = deliverablesByModule.get(module.module_code) ?? [];
          const required = items.filter((d) => d.is_mandatory && d.is_in_scope);
          const requiredDone = required.filter((d) => d.is_complete).length;
          const insight = insightByModule.get(module.module_code);
          const rankIndex = rankable.findIndex((m) => m.module_code === module.module_code);

          return (
            <div
              key={module.module_code}
              className="group flex items-center gap-4 rounded-xl border border-border p-4 transition-all hover:border-accent/50 hover:shadow-trinity-md"
            >
              <button
                type="button"
                onClick={() => onSelect(module.module_code)}
                className="flex flex-1 items-center gap-4 text-left min-w-0"
                aria-label={`Open ${module.title}`}
              >
                <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg bg-muted text-xs font-bold text-muted-foreground">
                  {module.effective_rank ?? '—'}
                </span>

                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                      {module.module_code}
                    </span>
                    <span className="font-semibold text-foreground transition-colors group-hover:text-accent">
                      {module.title}
                    </span>
                  </span>
                  {/*
                    `deliverables === null` is "not loaded yet", not "none" -
                    the two fetches run in parallel and the guide usually wins.
                    Saying "No deliverables yet" in that gap would be a claim
                    about data that has not arrived.
                  */}
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {deliverables === null
                      ? ' '
                      : required.length > 0
                        ? `${requiredDone} of ${required.length} required deliverables`
                        : items.length > 0
                          ? `${items.filter((d) => d.is_complete).length} of ${items.length} deliverables`
                          : 'No deliverables yet'}
                  </span>
                </span>

                <span className="hidden flex-shrink-0 items-center gap-2 md:flex">
                  {insight?.rag && (
                    <span
                      className={cn('status-badge whitespace-nowrap', RAG_CLASS[insight.rag] ?? 'bg-muted text-muted-foreground')}
                    >
                      <span className="h-1.5 w-1.5 rounded-full bg-current" />
                      {insight.severity ? `${insight.rag} / ${insight.severity}` : insight.rag}
                    </span>
                  )}
                  <span className={cn('status-badge whitespace-nowrap', statusConfig.badgeClass)}>
                    <statusConfig.icon className="h-3 w-3" />
                    {statusConfig.label}
                  </span>
                </span>

                <span className="w-14 flex-shrink-0 text-right font-bold">
                  {formatScore(insight?.score)}
                  <span className="text-xs font-medium text-muted-foreground"> /5</span>
                </span>

                <ChevronRight className="h-5 w-5 flex-shrink-0 text-muted-foreground transition-all group-hover:translate-x-0.5 group-hover:text-accent" />
              </button>

              {canReorder && rankIndex !== -1 && (
                <ModuleReorderControls
                  disabled={isReordering}
                  canMoveUp={rankIndex > 0}
                  canMoveDown={rankIndex < rankable.length - 1}
                  onMoveUp={() => onMove?.(module.module_code, -1)}
                  onMoveDown={() => onMove?.(module.module_code, 1)}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
