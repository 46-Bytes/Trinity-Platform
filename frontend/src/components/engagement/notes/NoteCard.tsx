import { Pin, User, Calendar, Trash2 } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn, capitalizeFirstLetter } from '@/lib/utils';
import type { Note, NoteType } from '@/store/slices/notesReducer';

export function formatNoteDate(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatNoteDateShort(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export const NOTE_TYPES: { value: NoteType; label: string }[] = [
  { value: 'general', label: 'General' },
  { value: 'follow_up', label: 'Follow-up' },
  { value: 'issue', label: 'Issue' },
  { value: 'decision', label: 'Decision' },
];

const NOTE_TYPE_META: Record<string, { label: string; pill: string; dot: string }> = {
  general: { label: 'General', pill: 'bg-gray-100 text-gray-700 dark:bg-gray-800/60 dark:text-gray-300', dot: 'bg-gray-400' },
  follow_up: { label: 'Follow-up', pill: 'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300', dot: 'bg-blue-500' },
  issue: { label: 'Issue', pill: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300', dot: 'bg-red-500' },
  decision: { label: 'Decision', pill: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300', dot: 'bg-amber-500' },
};

export function getNoteTypeMeta(type: string) {
  return NOTE_TYPE_META[type] ?? {
    label: capitalizeFirstLetter(type),
    pill: 'bg-gray-100 text-gray-700 dark:bg-gray-800/60 dark:text-gray-300',
    dot: 'bg-gray-400',
  };
}

export function noteTypeDotColor(type: string) {
  return getNoteTypeMeta(type).dot;
}

export function NoteTypeIndicator({ noteType, className }: { noteType: string; className?: string }) {
  const meta = getNoteTypeMeta(noteType);
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', meta.pill, className)}>
      {meta.label}
    </span>
  );
}

interface NoteCardProps {
  note: Note;
  selected?: boolean;
  onClick?: () => void;
  onDelete?: () => void;
  unread?: boolean;
}

export function NoteCard({ note, selected, onClick, onDelete, unread }: NoteCardProps) {
  return (
    <Card
      onClick={onClick}
      className={cn(
        'transition-colors',
        onClick && 'cursor-pointer hover:bg-muted/40',
        note.isPinned && 'border-primary',
        unread && 'bg-muted/60',
        selected && 'bg-muted border-primary',
      )}
    >
      <CardContent className="space-y-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm leading-relaxed flex-1 min-w-0 break-words line-clamp-4">
            {note.content}
          </p>
          {onDelete && (
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              className="text-destructive hover:text-destructive hover:bg-destructive/10 flex-shrink-0 -mt-1 -mr-1"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground flex-wrap">
          {note.isPinned && <Pin className="h-3 w-3 text-primary flex-shrink-0" />}
          <NoteTypeIndicator noteType={note.noteType} />
          {note.authorName && (
            <span className="flex items-center gap-1">
              <User className="h-3 w-3" />
              {note.authorName}
            </span>
          )}
          <span className="flex items-center gap-1">
            <Calendar className="h-3 w-3" />
            {formatNoteDate(note.createdAt)}
          </span>
        </div>
        {note.tags && note.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {note.tags.map((tag, i) => (
              <Badge key={i} variant="outline" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface NoteListRowProps {
  note: Note;
  selected?: boolean;
  onClick?: () => void;
}

export function NoteListRow({ note, selected, onClick }: NoteListRowProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full text-left rounded-lg px-3 py-2.5 transition-colors',
        selected ? 'bg-card shadow-sm' : 'hover:bg-black/5 dark:hover:bg-white/5',
      )}
    >
      <p className="text-sm font-medium text-foreground line-clamp-1 break-words">{note.content}</p>
      <div className="flex items-center gap-2 mt-1.5">
        {note.isPinned && <Pin className="h-3 w-3 text-primary flex-shrink-0" />}
        <NoteTypeIndicator noteType={note.noteType} />
        <span className="text-xs text-muted-foreground">{formatNoteDateShort(note.createdAt)}</span>
      </div>
    </button>
  );
}
