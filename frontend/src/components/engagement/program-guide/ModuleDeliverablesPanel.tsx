import { useState } from 'react';
import { toast } from 'sonner';
import { EyeOff, Eye, Loader2, MoreVertical, Package, Pencil, Plus, Trash2, X } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  addAdvisorDeliverable,
  generateModuleTasks,
  removeAdvisorDeliverable,
  setDeliverableComplete,
  setDeliverableScope,
  updateAdvisorDeliverable,
  type DeliverableItem,
  type ModuleDeliverables,
} from '@/store/slices/deliverablesReducer';
import { SECTION_LABEL_CLASS, STATUS_CONFIG, statusOf } from './moduleDisplay';

interface ModuleDeliverablesPanelProps {
  engagementId: string;
  moduleCode: string;
  moduleDeliverables?: ModuleDeliverables;
}

/**
 * The one part of the Program Guide that writes anything.
 *
 * Three of Part A's rules are visible in the markup rather than only in prose,
 * because a rule that only exists in a document is one an advisor has to be
 * told about:
 *
 * - A preset is never edited or deleted, only scoped out. So preset rows offer
 *   scope, and advisor-added rows offer edit and remove. Attempting otherwise
 *   is refused server-side too; this just does not offer it.
 * - Scoping out is not deletion. The row stays, struck through and dimmed, and
 *   the action reverses.
 * - Ticking a deliverable does not close its task, and closing a task does not
 *   tick the deliverable. Said plainly under the button, because the two sit
 *   inches apart and would otherwise be assumed to be linked.
 *
 * There is no wizard and no save button: every change is its own request, and
 * the response replaces the whole view, so leaving mid-edit loses nothing.
 */
export function ModuleDeliverablesPanel({
  engagementId,
  moduleCode,
  moduleDeliverables,
}: ModuleDeliverablesPanelProps) {
  const dispatch = useAppDispatch();
  const { pendingIds, generatingModules, isLoading, view } = useAppSelector(
    (state) => state.deliverables
  );
  // The guide and the deliverables are fetched in parallel, and the guide
  // usually wins. Without this the panel renders "no deliverables" for the gap
  // between them - which is not just wrong, it is the one message an advisor
  // would act on by adding a deliverable that already exists.
  const stillLoading = isLoading && !view;
  const [isAdding, setIsAdding] = useState(false);
  // A new deliverable has no id yet, so it cannot ride on pendingIds like every
  // other row does. Without its own flag the dialog would accept a second
  // submit, or be dismissed, while the first request is still in the air.
  const [isSubmittingNew, setIsSubmittingNew] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  const items = moduleDeliverables?.deliverables ?? [];
  const status = statusOf(moduleDeliverables?.status);
  const statusConfig = STATUS_CONFIG[status];
  const isGenerating = generatingModules.includes(moduleCode);

  // Only in-scope, incomplete deliverables with no task yet would actually
  // produce anything, so the count on the button is what the click will create -
  // not the number of rows on screen.
  const generatable = items.filter((d) => d.is_in_scope && !d.is_complete && d.task_count === 0);

  const toggleComplete = async (item: DeliverableItem) => {
    try {
      await dispatch(
        setDeliverableComplete({
          engagementId,
          deliverableId: item.deliverable_id,
          isComplete: !item.is_complete,
        })
      ).unwrap();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to update the deliverable');
    }
  };

  const toggleScope = async (item: DeliverableItem) => {
    try {
      await dispatch(
        setDeliverableScope({
          engagementId,
          deliverableId: item.deliverable_id,
          isInScope: !item.is_in_scope,
        })
      ).unwrap();
      toast.success(item.is_in_scope ? 'Deliverable scoped out' : 'Deliverable back in scope');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to change the deliverable scope');
    }
  };

  const remove = async (item: DeliverableItem) => {
    try {
      await dispatch(
        removeAdvisorDeliverable({ engagementId, deliverableId: item.deliverable_id })
      ).unwrap();
      toast.success('Deliverable removed');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to remove the deliverable');
    }
  };

  const createTasks = async () => {
    try {
      const result = await dispatch(generateModuleTasks({ engagementId, moduleCode })).unwrap();
      if (result.created_count === 0) {
        toast.info('Every deliverable in this module already has a task');
      } else {
        toast.success(
          `${result.created_count} ${result.created_count === 1 ? 'task' : 'tasks'} created`
        );
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to create tasks');
    }
  };

  return (
    <div className="card-trinity p-6">
      <div className="mb-1 flex items-center justify-between gap-3">
        <p className={cn(SECTION_LABEL_CLASS, 'mb-0')}>
          <Package className="h-3.5 w-3.5" />
          Deliverables
        </p>
        <span className={cn('status-badge whitespace-nowrap', statusConfig.badgeClass)}>
          <statusConfig.icon className="h-3 w-3" />
          {statusConfig.label}
        </span>
      </div>
      <p className="mb-4 text-xs text-muted-foreground">
        Module status is derived from these. It is never set by hand.
      </p>

      {stillLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-10 w-full" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
          No deliverables for this module yet.
        </p>
      ) : (
        <div className="divide-y divide-border/50">
          {items.map((item) =>
            editingId === item.deliverable_id ? (
              <DeliverableForm
                key={item.deliverable_id}
                initial={item}
                busy={pendingIds.includes(item.deliverable_id)}
                onCancel={() => setEditingId(null)}
                onSubmit={async ({ title, isMandatory, description }) => {
                  try {
                    await dispatch(
                      updateAdvisorDeliverable({
                        engagementId,
                        deliverableId: item.deliverable_id,
                        fields: { title, is_mandatory: isMandatory, description },
                      })
                    ).unwrap();
                    toast.success('Deliverable updated');
                    setEditingId(null);
                  } catch (error) {
                    toast.error(error instanceof Error ? error.message : 'Failed to update the deliverable');
                  }
                }}
              />
            ) : (
              <DeliverableRow
                key={item.deliverable_id}
                item={item}
                busy={pendingIds.includes(item.deliverable_id)}
                onToggleComplete={() => toggleComplete(item)}
                onToggleScope={() => toggleScope(item)}
                onEdit={() => setEditingId(item.deliverable_id)}
                onRemove={() => remove(item)}
              />
            )
          )}
        </div>
      )}

      <div className="mt-4 space-y-3">
        <Button
          variant="outline"
          className="w-full border-accent text-accent hover:bg-accent/10 hover:text-accent"
          disabled={isGenerating || stillLoading || generatable.length === 0}
          onClick={createTasks}
        >
          {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          {generatable.length > 0 ? (
            <>
              Create tasks
              <span className="ml-1 grid h-5 min-w-5 place-items-center rounded-full bg-accent px-1.5 text-[11px] font-semibold text-accent-foreground">
                {generatable.length}
              </span>
            </>
          ) : (
            'Tasks created for every deliverable'
          )}
        </Button>

        <p className="text-xs leading-relaxed text-muted-foreground">
          Nothing is created automatically. Tasks are tracked separately, so ticking a deliverable here does
          not close its task, and closing a task does not tick the deliverable.
        </p>

        {/*
          Adding is a modal rather than an inline form: the panel it would grow
          inside is already dense, and the form sits below a paragraph about
          tasks that has nothing to do with it. Editing stays inline, where the
          row being changed is the context.
        */}
        <Dialog
          open={isAdding}
          onOpenChange={(open) => {
            // Closing mid-request would leave a toast landing on nothing.
            if (isSubmittingNew) return;
            setIsAdding(open);
          }}
        >
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" className="w-full">
              <Plus className="mr-1 h-4 w-4" />
              Add deliverable
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>New deliverable</DialogTitle>
              <DialogDescription>
                Added for this engagement only. It counts towards this module&apos;s status like any
                preset does.
              </DialogDescription>
            </DialogHeader>
            <DeliverableForm
              inDialog
              busy={isSubmittingNew}
              onCancel={() => setIsAdding(false)}
              onSubmit={async ({ title, isMandatory, description }) => {
                setIsSubmittingNew(true);
                try {
                  await dispatch(
                    addAdvisorDeliverable({
                      engagementId,
                      moduleCode,
                      title,
                      isMandatory,
                      description,
                    })
                  ).unwrap();
                  toast.success('Deliverable added');
                  setIsAdding(false);
                } catch (error) {
                  toast.error(error instanceof Error ? error.message : 'Failed to add the deliverable');
                } finally {
                  setIsSubmittingNew(false);
                }
              }}
            />
          </DialogContent>
        </Dialog>

        <p className="rounded-lg bg-muted/50 px-3 py-2.5 text-xs leading-relaxed text-muted-foreground">
          Any deliverable can be completed from anywhere, at any time. A module can reach Complete without
          ever being formally opened.
        </p>
      </div>
    </div>
  );
}

function DeliverableRow({
  item,
  busy,
  onToggleComplete,
  onToggleScope,
  onEdit,
  onRemove,
}: {
  item: DeliverableItem;
  busy: boolean;
  onToggleComplete: () => void;
  onToggleScope: () => void;
  onEdit: () => void;
  onRemove: () => void;
}) {
  const scopedOut = !item.is_in_scope;

  return (
    <div className={cn('flex items-start gap-3 py-3', scopedOut && 'opacity-60')}>
      <Checkbox
        checked={item.is_complete}
        disabled={busy}
        onCheckedChange={onToggleComplete}
        className="mt-0.5 flex-shrink-0"
        aria-label={`Mark ${item.title} ${item.is_complete ? 'incomplete' : 'complete'}`}
      />

      <div className="min-w-0 flex-1">
        <p
          className={cn(
            'text-sm font-medium leading-snug',
            item.is_complete && 'text-muted-foreground line-through'
          )}
        >
          {item.title}
        </p>
        {item.description && (
          <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{item.description}</p>
        )}

        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
          <span className={item.is_mandatory ? 'font-semibold text-warning' : 'text-muted-foreground'}>
            {item.is_mandatory ? 'Required' : 'Optional'}
          </span>

          {item.source === 'advisor' && (
            <Badge variant="secondary" className="rounded-full px-1.5 py-0 text-[10px] font-normal">
              Added for this engagement
            </Badge>
          )}

          {item.task_count > 0 && (
            <Badge
              variant="secondary"
              className="rounded-full bg-info/10 px-1.5 py-0 text-[10px] font-medium text-info hover:bg-info/10"
            >
              {item.task_count === 1 ? 'Task created' : `${item.task_count} tasks`}
            </Badge>
          )}

          {scopedOut && (
            <Badge
              variant="secondary"
              className="rounded-full px-1.5 py-0 text-[10px] font-medium"
              title="Retained on the engagement but excluded from completion"
            >
              Scoped out
            </Badge>
          )}
        </div>
      </div>

      {busy ? (
        <Loader2 className="mt-0.5 h-4 w-4 flex-shrink-0 animate-spin text-muted-foreground" />
      ) : (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 flex-shrink-0 text-muted-foreground"
              aria-label={`Actions for ${item.title}`}
            >
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={onToggleScope}>
              {scopedOut ? (
                <>
                  <Eye className="mr-2 h-4 w-4" />
                  Bring back into scope
                </>
              ) : (
                <>
                  <EyeOff className="mr-2 h-4 w-4" />
                  Scope out
                </>
              )}
            </DropdownMenuItem>

            {/*
              Presets are library content shared by every engagement, so edit
              and remove are simply not offered for them - scoping out is the
              per-engagement way to exclude one.
            */}
            {item.source === 'advisor' && (
              <>
                <DropdownMenuItem onClick={onEdit}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </DropdownMenuItem>
                <DropdownMenuItem onClick={onRemove} className="text-destructive focus:text-destructive">
                  <Trash2 className="mr-2 h-4 w-4" />
                  Remove
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </div>
  );
}

/**
 * Shared by the inline edit row and the add dialog. `inDialog` drops the card
 * chrome and the header, because the dialog already supplies a title and a
 * close button and two of each reads as a bug.
 */
function DeliverableForm({
  initial,
  busy,
  inDialog = false,
  onCancel,
  onSubmit,
}: {
  initial?: DeliverableItem;
  busy: boolean;
  inDialog?: boolean;
  onCancel: () => void;
  onSubmit: (values: { title: string; isMandatory: boolean; description: string | null }) => void;
}) {
  const [title, setTitle] = useState(initial?.title ?? '');
  const [description, setDescription] = useState(initial?.description ?? '');
  const [isMandatory, setIsMandatory] = useState(initial?.is_mandatory ?? true);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = title.trim();
    // The service rejects a blank title with a 400; catching it here keeps a
    // predictable mistake from becoming a round trip and a red toast.
    if (!trimmed) {
      toast.error('A deliverable needs a title');
      return;
    }
    onSubmit({ title: trimmed, isMandatory, description: description.trim() || null });
  };

  return (
    <form
      onSubmit={submit}
      className={cn('space-y-3', !inDialog && 'rounded-lg border border-border bg-muted/30 p-3')}
    >
      {!inDialog && (
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {initial ? 'Edit deliverable' : 'New deliverable'}
          </p>
          <Button type="button" variant="ghost" size="icon" className="h-6 w-6" onClick={onCancel}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      <input
        autoFocus
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder="Title"
        maxLength={255}
        className="input-trinity py-2 text-sm"
      />

      <input
        value={description}
        onChange={(event) => setDescription(event.target.value)}
        placeholder="Description (optional)"
        className="input-trinity py-2 text-sm"
      />

      <label className="flex items-center gap-2 text-sm">
        <Checkbox checked={isMandatory} onCheckedChange={(checked) => setIsMandatory(checked === true)} />
        Required for this module to be complete
      </label>

      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={busy}>
          {busy ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : null}
          {initial ? 'Save' : 'Add'}
        </Button>
      </div>
    </form>
  );
}
