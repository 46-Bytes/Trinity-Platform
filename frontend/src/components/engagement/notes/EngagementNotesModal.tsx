import { useEffect, useMemo, useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  fetchEngagementNotes,
  clearEngagementNotes,
  createNote,
  updateNote,
  deleteNote,
  type Note,
  type NoteCreatePayload,
  type NoteType,
  type NoteUpdatePayload,
} from '@/store/slices/notesReducer';
import { NoteForm } from '@/components/engagement/tasks/NoteForm';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { NoteListRow, NoteTypeIndicator, formatNoteDate } from '@/components/engagement/notes/NoteCard';
import { Trash2, Search, Plus, ArrowLeft, Pencil } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { toast } from 'sonner';
import { cn, getInitials } from '@/lib/utils';

interface EngagementNotesModalProps {
  engagementId: string;
  engagementName?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

type PanelMode = 'view' | 'add' | 'edit';

function truncateContent(content: string, max = 60) {
  const trimmed = content.trim();
  return trimmed.length > max ? `${trimmed.slice(0, max).trim()}…` : trimmed;
}

export function EngagementNotesModal({ engagementId, engagementName, open, onOpenChange }: EngagementNotesModalProps) {
  const dispatch = useAppDispatch();
  const { engagementNotes, isLoadingEngagementNotes } = useAppSelector((state) => state.note);
  const { user } = useAuth();
  const [mode, setMode] = useState<PanelMode>('view');
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Note | null>(null);
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (open) {
      dispatch(fetchEngagementNotes({ engagementId }));
    } else {
      dispatch(clearEngagementNotes());
      setMode('view');
      setSelectedNoteId(null);
      setDeleteTarget(null);
      setMobileDetailOpen(false);
      setSearchQuery('');
    }
  }, [open, engagementId, dispatch]);

  const sortedNotes = useMemo(
    () => [...engagementNotes].sort((a: Note, b: Note) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()),
    [engagementNotes],
  );

  const filteredNotes = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return sortedNotes;
    return sortedNotes.filter((note) => note.content.toLowerCase().includes(query));
  }, [sortedNotes, searchQuery]);

  // Keep the right pane populated: auto-select the most recent note whenever
  // there's no active selection (initial open, or after the selected note was deleted).
  useEffect(() => {
    if (mode === 'view' && !selectedNoteId && sortedNotes.length > 0) {
      setSelectedNoteId(sortedNotes[0].id);
    }
  }, [mode, selectedNoteId, sortedNotes]);

  const selectedNote = useMemo(
    () => sortedNotes.find((n) => n.id === selectedNoteId) ?? null,
    [sortedNotes, selectedNoteId],
  );

  const goBack = () => {
    setMode('view');
    setMobileDetailOpen(false);
  };

  const selectNote = (noteId: string) => {
    setSelectedNoteId(noteId);
    setMode('view');
    setMobileDetailOpen(true);
  };

  const startAdd = () => {
    setMode('add');
    setMobileDetailOpen(true);
  };

  const handleCreateNote = async (data: NoteCreatePayload) => {
    try {
      const created = await dispatch(createNote({ ...data, engagementId, taskId: undefined })).unwrap();
      dispatch(fetchEngagementNotes({ engagementId }));
      setSelectedNoteId(created.id);
      setMode('view');
      toast.success('Note created');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create note');
    }
  };

  const handleUpdateNote = async (data: NoteCreatePayload) => {
    if (!selectedNote) return;
    try {
      const updates: NoteUpdatePayload = {
        content: data.content,
        noteType: data.noteType,
      };
      const updated = await dispatch(updateNote({ id: selectedNote.id, updates })).unwrap();
      dispatch(fetchEngagementNotes({ engagementId }));
      setSelectedNoteId(updated.id);
      setMode('view');
      toast.success('Note updated');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update note');
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    try {
      await dispatch(deleteNote(deleteTarget.id)).unwrap();
      dispatch(fetchEngagementNotes({ engagementId }));
      if (selectedNoteId === deleteTarget.id) {
        setSelectedNoteId(null);
        setMode('view');
      }
      toast.success('Note deleted');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to delete note');
    } finally {
      setDeleteTarget(null);
    }
  };

  const canEditOrDelete = (note: Note) => {
    if (!user) return false;
    const isAuthor = note.authorId === user.id;
    const isAdminRole = ['admin', 'super_admin', 'firm_admin'].includes(user.role);
    const isAdvisorRole = ['advisor', 'firm_advisor'].includes(user.role);
    return isAuthor || isAdminRole || isAdvisorRole;
  };

  const renderRightPane = () => {
    if (mode === 'add' || mode === 'edit') {
      return (
        <ScrollArea className="flex-1">
          <div className="p-6">
            <NoteForm
              engagementId={engagementId}
              initialValues={
                mode === 'edit' && selectedNote
                  ? { content: selectedNote.content, noteType: selectedNote.noteType as NoteType }
                  : undefined
              }
              isEditing={mode === 'edit'}
              onSubmit={mode === 'edit' ? handleUpdateNote : handleCreateNote}
              onCancel={goBack}
              variant="minimal"
            />
          </div>
        </ScrollArea>
      );
    }

    if (!selectedNote) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center p-6">
          <div className="bg-muted rounded-xl p-3">
            <Pencil className="h-5 w-5 text-muted-foreground" />
          </div>
          <p className="text-muted-foreground text-sm">Select a note or create one</p>
          <Button
            size="sm"
            onClick={startAdd}
            className="rounded-full bg-success text-success-foreground hover:bg-success/90"
          >
            <Plus className="h-4 w-4 mr-1" />
            New note
          </Button>
        </div>
      );
    }

    const canAct = canEditOrDelete(selectedNote);
    return (
      <>
        <ScrollArea className="flex-1">
          <div className="p-6">
            <div className="flex items-center justify-between gap-2 mb-4">
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={goBack}
                  className="md:hidden -ml-2 text-muted-foreground"
                >
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <NoteTypeIndicator noteType={selectedNote.noteType} />
                <span className="text-xs text-muted-foreground">{formatNoteDate(selectedNote.createdAt)}</span>
              </div>
              {canAct && (
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setMode('edit')}
                    className="text-muted-foreground hover:text-success hover:bg-success/10"
                  >
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setDeleteTarget(selectedNote)}
                    className="text-destructive hover:text-destructive hover:bg-destructive/10"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
            <p className="text-sm whitespace-pre-wrap break-words leading-relaxed">{selectedNote.content}</p>
            {selectedNote.tags && selectedNote.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-4">
                {selectedNote.tags.map((tag, i) => (
                  <Badge key={i} variant="outline" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </ScrollArea>
        <div className="border-t px-6 py-3 flex items-center gap-2 flex-shrink-0">
          <Avatar className="h-7 w-7">
            <AvatarFallback className="text-xs bg-success/15 text-success">
              {getInitials(selectedNote.authorName)}
            </AvatarFallback>
          </Avatar>
          <span className="text-sm text-muted-foreground">{selectedNote.authorName || 'Unknown'}</span>
        </div>
      </>
    );
  };

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-w-4xl h-[80vh] p-0 gap-0 flex flex-col">
          <DialogHeader className="pl-6 pr-12 py-4 border-b flex-shrink-0">
            <DialogTitle>{engagementName ? `${engagementName} Notes` : 'Engagement Notes'}</DialogTitle>
          </DialogHeader>

          <div className="flex flex-1 overflow-hidden">
            <div
              className={cn(
                'w-full md:w-[320px] md:border-r bg-muted/40 flex-shrink-0 flex-col overflow-hidden',
                mobileDetailOpen ? 'hidden md:flex' : 'flex',
              )}
            >
              <div className="p-3 pb-2 flex-shrink-0">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search notes..."
                    className="pl-9 h-9 bg-background"
                  />
                </div>
              </div>
              <div className="flex items-center justify-between px-3 pb-2 flex-shrink-0">
                <span className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                </span>
                <button
                  type="button"
                  onClick={startAdd}
                  className="inline-flex items-center gap-1 text-sm font-medium text-success hover:text-success/80"
                >
                  <Plus className="h-3.5 w-3.5" />
                  New
                </button>
              </div>
              <ScrollArea className="flex-1">
                <div className="px-2 pb-3 space-y-0.5">
                  {isLoadingEngagementNotes ? (
                    <p className="text-xs text-muted-foreground text-center py-6">Loading notes...</p>
                  ) : filteredNotes.length === 0 ? (
                    <p className="text-xs text-muted-foreground text-center py-6">
                      {sortedNotes.length === 0 ? 'No notes yet' : 'No matching notes'}
                    </p>
                  ) : (
                    filteredNotes.map((note) => (
                      <NoteListRow
                        key={note.id}
                        note={note}
                        selected={mode === 'view' && note.id === selectedNoteId}
                        onClick={() => selectNote(note.id)}
                      />
                    ))
                  )}
                </div>
              </ScrollArea>
            </div>

            <div
              className={cn(
                'flex-1 min-w-0 flex-col overflow-hidden bg-background',
                mobileDetailOpen ? 'flex' : 'hidden md:flex',
              )}
            >
              {renderRightPane()}
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => { if (!o) setDeleteTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Note</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this note
              {deleteTarget ? `: "${truncateContent(deleteTarget.content)}"` : ''}? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteConfirm}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
