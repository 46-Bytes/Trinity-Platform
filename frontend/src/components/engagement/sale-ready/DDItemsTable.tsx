import { useState } from 'react';
import { useAppDispatch } from '@/store/hooks';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Plus, Trash2, ClipboardCheck, ExternalLink } from 'lucide-react';
import {
  createDDItem,
  updateDDItem,
  deleteDDItem,
  type DDItem,
} from '@/store/slices/saleReadyReducer';
import type { EngagementMember } from './useEngagementMembers';

interface DDItemsTableProps {
  engagementId: string;
  items: DDItem[];
  /** When set, the "Add item" dialog pre-fills this module_code (module view). Omit for the master view. */
  moduleCode?: string;
  canEdit?: boolean;
  /** Show the Module column (master view). */
  showModuleColumn?: boolean;
  /** Assignable people, for the responsible-person picker. */
  members?: EngagementMember[];
}

const UNASSIGNED = '__none__';

const EMPTY = {
  module_code: '',
  category: '',
  sub_item: '',
  document_required: '',
  action_step: '',
  responsible_user_id: '',
  notes: '',
  file_link: '',
};

export function DDItemsTable({ engagementId, items, moduleCode, canEdit = false, showModuleColumn = false, members = [] }: DDItemsTableProps) {
  const dispatch = useAppDispatch();
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [draft, setDraft] = useState({ ...EMPTY, module_code: moduleCode || '' });

  const nameById = (id?: string | null) => (id ? (members.find((m) => m.id === id)?.name || '—') : '—');

  const handleToggleComplete = (item: DDItem, completed: boolean) => {
    dispatch(updateDDItem({ engagementId, itemId: item.id, updates: { completed } }));
  };

  const handleFieldBlur = (item: DDItem, field: keyof DDItem, value: string) => {
    if ((item[field] ?? '') === value) return;
    dispatch(updateDDItem({ engagementId, itemId: item.id, updates: { [field]: value } as Partial<DDItem> }));
  };

  const handleResponsible = (item: DDItem, value: string) => {
    dispatch(updateDDItem({ engagementId, itemId: item.id, updates: { responsible_user_id: value === UNASSIGNED ? null : value } }));
  };

  const handleAdd = () => {
    dispatch(createDDItem({
      engagementId,
      data: {
        ...draft,
        module_code: moduleCode || draft.module_code,
        // Empty UUID string would fail validation — send null instead.
        responsible_user_id: draft.responsible_user_id || null,
        file_link: draft.file_link || null,
      },
    }));
    setDraft({ ...EMPTY, module_code: moduleCode || '' });
    setIsAddOpen(false);
  };

  return (
    <div className="space-y-3">
      {canEdit && (
        <div className="flex justify-end">
          <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline">
                <Plus className="h-4 w-4 mr-1.5" /> Add DD item
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Due Diligence item</DialogTitle>
              </DialogHeader>
              <div className="space-y-3">
                {!moduleCode && (
                  <div className="space-y-1">
                    <Label>Module code</Label>
                    <Input value={draft.module_code} onChange={(e) => setDraft({ ...draft, module_code: e.target.value })} placeholder="e.g. M_FIN" />
                  </div>
                )}
                <div className="space-y-1">
                  <Label>Category *</Label>
                  <Input value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })} />
                </div>
                <div className="space-y-1">
                  <Label>Sub-item</Label>
                  <Textarea rows={2} value={draft.sub_item} onChange={(e) => setDraft({ ...draft, sub_item: e.target.value })} />
                </div>
                <div className="space-y-1">
                  <Label>Document required</Label>
                  <Input value={draft.document_required} onChange={(e) => setDraft({ ...draft, document_required: e.target.value })} />
                </div>
                <div className="space-y-1">
                  <Label>Action step</Label>
                  <Input value={draft.action_step} onChange={(e) => setDraft({ ...draft, action_step: e.target.value })} />
                </div>
                <div className="space-y-1">
                  <Label>Responsible person</Label>
                  <Select value={draft.responsible_user_id || UNASSIGNED} onValueChange={(v) => setDraft({ ...draft, responsible_user_id: v === UNASSIGNED ? '' : v })}>
                    <SelectTrigger><SelectValue placeholder="Unassigned" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
                      {members.map((m) => <SelectItem key={m.id} value={m.id}>{m.name || m.id}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label>File link (cloud/Drive)</Label>
                  <Input value={draft.file_link} onChange={(e) => setDraft({ ...draft, file_link: e.target.value })} placeholder="https://…" />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsAddOpen(false)}>Cancel</Button>
                <Button onClick={handleAdd} disabled={!draft.category || (!moduleCode && !draft.module_code)}>Add</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-border/60">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 hover:bg-muted/50">
              <TableHead className="w-10">Done</TableHead>
              {showModuleColumn && <TableHead>Module</TableHead>}
              <TableHead>Category</TableHead>
              <TableHead>Sub-item</TableHead>
              <TableHead>Document required</TableHead>
              <TableHead>Action step</TableHead>
              <TableHead>Responsible</TableHead>
              <TableHead>Completed</TableHead>
              <TableHead>File</TableHead>
              <TableHead>Notes</TableHead>
              {canEdit && <TableHead className="w-10" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.length === 0 ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={showModuleColumn ? 11 : 10} className="py-8">
                  <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
                    <ClipboardCheck className="h-5 w-5 opacity-60" />
                    No due diligence items.
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              items.map((item) => (
                <TableRow key={item.id} className={item.completed ? 'opacity-60' : ''}>
                  <TableCell>
                    <Checkbox
                      checked={item.completed}
                      disabled={!canEdit}
                      onCheckedChange={(v) => handleToggleComplete(item, !!v)}
                    />
                  </TableCell>
                  {showModuleColumn && (
                    <TableCell>
                      <Badge variant="secondary" className="rounded-full font-mono text-[10px]">{item.module_code}</Badge>
                    </TableCell>
                  )}
                  <TableCell className="whitespace-nowrap">
                    <Badge variant="secondary" className="rounded-full font-normal bg-info/10 text-info hover:bg-info/10">{item.category}</Badge>
                  </TableCell>
                  <TableCell className="min-w-[180px]">{item.sub_item}</TableCell>
                  <TableCell className="min-w-[160px]">{item.document_required}</TableCell>
                  <TableCell className="min-w-[160px]">{item.action_step}</TableCell>
                  <TableCell className="min-w-[150px]">
                    {canEdit ? (
                      <Select value={item.responsible_user_id || UNASSIGNED} onValueChange={(v) => handleResponsible(item, v)}>
                        <SelectTrigger className="h-8"><SelectValue placeholder="Unassigned" /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
                          {members.map((m) => <SelectItem key={m.id} value={m.id}>{m.name || m.id}</SelectItem>)}
                        </SelectContent>
                      </Select>
                    ) : (
                      <span className="text-muted-foreground">{nameById(item.responsible_user_id)}</span>
                    )}
                  </TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">{item.date_completed || '—'}</TableCell>
                  <TableCell className="min-w-[140px]">
                    {canEdit ? (
                      <Input
                        defaultValue={item.file_link || ''}
                        className="h-8"
                        placeholder="Link…"
                        onBlur={(e) => handleFieldBlur(item, 'file_link', e.target.value)}
                      />
                    ) : item.file_link ? (
                      <a href={item.file_link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                        Open <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    ) : <span className="text-muted-foreground">—</span>}
                  </TableCell>
                  <TableCell className="min-w-[160px]">
                    {canEdit ? (
                      <Input
                        defaultValue={item.notes || ''}
                        className="h-8"
                        onBlur={(e) => handleFieldBlur(item, 'notes', e.target.value)}
                      />
                    ) : (
                      item.notes
                    )}
                  </TableCell>
                  {canEdit && (
                    <TableCell>
                      <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive" onClick={() => dispatch(deleteDDItem({ engagementId, itemId: item.id }))}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  )}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
