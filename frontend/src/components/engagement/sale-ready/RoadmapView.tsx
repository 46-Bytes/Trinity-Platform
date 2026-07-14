import { useMemo } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { Button } from '@/components/ui/button';
import { ChevronUp, ChevronDown, Wand2, Info, CheckCircle2, Clock, Circle, ArrowRight } from 'lucide-react';
import { setModuleOrder, applyRecommendedOrder, type SaleReadyStage } from '@/store/slices/saleReadyReducer';
import { StatusPill, stageIcon, stageTaskProgress, ProgressBar } from './saleReadyUi';

interface RoadmapViewProps {
  engagementId: string;
  canEdit?: boolean;
  onOpenStage?: (stageCode: string) => void;
}

export function RoadmapView({ engagementId, canEdit = false, onOpenStage }: RoadmapViewProps) {
  const dispatch = useAppDispatch();
  const stages = useAppSelector((s) => s.saleReady.stages);
  const isReordering = useAppSelector((s) => s.saleReady.isReordering);
  const tasks = useAppSelector((s) => s.task.tasks);

  // Backend already returns modules in effective priority order.
  const modules = useMemo(() => stages.filter((s) => s.stage_type === 'module'), [stages]);

  const counts = useMemo(() => ({
    complete: modules.filter((m) => m.status === 'complete').length,
    inProgress: modules.filter((m) => m.status === 'in_progress').length,
    notStarted: modules.filter((m) => m.status === 'not_started').length,
  }), [modules]);

  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= modules.length) return;
    const order = modules.map((m) => m.stage_code);
    [order[index], order[target]] = [order[target], order[index]];
    dispatch(setModuleOrder({ engagementId, moduleOrder: order }));
  };

  const tiles = [
    { label: 'Complete', value: counts.complete, icon: CheckCircle2, tone: 'text-success' },
    { label: 'In Progress', value: counts.inProgress, icon: Clock, tone: 'text-warning' },
    { label: 'Not Started', value: counts.notStarted, icon: Circle, tone: 'text-muted-foreground' },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h3 className="font-heading text-xl font-bold tracking-tight">Module Roadmap</h3>
          <p className="text-sm text-muted-foreground">Priority order set at Prioritisation; adjust any time.</p>
        </div>
        {canEdit && (
          <Button variant="outline" size="sm" disabled={isReordering} onClick={() => dispatch(applyRecommendedOrder(engagementId))}>
            <Wand2 className="h-4 w-4 mr-1.5" /> Apply recommended order
          </Button>
        )}
      </div>

      {/* Summary tiles */}
      <div className="grid grid-cols-3 gap-3">
        {tiles.map((t) => {
          const Icon = t.icon;
          return (
            <div key={t.label} className="stat-card flex items-center justify-between !p-4">
              <div>
                <div className={`font-heading text-2xl font-bold ${t.tone}`}>{t.value}</div>
                <div className="text-xs text-muted-foreground">{t.label}</div>
              </div>
              <div className="p-2.5 rounded-xl bg-muted/50">
                <Icon className={`h-5 w-5 ${t.tone}`} />
              </div>
            </div>
          );
        })}
      </div>

      {canEdit && (
        <div className="flex items-center gap-2 rounded-lg bg-primary/5 px-3.5 py-2 text-sm text-muted-foreground">
          <Info className="h-4 w-4 text-primary flex-shrink-0" />
          Order is saved and stays put on reload. Use the arrows to reorder, or apply the AI-recommended order.
        </div>
      )}

      <div className="space-y-2.5">
        {modules.map((m: SaleReadyStage, index) => {
          const Icon = stageIcon(m.stage_code);
          const progress = stageTaskProgress(tasks, engagementId, m.stage_code);
          return (
            <div key={m.stage_code} className="card-trinity overflow-hidden">
              <div className="flex items-center gap-4 p-4">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary flex-shrink-0">
                  {index + 1}
                </div>
                <button className="flex-1 min-w-0 text-left" onClick={() => onOpenStage?.(m.stage_code)}>
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <span className="font-heading font-semibold truncate">{m.title}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-1.5">
                    <ProgressBar pct={progress.pct} className="w-32" />
                    <span className="text-xs text-muted-foreground">
                      {progress.total > 0 ? `${progress.done}/${progress.total} tasks` : 'No tasks'}
                    </span>
                  </div>
                </button>
                <StatusPill status={m.status} />
                {canEdit ? (
                  <div className="flex flex-col gap-0.5">
                    <Button size="icon" variant="ghost" className="h-6 w-6" disabled={isReordering || index === 0} onClick={() => move(index, -1)} aria-label="Move up">
                      <ChevronUp className="h-4 w-4" />
                    </Button>
                    <Button size="icon" variant="ghost" className="h-6 w-6" disabled={isReordering || index === modules.length - 1} onClick={() => move(index, 1)} aria-label="Move down">
                      <ChevronDown className="h-4 w-4" />
                    </Button>
                  </div>
                ) : (
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                )}
              </div>
            </div>
          );
        })}
        {modules.length === 0 && <p className="text-sm text-muted-foreground text-center py-8">No modules yet.</p>}
      </div>
    </div>
  );
}
