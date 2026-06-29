import { useEffect, useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  fetchEngagementNotes,
  clearEngagementNotes,
  createNote,
  updateNote,
  deleteNote,
  type Note,
  type NoteCreatePayload,
  type NoteUpdatePayload,
} from '@/store/slices/notesReducer';
import { NoteForm } from '@/components/engagement/tasks/NoteForm';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
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
import { ScrollArea } from '@/components/ui/scroll-area';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Trash2, Pin, User, Calendar, Plus, ArrowLeft, Pencil, Eye } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { toast } from 'sonner';

interface EngagementNotesPanelProps {
  engagementId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function getNoteTypeColor(type: string) {
  switch (type) {
    case 'meeting':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
    case 'observation':
      return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
    case 'decision':
      return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
    case 'progress_update':
      return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200';
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200';
  }
}

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

type PanelView = 'list' | 'add' | 'edit' | 'detail';

export function EngagementNotesPanel({ engagementId, open, onOpenChange }: EngagementNotesPanelProps) {
  const dispatch = useAppDispatch();
  const { engagementNotes, isLoadingEngagementNotes } = useAppSelector((state) => state.note);
  const { user } = useAuth();
  const [view, setView] = useState<PanelView>('list');
  const [activeNote, setActiveNote] = useState<Note | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Note | null>(null);

  useEffect(() => {
    if (open) {
      dispatch(fetchEngagementNotes({ engagementId }));
    } else {
      dispatch(clearEngagementNotes());
      setView('list');
      setActiveNote(null);
      setDeleteTarget(null);
    }
  }, [open, engagementId, dispatch]);

  const goBack = () => {
    setView('list');
    setActiveNote(null);
  };

  const handleCreateNote = async (data: NoteCreatePayload) => {
    try {
      await dispatch(createNote({ ...data, engagementId, taskId: undefined })).unwrap();
      dispatch(fetchEngagementNotes({ engagementId }));
      setView('list');
      toast.success('Note created');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create note');
    }
  };

  const handleUpdateNote = async (data: NoteCreatePayload) => {
    if (!activeNote) return;
    try {
      const updates: NoteUpdatePayload = {
        title: data.title,
        content: data.content,
        noteType: data.noteType,
      };
      await dispatch(updateNote({ id: activeNote.id, updates })).unwrap();
      dispatch(fetchEngagementNotes({ engagementId }));
      setView('list');
      setActiveNote(null);
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
      // If currently viewing the deleted note, go back to list
      if (activeNote?.id === deleteTarget.id) {
        setView('list');
        setActiveNote(null);
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

  const sortedNotes = [...engagementNotes].sort(
    (a: Note, b: Note) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );

  const renderHeader = () => {
    const titles: Record<PanelView, string> = {
      list: 'Engagement Notes',
      add: 'New Note',
      edit: 'Edit Note',
      detail: activeNote?.title || 'Note',
    };
    const descs: Record<PanelView, string> = {
      list: 'Notes for this engagement',
      add: 'Add a new note to this engagement',
      edit: 'Update the note',
      detail: formatDate(activeNote?.createdAt ?? ''),
    };
    return (
      <SheetHeader className="px-6 pt-10 pb-4 border-b">
        <div className="flex items-center justify-between">
          <div>
            <SheetTitle>{titles[view]}</SheetTitle>
            <SheetDescription className="mt-1">{descs[view]}</SheetDescription>
          </div>
          {view === 'list' && (
            <Button
              size="sm"
              className="bg-success text-success-foreground hover:bg-success/90"
              onClick={() => setView('add')}
            >
              <Plus className="h-4 w-4 mr-1" />
              Add Note
            </Button>
          )}
        </div>
      </SheetHeader>
    );
  };

  const renderContent = () => {
    if (view === 'add' || view === 'edit') {
      return (
        <div className="space-y-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={goBack}
            className="flex items-center gap-1 text-muted-foreground -ml-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to notes
          </Button>
          <NoteForm
            engagementId={engagementId}
            initialValues={
              view === 'edit' && activeNote
                ? {
                    title: activeNote.title ?? '',
                    content: activeNote.content,
                    noteType: activeNote.noteType,
                  }
                : undefined
            }
            isEditing={view === 'edit'}
            onSubmit={view === 'edit' ? handleUpdateNote : handleCreateNote}
            onCancel={goBack}
          />
        </div>
      );
    }

    if (view === 'detail' && activeNote) {
      const canAct = canEditOrDelete(activeNote);
      return (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              size="sm"
              onClick={goBack}
              className="flex items-center gap-1 text-muted-foreground -ml-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to notes
            </Button>
            {canAct && (
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setView('edit')}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <Pencil className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setDeleteTarget(activeNote)}
                  className="text-destructive hover:text-destructive"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>

          <div className="space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              {activeNote.isPinned && <Pin className="h-4 w-4 text-primary flex-shrink-0" />}
              <Badge variant="outline" className={getNoteTypeColor(activeNote.noteType)}>
                {activeNote.noteType.replace('_', ' ')}
              </Badge>
            </div>
            <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
              {activeNote.authorName && (
                <span className="flex items-center gap-1">
                  <User className="h-3 w-3" />
                  {activeNote.authorName}
                </span>
              )}
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                {formatDate(activeNote.createdAt)}
              </span>
            </div>
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{activeNote.content}</p>
            {activeNote.tags && activeNote.tags.length > 0 && (
              <div className="flex flex-wrap gap-1 pt-2">
                {activeNote.tags.map((tag, i) => (
                  <Badge key={i} variant="outline" className="text-xs">
                    {tag}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>
      );
    }

    // List view
    if (isLoadingEngagementNotes) {
      return (
        <div className="flex items-center justify-center h-32 text-muted-foreground">
          Loading notes...
        </div>
      );
    }

    if (sortedNotes.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center h-32 border border-dashed rounded-lg gap-2">
          <p className="text-muted-foreground text-sm">No notes yet</p>
          <Button variant="outline" size="sm" onClick={() => setView('add')}>
            Create First Note
          </Button>
        </div>
      );
    }

    return (
      <ScrollArea className="h-full pr-2">
        <div className="space-y-3 pb-4">
          <p className="text-sm text-muted-foreground">
            {sortedNotes.length} note{sortedNotes.length !== 1 ? 's' : ''}
          </p>
          {sortedNotes.map((note: Note) => {
            const canAct = canEditOrDelete(note);

            return (
              <Card
                key={note.id}
                className={`cursor-pointer hover:bg-muted/40 transition-colors ${note.isPinned ? 'border-primary' : ''}`}
                onClick={() => { setActiveNote(note); setView('detail'); }}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        {note.isPinned && <Pin className="h-4 w-4 text-primary flex-shrink-0" />}
                        <CardTitle className="text-base truncate">
                          {note.title || 'Untitled Note'}
                        </CardTitle>
                        <Badge variant="outline" className={getNoteTypeColor(note.noteType)}>
                          {note.noteType.replace('_', ' ')}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
                        {note.authorName && (
                          <span className="flex items-center gap-1">
                            <User className="h-3 w-3" />
                            {note.authorName}
                          </span>
                        )}
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {formatDate(note.createdAt)}
                        </span>
                      </div>
                    </div>

                    <div
                      className="flex items-center gap-1 flex-shrink-0"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => { setActiveNote(note); setView('detail'); }}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <Eye className="h-4 w-4" />
                      </Button>
                      {canAct && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => { setActiveNote(note); setView('edit'); }}
                            className="text-muted-foreground hover:text-foreground"
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeleteTarget(note)}
                            className="text-destructive hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {note.content}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </ScrollArea>
    );
  };

  return (
    <>
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="w-[500px] sm:w-[500px] flex flex-col p-0">
          {renderHeader()}
          <div className="flex-1 overflow-hidden px-6 py-4">
            {renderContent()}
          </div>
        </SheetContent>
      </Sheet>

      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => { if (!o) setDeleteTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Note</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{deleteTarget?.title || 'Untitled Note'}"? This action cannot be undone.
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
