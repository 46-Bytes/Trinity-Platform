import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Edit, Trash2, CheckCircle2, Clock, AlertCircle, XCircle, StickyNote } from 'lucide-react';
import type { Task } from '@/store/slices/tasksReducer';
import { NoteForm } from './NoteForm';
import { NotesList } from './NotesList';
import { useAppDispatch } from '@/store/hooks';
import { createNote, fetchNotes } from '@/store/slices/notesReducer';

interface TaskItemProps {
  task: Task;
  onEdit: () => void;
  onDelete: () => void;
  onStatusChange: (status: string) => void;
  onClick: () => void;
}

export function TaskItem({ task, onEdit, onDelete, onStatusChange, onClick }: TaskItemProps) {
  const dispatch = useAppDispatch();
  const [isNoteDialogOpen, setIsNoteDialogOpen] = useState(false);
  const [showNoteForm, setShowNoteForm] = useState(false);

  const handleCreateNote = async (noteData: any) => {
    try {
      await dispatch(createNote({
        ...noteData,
        engagementId: task.engagementId,
        taskId: task.id,
      })).unwrap();
      // Refetch notes after creation
      await dispatch(fetchNotes({ engagementId: task.engagementId, taskId: task.id }));
      setShowNoteForm(false);
    } catch (error) {
      console.error('Failed to create note:', error);
    }
  };

  const handleOpenNotesDialog = () => {
    setIsNoteDialogOpen(true);
    setShowNoteForm(false);
    // Fetch notes when dialog opens
    dispatch(fetchNotes({ engagementId: task.engagementId, taskId: task.id }));
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case 'completed':
        return 'default';
      case 'in_progress':
        return 'secondary';
      case 'cancelled':
        return 'destructive';
      default:
        return 'outline';
    }
  };

  const getPriorityBadgeVariant = (priority: string) => {
    switch (priority) {
      case 'urgent':
        return 'destructive';
      case 'high':
        return 'default';
      case 'medium':
        return 'secondary';
      default:
        return 'outline';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle2 className="h-4 w-4" />;
      case 'in_progress':
        return <Clock className="h-4 w-4" />;
      case 'cancelled':
        return <XCircle className="h-4 w-4" />;
      default:
        return <AlertCircle className="h-4 w-4" />;
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return null;
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const capitalizeFirstLetter = (str: string) => {
    if (!str) return str;
    return str
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
      .join(' ');
  };

  const isOverdue = task.dueDate && new Date(task.dueDate) < new Date() && task.status !== 'completed';

  return (
    <Card 
      className={`hover:shadow-md transition-shadow cursor-pointer ${isOverdue ? 'border-destructive' : ''}`}
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 space-y-2">
            <div className="flex items-start gap-3">
              <div className="mt-1">{getStatusIcon(task.status)}</div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="font-semibold text-lg">{task.title}</h3>
                  <Badge variant={getStatusBadgeVariant(task.status)}>{capitalizeFirstLetter(task.status)}</Badge>
                  <Badge variant={getPriorityBadgeVariant(task.priority)}>{capitalizeFirstLetter(task.priority)}</Badge>
                </div>
                {task.description && (
                  <p className="text-sm text-muted-foreground mb-2 line-clamp-2">{task.description}</p>
                )}
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  {task.assignedToName && (
                    <span>Assigned to: {task.assignedToName}</span>
                  )}
                  {task.createdByName && (
                    <span>Created by: {task.createdByName}</span>
                  )}
                  {task.dueDate && (
                    <span className={isOverdue ? 'text-destructive font-semibold' : ''}>
                      Due: {formatDate(task.dueDate)}
                      {isOverdue && ' (Overdue)'}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleOpenNotesDialog}
              title="View notes"
            >
              <StickyNote className="h-4 w-4" />
            </Button>
            {task.status !== 'completed' && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onStatusChange('completed')}
                title="Mark as completed"
              >
                <CheckCircle2 className="h-4 w-4" />
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); onEdit(); }} title="Edit task">
              <Edit className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); onDelete(); }} title="Delete task" className="text-destructive hover:text-destructive">
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>

      {/* Notes Dialog */}
      <Dialog open={isNoteDialogOpen} onOpenChange={setIsNoteDialogOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh]">
          <DialogHeader>
            <DialogTitle>Notes for Task: {task.title}</DialogTitle>
          </DialogHeader>
          {showNoteForm ? (
            <NoteForm
              engagementId={task.engagementId}
              taskId={task.id}
              onSubmit={handleCreateNote}
              onCancel={() => setShowNoteForm(false)}
            />
          ) : (
            <NotesList
              engagementId={task.engagementId}
              taskId={task.id}
              onAddNote={() => setShowNoteForm(true)}
            />
          )}
        </DialogContent>
      </Dialog>
    </Card>
  );
}

