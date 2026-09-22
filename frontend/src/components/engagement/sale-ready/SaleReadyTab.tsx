import { useEffect, useState, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  addStageTask,
  clearSaleReady,
  closeProgram,
  closeStage,
  completeStage,
  fetchCloseout,
  fetchSaleReadyGuide,
  fetchDDChecklist,
  fetchSalePlanner,
  fetchSaleReadyRoadmap,
  fetchStageDetail,
  reopenProgram,
  reopenStage,
  reorderSaleReadyModules,
  resetSaleReadyOrder,
  startStage,
  updateCloseout,
  updateDDItem,
  updateSalePlanner,
  updateStage,
  updateStageTask,
} from '@/store/slices/saleReadyReducer';
import { CloseoutPanel } from './CloseoutPanel';
import { DDChecklistView } from './DDChecklistView';
import { FilesView } from './FilesView';
import { ProgramGuideView } from './ProgramGuideView';
import { RoadmapView } from './RoadmapView';
import { SalePlannerPanel } from './SalePlannerPanel';
import { StageDetailView } from './StageDetailView';
import type { DDItem, DDItemUpdate } from './types';

interface SaleReadyTabProps {
  engagementId: string;
  /** Owner mode: Roadmap, DD checklist and Files only, all read-only. */
  readOnly?: boolean;
  /** Closing or reopening the program changes the engagement's status. */
  onEngagementStatusChange?: () => void;
}

type SubTab = 'roadmap' | 'dd' | 'files' | 'guide';

// Underlined sub-tabs, as in the mockup, so they read as a level below the engagement tabs.
const SUB_TAB =
  '-mb-px gap-2 rounded-none border-b-2 border-transparent bg-transparent px-0.5 pb-3 pt-2 text-sm font-medium ' +
  'text-muted-foreground shadow-none data-[state=active]:border-success data-[state=active]:bg-transparent ' +
  'data-[state=active]:font-semibold data-[state=active]:text-foreground data-[state=active]:shadow-none';

const ORDER_SOURCE_LABEL: Record<string, string> = {
  diagnostic: "Order proposed by this client's diagnostic, weakest-scoring modules first.",
  custom: 'Custom order, set by an advisor on this engagement.',
  default: 'Default order. The diagnostic proposes a tailored order once it has scores.',
};

function LoadingState() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-40 w-full rounded-xl" />
      <Skeleton className="h-32 w-full rounded-xl" />
      <Skeleton className="h-64 w-full rounded-xl" />
    </div>
  );
}

function errorMessage(error: unknown, fallback: string): string {
  return typeof error === 'string' ? error : fallback;
}

/**
 * The Sale Ready program: its own workflow of stages, tasks and DD items, not
 * the Value Builder deliverable guide. Four sub-tabs as in the client's mockup.
 */
export function SaleReadyTab({ engagementId, readOnly = false, onEngagementStatusChange }: SaleReadyTabProps) {
  const dispatch = useAppDispatch();
  const {
    roadmap,
    checklist,
    stage,
    salePlanner,
    closeout,
    guide,
    isLoadingRoadmap,
    isLoadingChecklist,
    isReordering,
    isSaving,
    error,
  } = useAppSelector((state) => state.saleReady);
  const [tab, setTab] = useState<SubTab>('roadmap');
  const [openStage, setOpenStage] = useState<string | null>(null);

  useEffect(() => {
    dispatch(clearSaleReady());
    dispatch(fetchSaleReadyRoadmap(engagementId));
    dispatch(fetchDDChecklist(engagementId));
  }, [engagementId, dispatch]);

  const fail = (fallback: string) => (e: unknown) => toast.error(errorMessage(e, fallback));

  const openStageDetail = (code: string) => {
    setTab('roadmap');
    setOpenStage(code);
    dispatch(fetchStageDetail({ engagementId, stageCode: code }))
      .unwrap()
      .catch(fail('Failed to load the stage'));
    const variant = [...(roadmap?.phases ?? []), ...(roadmap?.modules ?? []), ...(roadmap?.post_phases ?? [])].find(
      (s) => s.stage_code === code
    )?.ui_variant;
    if (variant === 'sale_planner') dispatch(fetchSalePlanner(engagementId)).unwrap().catch(fail('Failed to load the Sale Planner'));
    if (variant === 'closeout') dispatch(fetchCloseout(engagementId)).unwrap().catch(fail('Failed to load the close-out'));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const backToRoadmap = () => {
    setOpenStage(null);
    dispatch(closeStage());
    // Counts and status changed while the stage was open.
    dispatch(fetchSaleReadyRoadmap(engagementId));
  };

  const changeTab = (next: string) => {
    if (openStage) backToRoadmap();
    if (next === 'roadmap' && !openStage) dispatch(fetchSaleReadyRoadmap(engagementId));
    if (next === 'guide') dispatch(fetchSaleReadyGuide(engagementId));
    setTab(next as SubTab);
  };

  const onUpdateDD = (item: DDItem, changes: DDItemUpdate) => {
    dispatch(updateDDItem({ engagementId, itemId: item.id, changes }))
      .unwrap()
      .then(() => {
        // The stage's QA and counts depend on its DD statuses.
        if (openStage) dispatch(fetchStageDetail({ engagementId, stageCode: openStage }));
      })
      .catch(fail('Failed to update the DD item'));
  };

  if (!roadmap) {
    if (isLoadingRoadmap || !error) return <LoadingState />;
    return (
      <div className="py-12 text-center">
        <AlertTriangle className="mx-auto mb-3 h-8 w-8 text-destructive" />
        <p className="mb-1 font-medium text-destructive">Could not load the Sale Ready program</p>
        <p className="mb-4 text-sm text-muted-foreground">{error}</p>
        <Button variant="outline" onClick={() => dispatch(fetchSaleReadyRoadmap(engagementId))}>
          Retry
        </Button>
      </div>
    );
  }

  const ddDone = checklist ? `${checklist.stats.yes}/${checklist.stats.total}` : null;
  const stageArg = openStage ? { engagementId, stageCode: openStage } : null;

  const variantPanel = () => {
    const variant = stage?.stage.ui_variant;
    if (variant === 'sale_planner') {
      if (!salePlanner) return <LoadingState />;
      return (
        <SalePlannerPanel
          planner={salePlanner}
          onChange={(changes) =>
            dispatch(updateSalePlanner({ engagementId, changes })).unwrap().catch(fail('Failed to save the Sale Planner'))
          }
        />
      );
    }
    if (variant === 'closeout') {
      if (!closeout) return <LoadingState />;
      return (
        <CloseoutPanel
          closeout={closeout}
          isSaving={isSaving}
          onChange={(changes) =>
            dispatch(updateCloseout({ engagementId, changes })).unwrap().catch(fail('Failed to save the close-out'))
          }
          onClose={(changes, confirmWithoutReferral) =>
            dispatch(closeProgram({ engagementId, changes, confirmWithoutReferral }))
              .unwrap()
              .then(() => {
                toast.success('Program closed. The engagement has ended.');
                onEngagementStatusChange?.();
              })
              .catch(fail('Failed to close the program'))
          }
          onReopen={() =>
            dispatch(reopenProgram(engagementId))
              .unwrap()
              .then(() => {
                toast.success('Program reopened. The engagement is active again.');
                onEngagementStatusChange?.();
              })
              .catch(fail('Failed to reopen the program'))
          }
        />
      );
    }
    return null;
  };

  const renderRoadmap = () => {
    if (openStage && !readOnly) {
      if (!stage || stage.stage.stage_code !== openStage) return <LoadingState />;
      return (
        <StageDetailView
          detail={stage}
          modulesTotal={roadmap.modules.length}
          isSaving={isSaving}
          onBack={backToRoadmap}
          onStart={() =>
            stageArg &&
            dispatch(startStage(stageArg))
              .unwrap()
              .then((d) => d.tasks.length && toast.success(`${d.tasks.length} tasks ready`))
              .catch(fail('Failed to start the stage'))
          }
          onComplete={() =>
            stageArg &&
            dispatch(completeStage(stageArg))
              .unwrap()
              .then(() => toast.success(`${stage.stage.title} marked complete`))
              .catch(fail('Failed to mark the stage complete'))
          }
          onReopen={() => stageArg && dispatch(reopenStage(stageArg)).unwrap().catch(fail('Failed to reopen the stage'))}
          onUpdateStage={(changes) =>
            stageArg && dispatch(updateStage({ ...stageArg, changes })).unwrap().catch(fail('Failed to update the stage'))
          }
          onAddTask={(title) =>
            stageArg &&
            dispatch(addStageTask({ ...stageArg, title }))
              .unwrap()
              .then(() => toast.success('Task created in the Tasks system'))
              .catch(fail('Failed to add the task'))
          }
          onUpdateTask={(taskId, changes) =>
            dispatch(updateStageTask({ engagementId, taskId, changes })).unwrap().catch(fail('Failed to update the task'))
          }
          onUpdateDD={onUpdateDD}
          variantPanel={variantPanel()}
        />
      );
    }

    return (
      <div className="space-y-4">
        {ORDER_SOURCE_LABEL[roadmap.order_source] && (
          <p className="text-sm text-muted-foreground">{ORDER_SOURCE_LABEL[roadmap.order_source]}</p>
        )}
        <RoadmapView
          roadmap={roadmap}
          readOnly={readOnly}
          canReorder={!readOnly}
          isReordering={isReordering}
          onReorder={(moduleOrder) =>
            dispatch(reorderSaleReadyModules({ engagementId, moduleOrder }))
              .unwrap()
              .then(() => toast.success('Roadmap order updated'))
              .catch(fail('Failed to reorder modules'))
          }
          onResetOrder={() =>
            dispatch(resetSaleReadyOrder(engagementId))
              .unwrap()
              .then(() => toast.success("Order reset to the diagnostic's proposal"))
              .catch(fail('Failed to reset the module order'))
          }
          onOpenStage={openStageDetail}
        />
      </div>
    );
  };

  const needsChecklist = (content: (items: NonNullable<typeof checklist>) => ReactNode) =>
    checklist ? content(checklist) : isLoadingChecklist || !error ? <LoadingState /> : (
      <p className="py-8 text-center text-sm text-destructive">{error}</p>
    );

  return (
    <Tabs value={tab} onValueChange={changeTab}>
      <TabsList className="mb-6 h-auto w-full flex-wrap justify-start gap-x-6 gap-y-1 rounded-none border-b border-border bg-transparent p-0">
        <TabsTrigger value="roadmap" className={SUB_TAB}>
          Roadmap
        </TabsTrigger>
        <TabsTrigger value="dd" className={SUB_TAB}>
          Due diligence checklist
          {ddDone && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] font-semibold text-muted-foreground">
              {ddDone}
            </span>
          )}
        </TabsTrigger>
        <TabsTrigger value="files" className={SUB_TAB}>
          Files
        </TabsTrigger>
        {!readOnly && (
          <TabsTrigger value="guide" className={SUB_TAB}>
            Program guide
          </TabsTrigger>
        )}
      </TabsList>

      <TabsContent value="roadmap">{renderRoadmap()}</TabsContent>
      <TabsContent value="dd">
        {needsChecklist((c) => (
          <DDChecklistView
            checklist={c}
            readOnly={readOnly}
            onOpenStage={readOnly ? undefined : openStageDetail}
            onChange={onUpdateDD}
          />
        ))}
      </TabsContent>
      <TabsContent value="files">{needsChecklist((c) => <FilesView items={c.items} />)}</TabsContent>
      {!readOnly && (
        <TabsContent value="guide">
          <ProgramGuideView roadmap={roadmap} guide={guide} onOpenStage={openStageDetail} />
        </TabsContent>
      )}
    </Tabs>
  );
}
