import { useMemo, useState } from 'react';
import { useAppSelector } from '@/store/hooks';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DDItemsTable } from './DDItemsTable';
import { ProgressBar } from './saleReadyUi';
import { useEngagementMembers } from './useEngagementMembers';

interface MasterDDViewProps {
  engagementId: string;
  canEdit?: boolean;
}

const ALL = '__all__';

export function MasterDDView({ engagementId, canEdit = false }: MasterDDViewProps) {
  const ddItems = useAppSelector((s) => s.saleReady.ddItems);
  const stages = useAppSelector((s) => s.saleReady.stages);
  const { members } = useEngagementMembers(engagementId);
  const [moduleFilter, setModuleFilter] = useState<string>(ALL);
  const [categoryFilter, setCategoryFilter] = useState<string>(ALL);
  const [statusFilter, setStatusFilter] = useState<string>(ALL);
  const [responsibleFilter, setResponsibleFilter] = useState<string>(ALL);

  const moduleOptions = useMemo(() => stages.filter((s) => s.stage_type === 'module'), [stages]);
  const categories = useMemo(() => Array.from(new Set(ddItems.map((d) => d.category))).sort(), [ddItems]);

  const filtered = useMemo(() => {
    return ddItems.filter((d) => {
      if (moduleFilter !== ALL && d.module_code !== moduleFilter) return false;
      if (categoryFilter !== ALL && d.category !== categoryFilter) return false;
      if (statusFilter === 'completed' && !d.completed) return false;
      if (statusFilter === 'outstanding' && d.completed) return false;
      if (responsibleFilter === '__unassigned__' && d.responsible_user_id) return false;
      if (responsibleFilter !== ALL && responsibleFilter !== '__unassigned__' && d.responsible_user_id !== responsibleFilter) return false;
      return true;
    });
  }, [ddItems, moduleFilter, categoryFilter, statusFilter, responsibleFilter]);

  const total = ddItems.length;
  const done = ddItems.filter((d) => d.completed).length;
  const pct = total === 0 ? 0 : Math.round((done / total) * 100);

  return (
    <div className="space-y-4">
      {/* Progress header */}
      <div className="card-trinity p-6">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h3 className="font-heading text-xl font-bold tracking-tight">Due Diligence Checklist</h3>
            <p className="text-sm text-muted-foreground mt-0.5 max-w-xl">
              All due-diligence items across modules. Edits here reflect in the module view and vice-versa.
            </p>
          </div>
          <div className="text-right">
            <div className="font-heading text-2xl font-bold leading-none">{done}<span className="text-muted-foreground text-base font-normal">/{total}</span></div>
            <p className="text-xs text-muted-foreground mt-1">complete</p>
          </div>
        </div>
        <ProgressBar pct={pct} className="mt-4" />
      </div>

      {/* Filter toolbar */}
      <div className="card-trinity p-3 flex items-center gap-2 flex-wrap">
        <Select value={moduleFilter} onValueChange={setModuleFilter}>
          <SelectTrigger className="w-[190px]"><SelectValue placeholder="Module" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All modules</SelectItem>
            {moduleOptions.map((m) => <SelectItem key={m.stage_code} value={m.stage_code}>{m.title}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[160px]"><SelectValue placeholder="Category" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All categories</SelectItem>
            {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[150px]"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All</SelectItem>
            <SelectItem value="outstanding">Outstanding</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
          </SelectContent>
        </Select>
        <Select value={responsibleFilter} onValueChange={setResponsibleFilter}>
          <SelectTrigger className="w-[170px]"><SelectValue placeholder="Responsible" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Anyone responsible</SelectItem>
            <SelectItem value="__unassigned__">Unassigned</SelectItem>
            {members.map((m) => <SelectItem key={m.id} value={m.id}>{m.name || m.id}</SelectItem>)}
          </SelectContent>
        </Select>
        <span className="text-xs text-muted-foreground ml-auto">{filtered.length} of {total} shown</span>
      </div>

      <DDItemsTable engagementId={engagementId} items={filtered} canEdit={canEdit} showModuleColumn members={members} />
    </div>
  );
}
