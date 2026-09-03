import { useEffect, useState } from 'react';
import { AlertTriangle, Info, RotateCcw } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  fetchModuleInsights,
  fetchProgramGuide,
  fetchValueMovement,
  reorderModules,
  resetModuleOrder,
} from '@/store/slices/programGuideReducer';
import { fetchDeliverables } from '@/store/slices/deliverablesReducer';
import type { DiagnosticSummary } from '@/hooks/useToolLaunchers';
import { ModuleDetail } from './ModuleDetail';
import { ModuleList } from './ModuleList';
import { ProgramProgressCard } from './ProgramProgressCard';
import { ValueMovementView } from './ValueMovementView';

interface ProgramGuideTabProps {
  engagementId: string;
  diagnostics: DiagnosticSummary[];
  currentUserId?: string | null;
  isAdmin?: boolean;
  canReorder?: boolean;
  onNavigateToDiagnostic: () => void;
}

const ORDER_SOURCE_LABEL: Record<string, string> = {
  diagnostic: 'Order based on this client’s diagnostic — weakest-scoring modules first',
  custom: 'Custom order, set by an advisor on this engagement',
  default: 'Default order — complete the diagnostic for a sequence tailored to this client',
  unsupported: '',
};

function ProgramGuideSkeleton() {
  return (
    <div className="space-y-4">
      <div className="card-trinity p-6">
        <Skeleton className="mb-5 h-6 w-40" />
        <div className="mb-5 grid grid-cols-2 gap-6 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-8 w-12" />
              <Skeleton className="h-3 w-24" />
            </div>
          ))}
        </div>
        <Skeleton className="h-2 w-full rounded-full" />
      </div>
      <div className="card-trinity space-y-2.5 p-6">
        <Skeleton className="mb-4 h-6 w-32" />
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-[68px] w-full rounded-xl" />
        ))}
      </div>
    </div>
  );
}

/**
 * The Program Guide.
 *
 * Two views, swapped in place rather than routed: the module list with program
 * progress, and one module's detail. In place because the guide lives inside an
 * engagement tab that already owns its own navigation, and a nested route would
 * put a module URL under a tab the browser cannot restore anyway.
 *
 * Three reads on mount, deliberately independent. The guide is the authored
 * content, the deliverables are the live state and derived status, and the
 * insights are the diagnostic layer. Only the guide can block rendering: an
 * engagement with no deliverables and no diagnostic is an ordinary new
 * engagement, and it should still show its modules.
 */
export function ProgramGuideTab({
  engagementId,
  diagnostics,
  currentUserId,
  isAdmin = false,
  canReorder = false,
  onNavigateToDiagnostic,
}: ProgramGuideTabProps) {
  const dispatch = useAppDispatch();
  const { view, valueMovement, insights, isLoading, isReordering, error } = useAppSelector(
    (state) => state.programGuide
  );
  const deliverables = useAppSelector((state) => state.deliverables.view);
  const [activeModuleCode, setActiveModuleCode] = useState<string | null>(null);

  useEffect(() => {
    if (!engagementId) return;
    dispatch(fetchProgramGuide(engagementId));
    dispatch(fetchValueMovement(engagementId));
    dispatch(fetchModuleInsights(engagementId));
    dispatch(fetchDeliverables(engagementId));
  }, [engagementId, dispatch]);

  // A module removed from the library while open would otherwise leave the
  // detail view pointing at nothing. Falling back to the list is the only safe
  // resolution - there is no sensible "next" module to jump to.
  useEffect(() => {
    if (!view || !activeModuleCode) return;
    if (!view.modules.some((m) => m.module_code === activeModuleCode)) {
      setActiveModuleCode(null);
    }
  }, [view, activeModuleCode]);

  if (isLoading && !view) return <ProgramGuideSkeleton />;

  if (error && !view) {
    return (
      <div className="py-12 text-center">
        <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-destructive" />
        <p className="mb-1 font-medium text-destructive">Could not load the Program Guide</p>
        <p className="mb-4 text-sm text-muted-foreground">{error}</p>
        <Button variant="outline" onClick={() => dispatch(fetchProgramGuide(engagementId))}>
          Retry
        </Button>
      </div>
    );
  }

  if (!view) return null;

  if (view.modules.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
        No module content has been published for this program yet.
      </div>
    );
  }

  const rankedModules = view.modules.filter((m) => m.effective_rank != null);

  const moveModule = (moduleCode: string, direction: -1 | 1) => {
    const order = rankedModules.map((m) => m.module_code);
    const index = order.indexOf(moduleCode);
    const targetIndex = index + direction;
    if (index === -1 || targetIndex < 0 || targetIndex >= order.length) return;

    const next = [...order];
    [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
    dispatch(reorderModules({ engagementId, moduleOrder: next }))
      .unwrap()
      .catch((message) => toast.error(typeof message === 'string' ? message : 'Failed to reorder modules'));
  };

  const orderBanner = ORDER_SOURCE_LABEL[view.order_source] ? (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-primary/5 px-3.5 py-2">
      <span className="flex items-center gap-2 text-sm text-muted-foreground">
        <Info className="h-4 w-4 flex-shrink-0 text-primary" />
        {ORDER_SOURCE_LABEL[view.order_source]}
      </span>
      {view.order_source === 'custom' && canReorder && (
        <Button
          variant="ghost"
          size="sm"
          disabled={isReordering}
          onClick={() =>
            dispatch(resetModuleOrder(engagementId))
              .unwrap()
              .catch((message) =>
                toast.error(typeof message === 'string' ? message : 'Failed to reset module order')
              )
          }
        >
          <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
          Reset to recommended order
        </Button>
      )}
    </div>
  ) : null;

  /*
    Modules the diagnostic never scored. They sit after the scored ones in
    default taxonomy order rather than being ranked, and an advisor looking at a
    sequence that seems wrong has no other way to find out why. Roughly a third
    of the diagnostic is conditional, so this is ordinary rather than a fault.
  */
  const unscored =
    view.order_source === 'diagnostic'
      ? (insights?.modules ?? []).filter((m) => m.score == null)
      : [];

  if (!activeModuleCode) {
    return (
      <div className="space-y-4">
        <ProgramProgressCard modules={view.modules} deliverables={deliverables} />
        {orderBanner}

        {unscored.length > 0 && (
          <div className="flex items-start gap-2 rounded-lg bg-warning/10 px-3.5 py-2.5 text-sm text-warning">
            <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>
              The diagnostic did not score {unscored.length}{' '}
              {unscored.length === 1 ? 'module' : 'modules'}
              {': '}
              {unscored.map((m) => m.module_name).join(', ')}. Those sit after the scored ones in default
              program order rather than being ranked.
            </span>
          </div>
        )}

        {/*
          Value movement used to live on the M12 capstone card. That module is
          gone, but the comparison is engagement-level rather than M12's, so it
          moves here rather than being deleted with the card. Rendered only when
          there IS a second diagnostic to compare against - its own empty state
          is a prompt to retake, which does not belong at the top of the guide.
        */}
        {valueMovement?.has_comparison && (
          <div className="card-trinity p-6">
            <h2 className="font-heading text-lg font-semibold">Value movement</h2>
            <p className="mb-4 mt-1 text-sm text-muted-foreground">
              How this business has scored across its last two diagnostics.
            </p>
            <ValueMovementView valueMovement={valueMovement} />
          </div>
        )}

        <ModuleList
          modules={view.modules}
          deliverables={deliverables}
          insights={insights}
          canReorder={canReorder}
          isReordering={isReordering}
          onSelect={setActiveModuleCode}
          onMove={moveModule}
        />
      </div>
    );
  }

  const activeIndex = view.modules.findIndex((m) => m.module_code === activeModuleCode);
  const activeModule = view.modules[activeIndex];
  if (!activeModule) return null;

  const moduleDeliverables = deliverables?.modules.find(
    (m) => m.module_code === activeModule.module_code
  );

  return (
    <div key={activeModuleCode} className="animate-in fade-in slide-in-from-right-2 duration-200">
      <ModuleDetail
        module={activeModule}
        nextModule={view.modules[activeIndex + 1]}
        view={view}
        insights={insights}
        moduleDeliverables={moduleDeliverables}
        engagementId={engagementId}
        diagnostics={diagnostics}
        currentUserId={currentUserId}
        isAdmin={isAdmin}
        rankedCount={rankedModules.length}
        onBack={() => setActiveModuleCode(null)}
        onGoToNext={() => {
          const next = view.modules[activeIndex + 1];
          if (next) setActiveModuleCode(next.module_code);
        }}
        onNavigateToDiagnostic={onNavigateToDiagnostic}
      />
    </div>
  );
}
