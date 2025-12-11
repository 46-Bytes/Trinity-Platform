import { useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchNotes, deleteNote, type Note } from '@/store/slices/notesReducer';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Trash2, Pin, User, Calendar } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

interface NotesListProps {
  engagementId: string;
  taskId: string;
  onAddNote: () => void;
}

export function NotesList({ engagementId, taskId, onAddNote }: NotesListProps) {
  const dispatch = useAppDispatch();
  const { notes, isLoading, error } = useAppSelector((state) => state.note);

  useEffect(() => {
    // Fetch notes for this task
    dispatch(fetchNotes({ engagementId, taskId }));
  }, [dispatch, engagementId, taskId]);

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

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getNoteTypeColor = (type: string) => {
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
        <Button onClick={onAddNote} size="sm">
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
            {sortedNotes.map((note) => (
              <Card key={note.id} className={note.isPinned ? 'border-primary' : ''}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        {note.isPinned && (
                          <Pin className="h-4 w-4 text-primary" />
                        )}
                        <CardTitle className="text-base">
                          {note.title || 'Untitled Note'}
                        </CardTitle>
                        <Badge
                          variant="outline"
                          className={getNoteTypeColor(note.noteType)}
                        >
                          {note.noteType.replace('_', ' ')}
                        </Badge>
                        {note.visibility !== 'all' && (
                          <Badge variant="secondary" className="text-xs">
                            {note.visibility.replace('_', ' ')}
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
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
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDeleteNote(note.id)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="pt-0">
                  <p className="text-sm whitespace-pre-wrap">{note.content}</p>
                  {note.tags && note.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-3">
                      {note.tags.map((tag, index) => (
                        <Badge key={index} variant="outline" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </ScrollArea>
      )}
    </div>
  );
}

