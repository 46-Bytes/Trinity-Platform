import { useEffect, useRef } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchNotes, deleteNote, type Note, markNoteRead } from '@/store/slices/notesReducer';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { NoteCard } from '@/components/engagement/notes/NoteCard';
import { useAuth } from '@/context/AuthContext';

interface NotesListProps {
  engagementId: string;
  taskId: string;
  onAddNote: () => void;
}

export function NotesList({ engagementId, taskId, onAddNote }: NotesListProps) {
  const dispatch = useAppDispatch();
  const { notes, isLoading, error } = useAppSelector((state) => state.note);
  const { user } = useAuth();
  const hasMarkedAllReadRef = useRef(false);

  useEffect(() => {
    // Fetch notes for this task
    dispatch(fetchNotes({ engagementId, taskId }));
  }, [dispatch, engagementId, taskId]);

  useEffect(() => {
    // After notes are loaded, mark them as read for the current user (once per dialog open)
    if (!user) return;
    if (hasMarkedAllReadRef.current) return;
    if (!notes || notes.length === 0) return;

    const unreadNotes = notes.filter((note: Note) => {
      const alreadyRead = Array.isArray(note.readBy) && note.readBy.includes(user.id);
      return !alreadyRead;
    });

    if (unreadNotes.length === 0) {
      hasMarkedAllReadRef.current = true;
      return;
    }

    unreadNotes.forEach((note) => {
      dispatch(markNoteRead(note.id));
    });

    // Avoid re-marking on subsequent state updates for this dialog open
    hasMarkedAllReadRef.current = true;
  }, [dispatch, notes, user]);

  const handleDeleteNote = async (noteId: string) => {
    if (window.confirm('Are you sure you want to delete this note?')) {
      try {
        await dispatch(deleteNote(noteId)).unwrap();
        // Refetch notes after deletion
        dispatch(fetchNotes({ engagementId, taskId }));
      } catch (error) {
        console.error('Failed to delete note:', error);
      }
    }
  };

  // Sort notes: pinned first, then by creation date
  const sortedNotes = [...notes].sort((a, b) => {
    if (a.isPinned && !b.isPinned) return -1;
    if (!a.isPinned && b.isPinned) return 1;
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-muted-foreground">Loading notes...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-8">
        <p className="text-destructive">Error loading notes: {error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Notes ({sortedNotes.length})</h3>
        <Button onClick={onAddNote} size="sm" className="bg-success text-success-foreground hover:bg-success/90">
          Add Note
        </Button>
      </div>

      {sortedNotes.length === 0 ? (
        <div className="text-center py-8 border border-dashed rounded-lg">
          <p className="text-muted-foreground mb-2">No notes yet</p>
          <Button onClick={onAddNote} variant="outline" size="sm">
            Create First Note
          </Button>
        </div>
      ) : (
        <ScrollArea className="h-[400px] pr-4">
          <div className="space-y-3">
            {sortedNotes.map((note) => {
              const isUnreadForCurrentUser =
                !!user && (!note.readBy || !note.readBy.includes(user.id));

              return (
                <NoteCard
                  key={note.id}
                  note={note}
                  unread={isUnreadForCurrentUser}
                  onDelete={() => handleDeleteNote(note.id)}
                />
              );
            })}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}

