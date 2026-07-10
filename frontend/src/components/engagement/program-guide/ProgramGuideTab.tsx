import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2, RotateCcw, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchProgramGuide, reorderModules, resetModuleOrder, fetchValueMovement } from '@/store/slices/programGuideReducer';
import type { DiagnosticSummary } from '@/hooks/useToolLaunchers';
import { ProgramGuideStepper } from './ProgramGuideStepper';
import { ModuleCard } from './ModuleCard';
import { ModuleReorderControls } from './ModuleReorderControls';
import { RetakeDiagnosticCard } from './RetakeDiagnosticCard';

interface ProgramGuideTabProps {
  engagementId: string;
  diagnostics: DiagnosticSummary[];
  currentUserId?: string | null;
  isAdmin?: boolean;
  canReorder?: boolean;
  onNavigateToDiagnostic: () => void;
}

const ORDER_SOURCE_LABEL: Record<string, string> = {
  bba: 'Order based on your Recommendations Report',
  custom: 'Custom order set by your advisor',
  default: 'Default order — run the Recommendations Report Builder for a tailored order',
  unsupported: '',
};

function ProgramGuideSkeleton() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <Skeleton className="h-8 w-8 rounded-full" />
          <Skeleton className="h-8 w-8 rounded-full" />
          <Skeleton className="h-7 w-40 ml-1" />
        </div>
        <Skeleton className="h-6 w-28 rounded-full" />
      </div>
      <div className="flex items-center justify-between gap-1">
        {Array.from({ length: 13 }).map((_, i) => (
          <Skeleton key={i} className="h-8 w-8 rounded-full flex-shrink-0" />
        ))}
      </div>
      <div className="card-trinity p-6 space-y-5">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-2/3" />
        <div className="space-y-2 pt-2">
          <Skeleton className="h-9 w-full rounded-md" />
          <Skeleton className="h-9 w-full rounded-md" />
        </div>
      </div>
    </div>
  );
}

export function ProgramGuideTab({
  engagementId,
  diagnostics,
  currentUserId,
  isAdmin = false,
  canReorder = false,
  onNavigateToDiagnostic,
}: ProgramGuideTabProps) {
  const dispatch = useAppDispatch();
  const { view, valueMovement, isLoading, isReordering, error } = useAppSelector((state) => state.programGuide);
  const [activeModuleCode, setActiveModuleCode] = useState<string | null>(null);

  useEffect(() => {
    if (!engagementId) return;
    dispatch(fetchProgramGuide(engagementId));
    dispatch(fetchValueMovement(engagementId));
  }, [engagementId, dispatch]);

  // Default to the first module once the guide loads; keep the current
  // selection stable across refetches (e.g. after a reorder) as long as it
  // still exists in the returned list.
  useEffect(() => {
    if (!view) return;
    setActiveModuleCode((prev) => {
      if (prev && view.modules.some((m) => m.module_code === prev)) return prev;
      return view.modules[0]?.module_code ?? null;
    });
  }, [view]);

  if (isLoading && !view) {
    return <ProgramGuideSkeleton />;
  }

  if (error && !view) {
    return <div className="py-8 text-center text-sm text-destructive">{error}</div>;
  }

  if (!view || !activeModuleCode) return null;

  const activeIndex = view.modules.findIndex((m) => m.module_code === activeModuleCode);
  const activeModule = view.modules[activeIndex];
  if (!activeModule) return null;

  const nextModule = view.modules[activeIndex + 1];
  const workingModules = view.modules.filter((m) => !m.is_gateway && !m.is_capstone);
  const workingPosition = workingModules.findIndex((m) => m.module_code === activeModuleCode);

  const goTo = (index: number) => {
    const target = view.modules[index];
    if (target) setActiveModuleCode(target.module_code);
  };

  const moveActiveModule = (direction: -1 | 1) => {
    const currentOrder = workingModules.map((m) => m.module_code);
    const index = currentOrder.indexOf(activeModuleCode);
    const targetIndex = index + direction;
    if (index === -1 || targetIndex < 0 || targetIndex >= currentOrder.length) return;

    const newOrder = [...currentOrder];
    [newOrder[index], newOrder[targetIndex]] = [newOrder[targetIndex], newOrder[index]];
    dispatch(reorderModules({ engagementId, moduleOrder: newOrder }));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 rounded-full text-muted-foreground hover:text-foreground"
            disabled={activeIndex <= 0}
            onClick={() => goTo(activeIndex - 1)}
            aria-label="Previous module"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 rounded-full text-muted-foreground hover:text-foreground"
            disabled={activeIndex >= view.modules.length - 1}
            onClick={() => goTo(activeIndex + 1)}
            aria-label="Next module"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
          <h2 className="font-heading text-3xl font-bold tracking-tight ml-1">{activeModule.title}</h2>
        </div>

        <div className="flex items-center gap-3">
          {workingPosition !== -1 && (
            <Badge variant="secondary" className="rounded-full">
              Module {workingPosition + 1} of {workingModules.length}
            </Badge>
          )}
          {canReorder && workingPosition !== -1 && (
            <ModuleReorderControls
              disabled={isReordering}
              canMoveUp={workingPosition > 0}
              canMoveDown={workingPosition < workingModules.length - 1}
              onMoveUp={() => moveActiveModule(-1)}
              onMoveDown={() => moveActiveModule(1)}
            />
          )}
        </div>
      </div>

      <div className="py-3">
        <ProgramGuideStepper modules={view.modules} activeModuleCode={activeModuleCode} onSelect={setActiveModuleCode} />
      </div>

      {ORDER_SOURCE_LABEL[view.order_source] && (
        <div className="flex items-center justify-between gap-3 flex-wrap rounded-lg bg-primary/5 px-3.5 py-2">
          <span className="flex items-center gap-2 text-sm text-muted-foreground">
            <Info className="h-4 w-4 text-primary flex-shrink-0" />
            {ORDER_SOURCE_LABEL[view.order_source]}
          </span>
          {view.order_source === 'custom' && canReorder && (
            <Button
              variant="ghost"
              size="sm"
              disabled={isReordering}
              onClick={() => dispatch(resetModuleOrder(engagementId))}
            >
              <RotateCcw className="h-3.5 w-3.5 mr-1.5" />
              Reset to recommended order
            </Button>
          )}
        </div>
      )}

      <div key={activeModuleCode} className="animate-in fade-in slide-in-from-right-2 duration-200">
        {activeModule.is_capstone ? (
          <RetakeDiagnosticCard
            module={activeModule}
            engagementId={engagementId}
            currentUserId={currentUserId}
            valueMovement={valueMovement}
            onNavigateToDiagnostic={onNavigateToDiagnostic}
          />
        ) : (
          <ModuleCard
            module={activeModule}
            nextModule={nextModule}
            engagementId={engagementId}
            diagnostics={diagnostics}
            currentUserId={currentUserId}
            isAdmin={isAdmin}
            onNavigateToDiagnostic={onNavigateToDiagnostic}
            onGoToNext={() => goTo(activeIndex + 1)}
          />
        )}
      </div>
    </div>
  );
}
