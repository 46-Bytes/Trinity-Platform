import { useState } from 'react';
import { useAppDispatch } from '@/store/hooks';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Plus, Trash2, FileText, ExternalLink, Pencil } from 'lucide-react';
import {
  createDocument,
  updateDocument,
  deleteDocument,
  type DocumentEntry,
} from '@/store/slices/saleReadyReducer';

interface DocumentRegisterTableProps {
  engagementId: string;
  stageCode: string;
  entries: DocumentEntry[];
  canEdit?: boolean;
}

const EMPTY = {
  document_name: '',
  document_id: '',
  creation_date: '',
  renewal_date: '',
  renewal_cost: '',
  notes: '',
  file_link: '',
};

export function DocumentRegisterTable({ engagementId, stageCode, entries, canEdit = false }: DocumentRegisterTableProps) {
  const dispatch = useAppDispatch();
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState(EMPTY);

  const openAdd = () => {
    setEditingId(null);
    setDraft(EMPTY);
    setIsDialogOpen(true);
  };

  const openEdit = (entry: DocumentEntry) => {
    setEditingId(entry.id);
    setDraft({
      document_name: entry.document_name || '',
      document_id: entry.document_id || '',
      creation_date: entry.creation_date || '',
      renewal_date: entry.renewal_date || '',
      renewal_cost: entry.renewal_cost != null ? String(entry.renewal_cost) : '',
      notes: entry.notes || '',
      file_link: entry.file_link || '',
    });
    setIsDialogOpen(true);
  };

  const handleSave = () => {
    const payload = {
      document_name: draft.document_name,
      document_id: draft.document_id || null,
      creation_date: draft.creation_date || null,
      renewal_date: draft.renewal_date || null,
      renewal_cost: draft.renewal_cost ? Number(draft.renewal_cost) : null,
      notes: draft.notes || null,
      file_link: draft.file_link || null,
    };
    if (editingId) {
      dispatch(updateDocument({ engagementId, entryId: editingId, updates: payload }));
    } else {
      dispatch(createDocument({ engagementId, data: { stage_code: stageCode, ...payload } }));
    }
    setDraft(EMPTY);
    setEditingId(null);
    setIsDialogOpen(false);
  };

  return (
    <div className="space-y-3">
      {canEdit && (
        <div className="flex justify-end">
          <Button size="sm" variant="outline" onClick={openAdd}>
            <Plus className="h-4 w-4 mr-1.5" /> Add document
          </Button>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{editingId ? 'Edit document register entry' : 'Add document register entry'}</DialogTitle>
              </DialogHeader>
              <div className="space-y-3">
                <div className="space-y-1">
                  <Label>Document name *</Label>
                  <Input value={draft.document_name} onChange={(e) => setDraft({ ...draft, document_name: e.target.value })} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label>Document ID</Label>
                    <Input value={draft.document_id} onChange={(e) => setDraft({ ...draft, document_id: e.target.value })} />
                  </div>
                  <div className="space-y-1">
                    <Label>Creation date</Label>
                    <Input type="date" value={draft.creation_date} onChange={(e) => setDraft({ ...draft, creation_date: e.target.value })} />
                  </div>
                  <div className="space-y-1">
                    <Label>Renewal date</Label>
                    <Input type="date" value={draft.renewal_date} onChange={(e) => setDraft({ ...draft, renewal_date: e.target.value })} />
                  </div>
                  <div className="space-y-1">
                    <Label>Renewal cost</Label>
                    <Input type="number" step="0.01" value={draft.renewal_cost} onChange={(e) => setDraft({ ...draft, renewal_cost: e.target.value })} />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label>File link (cloud/Drive)</Label>
                  <Input value={draft.file_link} onChange={(e) => setDraft({ ...draft, file_link: e.target.value })} placeholder="https://…" />
                </div>
                <div className="space-y-1">
                  <Label>Notes</Label>
                  <Input value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
                <Button onClick={handleSave} disabled={!draft.document_name}>{editingId ? 'Save' : 'Add'}</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-border/60">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50 hover:bg-muted/50">
              <TableHead>Document name</TableHead>
              <TableHead>Creation date</TableHead>
              <TableHead>Document ID</TableHead>
              <TableHead>Renewal date</TableHead>
              <TableHead>Renewal cost</TableHead>
              <TableHead>File</TableHead>
              <TableHead>Notes</TableHead>
              {canEdit && <TableHead className="w-20" />}
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.length === 0 ? (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={canEdit ? 8 : 7} className="py-8">
                  <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
                    <FileText className="h-5 w-5 opacity-60" />
                    No documents recorded for this stage.
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              entries.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="font-medium">{e.document_name}</TableCell>
                  <TableCell className="text-muted-foreground">{e.creation_date || '—'}</TableCell>
                  <TableCell className="text-muted-foreground">{e.document_id || '—'}</TableCell>
                  <TableCell className="text-muted-foreground">{e.renewal_date || '—'}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {e.renewal_cost != null ? e.renewal_cost.toLocaleString(undefined, { style: 'currency', currency: 'USD' }) : '—'}
                  </TableCell>
                  <TableCell>
                    {e.file_link ? (
                      <a href={e.file_link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline">
                        Open <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    ) : <span className="text-muted-foreground">—</span>}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{e.notes || '—'}</TableCell>
                  {canEdit && (
                    <TableCell>
                      <div className="flex items-center gap-0.5">
                        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => openEdit(e)} aria-label="Edit">
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => dispatch(deleteDocument({ engagementId, entryId: e.id }))} aria-label="Delete">
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
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
