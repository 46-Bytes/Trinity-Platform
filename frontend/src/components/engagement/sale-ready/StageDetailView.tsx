import { useMemo } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Info, ListChecks, FileText, ClipboardCheck } from 'lucide-react';
import { updateStage, type SaleReadyStage, type StageStatus } from '@/store/slices/saleReadyReducer';
import { StageTasksSection } from './StageTasksSection';
import { DocumentRegisterTable } from './DocumentRegisterTable';
import { DDItemsTable } from './DDItemsTable';
import { StatusPill, stageIcon, SectionLabel } from './saleReadyUi';
import { useEngagementMembers } from './useEngagementMembers';

const UNASSIGNED = '__none__';

interface StageDetailViewProps {
  engagementId: string;
  stage: SaleReadyStage;
  canEdit?: boolean;
}

export function StageDetailView({ engagementId, stage, canEdit = false }: StageDetailViewProps) {
  const dispatch = useAppDispatch();
  const allTasks = useAppSelector((s) => s.task.tasks);
  const ddItems = useAppSelector((s) => s.saleReady.ddItems);
  const documents = useAppSelector((s) => s.saleReady.documents);

  const stageTasks = useMemo(
    () => allTasks.filter((t) => t.engagementId === engagementId && t.moduleReference === stage.stage_code),
    [allTasks, engagementId, stage.stage_code],
  );
  const allTasksDone = stageTasks.length > 0 && stageTasks.every((t) => t.status === 'completed');

  const moduleDDItems = useMemo(() => ddItems.filter((d) => d.module_code === stage.stage_code), [ddItems, stage.stage_code]);
  const stageDocuments = useMemo(() => documents.filter((d) => d.stage_code === stage.stage_code), [documents, stage.stage_code]);

  const { members } = useEngagementMembers(engagementId);
  const advisors = useMemo(
    () => members.filter((m) => (m.role || '').includes('advisor') || (m.role || '').includes('admin')),
    [members],
  );

  const patch = (updates: Partial<Pick<SaleReadyStage, 'status' | 'start_date' | 'due_date' | 'lead_advisor_id'>>) =>
    dispatch(updateStage({ engagementId, stageCode: stage.stage_code, updates }));

  const isModule = stage.stage_type === 'module';
  const Icon = stageIcon(stage.stage_code);

  return (
    <div className="space-y-5">
      {/* Header card */}
      <div className="stat-card">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="flex items-start gap-3.5">
            <div className="p-3 rounded-xl bg-accent/10 text-accent flex-shrink-0">
              <Icon className="h-6 w-6" />
            </div>
            <div>
              <h2 className="font-heading text-2xl font-bold tracking-tight">{stage.title}</h2>
              {stage.description && <p className="text-sm text-muted-foreground mt-1 max-w-2xl">{stage.description}</p>}
            </div>
          </div>
          <StatusPill status={stage.status} />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mt-5">
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Status</Label>
            <Select value={stage.status} onValueChange={(v) => patch({ status: v as StageStatus })} disabled={!canEdit}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="not_started">Not Started</SelectItem>
                <SelectItem value="in_progress">In Progress</SelectItem>
                <SelectItem value="complete">Complete</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Lead advisor</Label>
            <Select
              value={stage.lead_advisor_id || UNASSIGNED}
              onValueChange={(v) => patch({ lead_advisor_id: v === UNASSIGNED ? null : v })}
              disabled={!canEdit}
            >
              <SelectTrigger><SelectValue placeholder="Unassigned" /></SelectTrigger>
              <SelectContent>
                <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
                {advisors.map((a) => (
                  <SelectItem key={a.id} value={a.id}>{a.name || a.id}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Start date</Label>
            <Input type="date" defaultValue={stage.start_date || ''} disabled={!canEdit} onBlur={(e) => patch({ start_date: e.target.value || null })} />
          </div>
          <div className="space-y-1">
            <Label className="text-xs text-muted-foreground">Due date</Label>
            <Input type="date" defaultValue={stage.due_date || ''} disabled={!canEdit} onBlur={(e) => patch({ due_date: e.target.value || null })} />
          </div>
        </div>

        {canEdit && allTasksDone && stage.status !== 'complete' && (
          <div className="flex items-center justify-between gap-3 flex-wrap rounded-lg bg-primary/5 px-3.5 py-2 mt-4">
            <span className="flex items-center gap-2 text-sm text-muted-foreground">
              <Info className="h-4 w-4 text-primary flex-shrink-0" />
              All tasks in this stage are complete.
            </span>
            <Button variant="ghost" size="sm" onClick={() => patch({ status: 'complete' })}>Mark stage Complete</Button>
          </div>
        )}
      </div>

      {/* Tasks */}
      <div className="card-trinity p-6">
        <SectionLabel icon={ListChecks}>Tasks</SectionLabel>
        <StageTasksSection engagementId={engagementId} stageCode={stage.stage_code} canEdit={canEdit} />
      </div>

      {/* Document register */}
      <div className="card-trinity p-6">
        <SectionLabel icon={FileText}>Document Register</SectionLabel>
        <DocumentRegisterTable engagementId={engagementId} stageCode={stage.stage_code} entries={stageDocuments} canEdit={canEdit} />
      </div>

      {/* DD items (modules only) */}
      {isModule && (
        <div className="card-trinity p-6">
          <SectionLabel icon={ClipboardCheck}>Due Diligence Items</SectionLabel>
          <DDItemsTable engagementId={engagementId} items={moduleDDItems} moduleCode={stage.stage_code} canEdit={canEdit} members={members} />
        </div>
      )}
    </div>
  );
}
