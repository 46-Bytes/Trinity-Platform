import { useState } from 'react';
import { ChevronRight, GripVertical, Lock, RotateCcw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ModuleReorderControls } from '../program-guide/ModuleReorderControls';
import { STATUS_CONFIG, formatShortDate, percentOf, reorderModules } from './saleReadyDisplay';
import type { RoadmapStage } from './types';

interface ModuleRoadmapListProps {
  /** In effective order, pinned module last. */
  modules: RoadmapStage[];
  canReorder: boolean;
  isReordering?: boolean;
  onReorder?: (order: string[]) => void;
  onReset?: () => void;
  /** Omitted in read-only mode. */
  onOpen?: (stageCode: string) => void;
}

function Bar({ label, done, total, className }: { label: string; done: number; total: number; className?: string }) {
  return (
    <div className="min-w-0">
      <p className="mb-1 text-[11px] text-muted-foreground">
        {label} {done}/{total}
      </p>
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div className={cn('h-full rounded-full bg-success', className)} style={{ width: `${percentOf(done, total)}%` }} />
      </div>
    </div>
  );
}

/**
 * The mockup's module list. Desktop drags rows; the arrow controls do the same
 * for touch and keyboard, since native drag and drop does not work on phones.
 * A pinned module (M8) shows a lock and cannot be moved or dropped onto.
 */
export function ModuleRoadmapList({
  modules,
  canReorder,
  isReordering = false,
  onReorder,
  onReset,
  onOpen,
}: ModuleRoadmapListProps) {
  const [dragging, setDragging] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const movable = modules.filter((m) => !m.is_pinned_last);

  const move = (code: string, target: string) => {
    const next = reorderModules(modules, code, target);
    if (next) onReorder?.(next);
  };

  const step = (code: string, direction: -1 | 1) => {
    const index = movable.findIndex((m) => m.stage_code === code);
    const target = movable[index + direction];
    if (target) move(code, target.stage_code);
  };

  return (
    <div className="card-trinity p-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-lg font-semibold">Modules</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Initial order proposed by the diagnostic.
            {canReorder ? ' Drag or use the arrows to reorder. Two or more can run at once.' : ''} Due Diligence
            Preparation is pinned last.
          </p>
        </div>
        {canReorder && onReset && (
          <Button variant="outline" size="sm" disabled={isReordering} onClick={onReset}>
            <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
            Reset to proposed order
          </Button>
        )}
      </div>

      <div className="space-y-2.5">
        {modules.map((module) => {
          const status = STATUS_CONFIG[module.status];
          const draggable = canReorder && !module.is_pinned_last && !isReordering;
          const index = movable.findIndex((m) => m.stage_code === module.stage_code);
          const due = formatShortDate(module.due_date);

          return (
            <div
              key={module.stage_code}
              draggable={draggable}
              onDragStart={(e) => {
                setDragging(module.stage_code);
                e.dataTransfer.effectAllowed = 'move';
              }}
              onDragEnd={() => {
                setDragging(null);
                setOver(null);
              }}
              onDragOver={(e) => {
                if (!dragging || module.is_pinned_last) return;
                e.preventDefault();
                setOver(module.stage_code);
              }}
              onDragLeave={() => setOver(null)}
              onDrop={(e) => {
                e.preventDefault();
                if (dragging) move(dragging, module.stage_code);
                setDragging(null);
                setOver(null);
              }}
              className={cn(
                'flex flex-col gap-3 rounded-xl border border-border p-4 transition-all md:flex-row md:items-center md:gap-4',
                dragging === module.stage_code && 'opacity-40',
                over === module.stage_code && 'border-success ring-2 ring-success/20'
              )}
            >
              <div className="flex min-w-0 flex-1 items-center gap-3">
                {canReorder && (
                  <span
                    className={cn('hidden text-muted-foreground/50 md:block', draggable && 'cursor-grab')}
                    title={module.is_pinned_last ? 'Pinned last' : 'Drag to reorder'}
                  >
                    {module.is_pinned_last ? <Lock className="h-4 w-4" /> : <GripVertical className="h-4 w-4" />}
                  </span>
                )}
                <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg bg-muted text-xs font-bold text-muted-foreground">
                  {module.effective_rank ?? '—'}
                </span>
                <div className="min-w-0">
                  {onOpen ? (
                    <button
                      type="button"
                      onClick={() => onOpen(module.stage_code)}
                      className="text-left font-semibold hover:underline"
                    >
                      {module.title}
                    </button>
                  ) : (
                    <p className="font-semibold">{module.title}</p>
                  )}
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {module.display_code} ·{' '}
                    {module.tasks_created
                      ? `${module.must_do_resolved} of ${module.must_do_total} must-do tasks`
                      : `${module.must_do_total} must-do tasks ready to create`}
                    {due ? ` · due ${due}` : ''}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 md:w-60 md:flex-shrink-0">
                <Bar label="Tasks" done={module.must_do_resolved} total={module.must_do_total} />
                <Bar label="DD" done={module.dd_yes} total={module.dd_total} className="bg-info" />
              </div>

              <div className="flex items-center justify-between gap-3 md:w-auto md:justify-end">
                <span className={cn('status-badge whitespace-nowrap', status.badgeClass)}>
                  <status.icon className="h-3 w-3" />
                  {status.label}
                </span>
                <div className="flex items-center gap-1">
                  {canReorder && !module.is_pinned_last && (
                    <ModuleReorderControls
                      disabled={isReordering}
                      canMoveUp={index > 0}
                      canMoveDown={index < movable.length - 1}
                      onMoveUp={() => step(module.stage_code, -1)}
                      onMoveDown={() => step(module.stage_code, 1)}
                    />
                  )}
                  {onOpen && (
                    <button
                      type="button"
                      onClick={() => onOpen(module.stage_code)}
                      aria-label={`Open ${module.title}`}
                      className="text-muted-foreground hover:text-accent"
                    >
                      <ChevronRight className="h-5 w-5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
