import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import type { SettableEngagementStatus } from '@/store/slices/engagementReducer';

interface EngagementStatusDialogProps {
  open: boolean;
  target: SettableEngagementStatus | null;
  title?: string | null;
  isSaving: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

const COPY: Record<
  SettableEngagementStatus,
  { heading: string; body: string; confirm: string; busy: string; destructive: boolean }
> = {
  paused: {
    heading: 'Pause Engagement',
    body:
      'Its tasks will be hidden from the Tasks views. Nothing is deleted — the engagement and all of its data stay intact, and the tasks come back when you recommence it.',
    confirm: 'Pause Engagement',
    busy: 'Pausing...',
    destructive: false,
  },
  ended: {
    heading: 'End Engagement',
    body:
      'Its tasks will be hidden from the Tasks views. Nothing is deleted — the engagement and all of its data stay intact, and it can be recommenced at any time.',
    confirm: 'End Engagement',
    busy: 'Ending...',
    destructive: true,
  },
  active: {
    heading: 'Recommence Engagement',
    body:
      'The engagement will become active again and its tasks will reappear in the Tasks views.',
    confirm: 'Recommence',
    busy: 'Recommencing...',
    destructive: false,
  },
};

export function EngagementStatusDialog({
  open,
  target,
  title,
  isSaving,
  onCancel,
  onConfirm,
}: EngagementStatusDialogProps) {
  if (!target) return null;
  const copy = COPY[target];

  return (
    <Dialog open={open} onOpenChange={() => !isSaving && onCancel()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{copy.heading}</DialogTitle>
          <DialogDescription>
            <span className="font-semibold">{title || 'This engagement'}</span> — {copy.body}
          </DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-2 pt-4">
          <Button type="button" variant="outline" onClick={onCancel} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            type="button"
            variant={copy.destructive ? 'destructive' : 'default'}
            onClick={onConfirm}
            disabled={isSaving}
          >
            {isSaving ? copy.busy : copy.confirm}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
