import { useEffect, useState, useMemo } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { useAuth } from '@/context/AuthContext';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { CheckCircle2, Clock, Circle } from 'lucide-react';
import { fetchTasks } from '@/store/slices/tasksReducer';
import { fetchStages, fetchDDItems, fetchDocuments } from '@/store/slices/saleReadyReducer';
import { RoadmapView } from './RoadmapView';
import { StageDetailView } from './StageDetailView';
import { MasterDDView } from './MasterDDView';
import { StatusDot, stageIcon, ProgressBar } from './saleReadyUi';

interface SaleReadyProgramTabProps {
  engagementId: string;
}

const STAGE_GROUP_LABEL: Record<string, string> = {
  pre_module: 'Pre-Module Phases',
  module: 'Modules',
  post_module: 'Post-Module',
};
const GROUP_ORDER = ['pre_module', 'module', 'post_module'];

function SaleReadySkeleton() {
  return (
    <div className="space-y-4">
      <div className="card-trinity p-6 space-y-4">
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-2 w-full rounded-full" />
        <div className="flex gap-3">
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-6 w-24 rounded-full" />
          <Skeleton className="h-6 w-24 rounded-full" />
        </div>
      </div>
      <Skeleton className="h-9 w-72" />
      <div className="card-trinity p-6 space-y-3">
        <Skeleton className="h-16 w-full rounded-lg" />
        <Skeleton className="h-16 w-full rounded-lg" />
        <Skeleton className="h-16 w-full rounded-lg" />
      </div>
    </div>
  );
}

export function SaleReadyProgramTab({ engagementId }: SaleReadyProgramTabProps) {
  const dispatch = useAppDispatch();
  const { user } = useAuth();
  const { stages, ddItems, isLoading, error } = useAppSelector((s) => s.saleReady);
  const [subTab, setSubTab] = useState('roadmap');
  const [activeStageCode, setActiveStageCode] = useState<string | null>(null);

  const canEdit = ['advisor', 'firm_advisor', 'admin', 'super_admin', 'firm_admin'].includes(user?.role || '');

  useEffect(() => {
    if (!engagementId) return;
    dispatch(fetchStages(engagementId));
    dispatch(fetchDDItems(engagementId));
    dispatch(fetchDocuments(engagementId));
    dispatch(fetchTasks({ engagementId, limit: 1000 }));
  }, [engagementId, dispatch]);

  useEffect(() => {
    if (!stages.length) return;
    setActiveStageCode((prev) => (prev && stages.some((s) => s.stage_code === prev) ? prev : stages[0].stage_code));
  }, [stages]);

  const groupedStages = useMemo(() => {
    const groups: Record<string, typeof stages> = { pre_module: [], module: [], post_module: [] };
    stages.forEach((s) => groups[s.stage_type]?.push(s));
    return groups;
  }, [stages]);

  const summary = useMemo(() => {
    const total = stages.length;
    const complete = stages.filter((s) => s.status === 'complete').length;
    const inProgress = stages.filter((s) => s.status === 'in_progress').length;
    const notStarted = total - complete - inProgress;
    const pct = total === 0 ? 0 : Math.round((complete / total) * 100);
    const ddDone = ddItems.filter((d) => d.completed).length;
    return { total, complete, inProgress, notStarted, pct, ddDone, ddTotal: ddItems.length };
  }, [stages, ddItems]);

  const activeStage = useMemo(() => stages.find((s) => s.stage_code === activeStageCode) || null, [stages, activeStageCode]);

  const openStage = (stageCode: string) => {
    setActiveStageCode(stageCode);
    setSubTab('stages');
  };

  if (isLoading && !stages.length) return <SaleReadySkeleton />;
  if (error && !stages.length) return <div className="py-8 text-center text-sm text-destructive">{error}</div>;
  if (!stages.length) return <div className="py-8 text-center text-sm text-muted-foreground">This Sale Ready program has not been set up yet.</div>;

  return (
    <div className="space-y-5">
      {/* Program progress header */}
      <div className="card-trinity p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h2 className="font-heading text-2xl font-bold tracking-tight">Sale Ready Program</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              {summary.complete} of {summary.total} phases &amp; modules complete
            </p>
          </div>
          <div className="text-right">
            <div className="font-heading text-3xl font-bold leading-none">{summary.pct}%</div>
            <p className="text-xs text-muted-foreground mt-1">overall</p>
          </div>
        </div>
        <ProgressBar pct={summary.pct} className="mt-4" />
        <div className="flex flex-wrap items-center gap-2 mt-4">
          <Badge variant="secondary" className="rounded-full gap-1.5 bg-success/10 text-success hover:bg-success/10">
            <CheckCircle2 className="h-3.5 w-3.5" /> {summary.complete} Complete
          </Badge>
          <Badge variant="secondary" className="rounded-full gap-1.5 bg-warning/10 text-warning hover:bg-warning/10">
            <Clock className="h-3.5 w-3.5" /> {summary.inProgress} In Progress
          </Badge>
          <Badge variant="secondary" className="rounded-full gap-1.5">
            <Circle className="h-3.5 w-3.5" /> {summary.notStarted} Not Started
          </Badge>
          {summary.ddTotal > 0 && (
            <Badge variant="secondary" className="rounded-full">
              Due Diligence {summary.ddDone}/{summary.ddTotal}
            </Badge>
          )}
        </div>
      </div>

      <Tabs value={subTab} onValueChange={setSubTab} className="w-full">
        <TabsList className="grid w-fit grid-cols-3">
          <TabsTrigger value="roadmap">Roadmap</TabsTrigger>
          <TabsTrigger value="stages">Stages</TabsTrigger>
          <TabsTrigger value="dd" className="gap-1.5">
            Due Diligence
            {summary.ddTotal > 0 && (
              <span className="text-xs text-muted-foreground">{summary.ddDone}/{summary.ddTotal}</span>
            )}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="roadmap" className="mt-4 animate-in fade-in duration-200">
          <RoadmapView engagementId={engagementId} canEdit={canEdit} onOpenStage={openStage} />
        </TabsContent>

        <TabsContent value="stages" className="mt-4 animate-in fade-in duration-200">
          <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-6">
            <nav className="space-y-4">
              {GROUP_ORDER.map((group) => (
                groupedStages[group]?.length ? (
                  <div key={group} className="space-y-1">
                    <p className="px-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{STAGE_GROUP_LABEL[group]}</p>
                    {groupedStages[group].map((s) => {
                      const Icon = stageIcon(s.stage_code);
                      const isActive = s.stage_code === activeStageCode;
                      return (
                        <button
                          key={s.stage_code}
                          onClick={() => setActiveStageCode(s.stage_code)}
                          className={`group w-full flex items-center gap-2.5 rounded-md border-l-2 px-2.5 py-2 text-left text-sm transition-colors ${
                            isActive
                              ? 'border-primary bg-primary/10 text-primary font-medium'
                              : 'border-transparent hover:bg-muted'
                          }`}
                        >
                          <Icon className={`h-4 w-4 flex-shrink-0 ${isActive ? 'text-primary' : 'text-muted-foreground'}`} />
                          <span className="truncate flex-1">{s.title}</span>
                          <StatusDot status={s.status} />
                        </button>
                      );
                    })}
                  </div>
                ) : null
              ))}
            </nav>

            <div key={activeStageCode} className="animate-in fade-in slide-in-from-right-2 duration-200">
              {activeStage ? (
                <StageDetailView engagementId={engagementId} stage={activeStage} canEdit={canEdit} />
              ) : (
                <p className="text-sm text-muted-foreground">Select a stage.</p>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="dd" className="mt-4 animate-in fade-in duration-200">
          <MasterDDView engagementId={engagementId} canEdit={canEdit} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
