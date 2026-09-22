import { useEffect, useState, type ReactNode } from 'react';
import { ArrowLeft, Pencil } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { DDHeaderRow, DDItemRow } from './DDItemRow';
import { RUN_WITH, STAGE_GUIDES } from './saleReadyGuide';
import { STATUS_CONFIG } from './saleReadyDisplay';
import type { DDItem, DDItemUpdate, SaleReadyPerson, StageDetail, StageTask, StageTaskUpdate, StageUpdate } from './types';

const NONE = '__none__';

interface StageDetailViewProps {
  detail: StageDetail;
  modulesTotal: number;
  isSaving: boolean;
  onBack: () => void;
  onStart: () => void;
  onComplete: () => void;
  onReopen: () => void;
  onUpdateStage: (changes: StageUpdate) => void;
  onAddTask: (title: string) => void;
  onUpdateTask: (taskId: string, changes: StageTaskUpdate) => void;
  onUpdateDD: (item: DDItem, changes: DDItemUpdate) => void;
  /** The Sale Planner or Close-out screen, for stages with their own. */
  variantPanel?: ReactNode;
}

function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cn('card-trinity p-4 sm:p-6', className)}>{children}</section>;
}

/** A date input that saves on blur, not on every keystroke while a year is typed. */
function DateField({
  value,
  onCommit,
  className,
  label,
}: {
  value: string | null;
  onCommit: (value: string | null) => void;
  className?: string;
  label?: string;
}) {
  const [draft, setDraft] = useState(value ?? '');
  useEffect(() => setDraft(value ?? ''), [value]);
  return (
    <Input
      type="date"
      aria-label={label}
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => draft !== (value ?? '') && onCommit(draft || null)}
      className={className}
    />
  );
}

function formatUpdated(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleString('en-AU', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });
}

// ---------------------------------------------------------------- tasks
/**
 * The mockup's task box: clear -> done -> not required -> blocked -> clear.
 *
 * Only "done" touches `status`; N/A and blocked are Sale Ready's own marks, so
 * the shared Tasks views keep seeing an ordinary pending task.
 */
const TASK_CYCLE: { key: string; next: StageTaskUpdate; label: string; mark: string; className: string }[] = [
  { key: 'clear', next: { status: 'completed', sale_ready_state: null }, label: 'Not done', mark: '', className: 'border-border' },
  { key: 'done', next: { status: 'pending', sale_ready_state: 'not_applicable' }, label: 'Done', mark: '✓', className: 'border-success bg-success text-success-foreground' },
  { key: 'not_applicable', next: { status: 'pending', sale_ready_state: 'blocked' }, label: 'Not required', mark: '–', className: 'border-muted-foreground/40 bg-muted-foreground/40 text-white' },
  { key: 'blocked', next: { status: 'pending', sale_ready_state: null }, label: 'Blocked', mark: '!', className: 'border-destructive bg-destructive text-destructive-foreground' },
];

/** Resolved as the server counts it: done or not required. Blocked stays open. */
function isTaskResolved(task: StageTask): boolean {
  return (
    task.sale_ready_state !== 'blocked' &&
    (task.status === 'completed' || task.sale_ready_state === 'not_applicable')
  );
}

function taskStateKey(task: StageTask): string {
  if (task.sale_ready_state) return task.sale_ready_state;
  return task.status === 'completed' ? 'done' : 'clear';
}

function TaskStateBox({ task, onUpdate }: { task: StageTask; onUpdate: (changes: StageTaskUpdate) => void }) {
  const current = TASK_CYCLE.find((s) => s.key === taskStateKey(task)) ?? TASK_CYCLE[0];
  const next = TASK_CYCLE[(TASK_CYCLE.indexOf(current) + 1) % TASK_CYCLE.length];
  return (
    <button
      type="button"
      onClick={() => onUpdate(current.next)}
      aria-label={`${task.title}: ${current.label}. Click to mark ${next.label.toLowerCase()}`}
      title={`${current.label} - click to mark ${next.label.toLowerCase()}`}
      className={cn(
        'mt-0.5 grid h-[19px] w-[19px] place-items-center rounded-[5px] border-2 text-[10px] font-bold leading-none transition-colors',
        current.className
      )}
    >
      {current.mark}
    </button>
  );
}

function TaskRow({
  task,
  people,
  onUpdate,
}: {
  task: StageTask;
  people: SaleReadyPerson[];
  onUpdate: (changes: StageTaskUpdate) => void;
}) {
  const [open, setOpen] = useState(false);
  const [notes, setNotes] = useState(task.notes ?? '');
  useEffect(() => setNotes(task.notes ?? ''), [task.notes]);
  const done = task.status === 'completed';
  const state = task.sale_ready_state;
  const otherStatus = !done && !state && task.status !== 'pending' ? task.status.replace('_', ' ') : null;

  return (
    <div className="border-b border-border/60 py-2.5 last:border-b-0">
      <div className="grid grid-cols-[1.5rem_1fr] gap-x-3 gap-y-2 md:grid-cols-[1.5rem_1fr_9rem_8.5rem_2rem] md:items-start">
        <TaskStateBox task={task} onUpdate={onUpdate} />
        <div className="min-w-0">
          <p
            className={cn(
              'text-sm font-medium leading-snug',
              done && 'text-muted-foreground line-through',
              state === 'not_applicable' && 'text-muted-foreground',
              state === 'blocked' && 'text-destructive'
            )}
          >
            {task.title}
          </p>
          {state === 'not_applicable' && <p className="mt-0.5 text-xs text-muted-foreground">Marked not required</p>}
          {state === 'blocked' && <p className="mt-0.5 text-xs text-destructive">Blocked</p>}
          {otherStatus && <p className="mt-0.5 text-xs capitalize text-muted-foreground">{otherStatus}</p>}
        </div>
        <div className="col-start-2 grid grid-cols-[1fr_1fr_2rem] gap-2 md:col-start-auto md:contents">
          <Select
            value={task.assigned_to_user_id ?? NONE}
            onValueChange={(v) => onUpdate({ assigned_to_user_id: v === NONE ? null : v })}
          >
            <SelectTrigger aria-label="Responsible" className="h-8 text-xs">
              <SelectValue placeholder="Responsible" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>Unassigned</SelectItem>
              {people.map((p) => (
                <SelectItem key={p.id} value={p.id}>
                  {p.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <DateField
            label="Due date"
            value={task.due_date}
            onCommit={(v) => onUpdate({ due_date: v })}
            className="h-8 text-xs"
          />
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-label="Notes"
            aria-expanded={open}
            className={cn('grid h-8 w-8 place-items-center rounded-md', task.notes ? 'text-success' : 'text-muted-foreground/50')}
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      {open && (
        <Textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={() => notes !== (task.notes ?? '') && onUpdate({ notes })}
          placeholder="Notes"
          className="ml-9 mt-2 min-h-[44px] w-[calc(100%-2.25rem)] text-xs"
        />
      )}
    </div>
  );
}

function sectionGroups(detail: StageDetail): { key: string; label: string; must: boolean; tasks: StageTask[] }[] {
  const isModule = detail.stage.stage_type === 'module';
  const byKey = new Map<string, { key: string; label: string; must: boolean; tasks: StageTask[] }>();
  for (const task of detail.tasks) {
    // Phases group must-do tasks under their template heading, as in the mockup.
    const heading =
      task.section === 'must_do'
        ? isModule || !task.group_title
          ? 'Must-do · QA required'
          : task.group_title
        : task.section === 'optional'
          ? 'Optional / enhancements'
          : 'Client-specific · added by advisor or AI';
    const key = `${task.section}:${heading}`;
    if (!byKey.has(key)) byKey.set(key, { key, label: heading, must: task.section === 'must_do', tasks: [] });
    byKey.get(key)!.tasks.push(task);
  }
  if (isModule && ![...byKey.values()].some((g) => g.key.startsWith('client_specific'))) {
    byKey.set('client_specific', {
      key: 'client_specific',
      label: 'Client-specific · added by advisor or AI',
      must: false,
      tasks: [],
    });
  }
  return [...byKey.values()];
}

function TasksCard({
  detail,
  isSaving,
  onStart,
  onAddTask,
  onUpdateTask,
}: Pick<StageDetailViewProps, 'detail' | 'isSaving' | 'onStart' | 'onAddTask' | 'onUpdateTask'>) {
  const [title, setTitle] = useState('');
  const { stage } = detail;

  if (!stage.tasks_created) {
    const count = detail.template_preview.length;
    return (
      <Card>
        <h2 className="mb-3 font-heading text-base font-semibold">Tasks</h2>
        <div className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          {count} tasks are ready for this module. They are created in the Tasks system when you start it, so the
          task list only carries live work.
          <div>
            <Button className="mt-4" disabled={isSaving} onClick={onStart}>
              Start and create {count} tasks
            </Button>
          </div>
        </div>
        <ul className="mt-4 space-y-1.5 opacity-60">
          {detail.template_preview.map((t, i) => (
            <li key={i} className="text-sm">
              <span className="mr-2 text-xs font-semibold text-muted-foreground">
                {t.section === 'must_do' ? 'Must-do' : 'Optional'}
              </span>
              {t.title}
            </li>
          ))}
        </ul>
      </Card>
    );
  }

  const groups = sectionGroups(detail);
  if (groups.length === 0) return null;

  return (
    <Card>
      <h2 className="font-heading text-base font-semibold">Tasks</h2>
      <p className="mb-4 mt-1 text-xs text-muted-foreground">
        What the advisor and client do. Live in the Tasks system, grouped here. Only must-do tasks gate completion.
      </p>
      {groups.map((group) => {
        const done = group.tasks.filter(isTaskResolved).length;
        return (
          <div key={group.key} className="mb-4">
            <div
              className={cn(
                'flex items-center justify-between border-b border-border pb-1.5 text-xs font-bold',
                group.must ? 'text-warning' : 'text-muted-foreground'
              )}
            >
              {group.label}
              <span className="font-medium">
                {done}/{group.tasks.length}
              </span>
            </div>
            {group.tasks.map((task) => (
              <TaskRow
                key={task.id}
                task={task}
                people={detail.people}
                onUpdate={(changes) => onUpdateTask(task.id, changes)}
              />
            ))}
            {group.key.startsWith('client_specific') && (
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && title.trim()) {
                    onAddTask(title.trim());
                    setTitle('');
                  }
                }}
                disabled={isSaving}
                placeholder="Add a client-specific task, then press Enter"
                className="mt-2.5 border-dashed text-sm"
              />
            )}
          </div>
        );
      })}

      <div className="mt-1 flex flex-wrap gap-4 text-xs text-muted-foreground">
        {[
          { label: 'Done', className: 'bg-success' },
          { label: 'Not required / N/A', className: 'bg-muted-foreground/40' },
          { label: 'Blocked', className: 'bg-destructive' },
        ].map((item) => (
          <span key={item.label} className="flex items-center gap-1.5">
            <i className={cn('inline-block h-[11px] w-[11px] rounded-[3px]', item.className)} aria-hidden />
            {item.label}
          </span>
        ))}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------- DD
function DDCard({ detail, onUpdateDD }: Pick<StageDetailViewProps, 'detail' | 'onUpdateDD'>) {
  const items = detail.dd_items;
  const flagged = detail.flagged_for_review;
  if (items.length === 0 && flagged.length === 0) return null;
  const subItems = [...new Set(items.map((i) => `${i.sub_item_code} ${i.sub_item ?? ''}`.trim()))];

  return (
    <Card>
      <h2 className="font-heading text-base font-semibold">Due diligence items</h2>
      <p className="mb-4 mt-1 text-xs text-muted-foreground">
        What a buyer will ask to see. {items.filter((i) => i.status === 'yes').length} of {items.length} complete.
        Changes here show in the master checklist, and the reverse.
      </p>
      {flagged.length > 0 && (
        <div className="mb-4 rounded-xl bg-warning/10 px-4 py-3">
          <h3 className="mb-1.5 text-sm font-bold text-warning">Flagged for review at this module</h3>
          <ul className="space-y-1 text-sm">
            {flagged.map((f) => (
              <li key={f.id}>
                {f.document_required} <span className="text-xs text-muted-foreground">· {f.stage_title}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <DDHeaderRow />
      {subItems.map((sub) => {
        const group = items.filter((i) => `${i.sub_item_code} ${i.sub_item ?? ''}`.trim() === sub);
        return (
          <div key={sub} className="mb-3">
            <h3 className="pb-1 pt-2 text-sm font-bold">
              {sub}
              <span className="ml-2 text-xs font-medium text-muted-foreground">
                {group[0].category_code}. {group[0].category}
              </span>
            </h3>
            {group.map((item) => (
              <DDItemRow key={item.id} item={item} people={detail.people} onChange={(c) => onUpdateDD(item, c)} />
            ))}
          </div>
        );
      })}
    </Card>
  );
}

// ---------------------------------------------------------------- page
export function StageDetailView(props: StageDetailViewProps) {
  const { detail, modulesTotal, isSaving, onBack, onStart, onComplete, onReopen, onUpdateStage, variantPanel } = props;
  const { stage, qa } = detail;
  const status = STATUS_CONFIG[stage.status];
  // The engagement's own frozen copy. The constants are the fallback for
  // engagements created before guide snapshots existed.
  const fallback = STAGE_GUIDES[stage.stage_code];
  const snapshot = detail.guide ?? {};
  const guide = {
    purpose: snapshot.purpose ?? fallback?.purpose ?? '',
    steps: snapshot.steps ?? fallback?.steps ?? [],
    watch: snapshot.watch ?? fallback?.watch ?? [],
    templates: snapshot.templates ?? fallback?.templates ?? [],
  };
  const runWith = snapshot.run_with ?? RUN_WITH[stage.stage_code] ?? null;
  const advisors = detail.people.filter((p) => p.role !== 'client');
  const isModule = stage.stage_type === 'module';
  const needsStart = isModule && !stage.tasks_created;

  const must = detail.tasks.filter((t) => t.section === 'must_do');
  const others = detail.tasks.filter((t) => t.section !== 'must_do');
  const ddYes = detail.dd_items.filter((i) => i.status === 'yes').length;
  const ddBlank = detail.dd_items.filter((i) => !i.status).length;
  const gated = stage.must_do_total > 0 || stage.dd_total > 0;

  return (
    <div className="space-y-5">
      <button type="button" onClick={onBack} className="flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Back to roadmap
      </button>

      <Card>
        <div className="flex flex-wrap items-start gap-3">
          <div className="min-w-[14rem] flex-1">
            <p className="text-xs font-semibold tracking-wide text-muted-foreground">
              {stage.display_code}
              {stage.effective_rank ? ` · Priority ${stage.effective_rank} of ${modulesTotal}` : ''}
            </p>
            <h2 className="mt-1 font-heading text-2xl font-bold">{stage.title}</h2>
          </div>
          <span className={cn('status-badge mt-2', status.badgeClass)}>
            <status.icon className="h-3 w-3" />
            {status.label}
          </span>
          {stage.status === 'completed' ? (
            <Button variant="outline" disabled={isSaving} onClick={onReopen}>
              Reopen
            </Button>
          ) : (
            <>
              {stage.status === 'not_started' && !needsStart && (
                <Button variant="outline" disabled={isSaving} onClick={onStart}>
                  Start
                </Button>
              )}
              <Button disabled={isSaving || needsStart || !qa.passed} onClick={onComplete}>
                Mark complete
              </Button>
            </>
          )}
        </div>

        <div className="mt-5 grid grid-cols-1 gap-4 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs font-semibold text-muted-foreground">
            Start date
            <DateField
              value={stage.start_date}
              onCommit={(v) => onUpdateStage({ start_date: v })}
              className="mt-1.5 h-9 text-sm font-normal text-foreground"
            />
          </label>
          <label className="text-xs font-semibold text-muted-foreground">
            Due date
            <DateField
              value={stage.due_date}
              onCommit={(v) => onUpdateStage({ due_date: v })}
              className="mt-1.5 h-9 text-sm font-normal text-foreground"
            />
          </label>
          <div className="text-xs font-semibold text-muted-foreground">
            Lead advisor
            <Select
              value={detail.lead_advisor_id ?? NONE}
              onValueChange={(v) => onUpdateStage({ lead_advisor_id: v === NONE ? null : v })}
            >
              <SelectTrigger aria-label="Lead advisor" className="mt-1.5 h-9 text-sm font-normal text-foreground">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>Not set</SelectItem>
                {advisors.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="text-xs font-semibold text-muted-foreground">
            Last updated
            <p className="mt-1.5 flex h-9 items-center rounded-md border border-border bg-muted/40 px-3 text-sm font-normal text-muted-foreground">
              {formatUpdated(detail.updated_at)}
            </p>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[1fr_20rem]">
        <div className="min-w-0 space-y-5">
          {guide.purpose && (
            <Card>
              <span className="mb-3 inline-block rounded bg-muted px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                Program guide
              </span>
              <h3 className="mb-2 text-sm font-bold">Purpose</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">{guide.purpose}</p>
              <h3 className="mb-1 mt-5 text-sm font-bold">How it runs</h3>
              <ol>
                {guide.steps.map((step, i) => (
                  <li key={i} className="flex gap-3 border-b border-border/60 py-2 text-sm text-muted-foreground last:border-b-0">
                    <span className="grid h-5 w-5 flex-shrink-0 place-items-center rounded bg-muted text-[11px] font-bold">
                      {i + 1}
                    </span>
                    {step}
                  </li>
                ))}
              </ol>
              {guide.watch.length > 0 && (
                <div className="mt-4 rounded-xl bg-warning/10 px-4 py-3">
                  <h3 className="mb-1.5 text-sm font-bold text-warning">Watch for</h3>
                  <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
                    {guide.watch.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          )}

          <TasksCard {...props} />
          {variantPanel}
          <DDCard {...props} />
        </div>

        <div className="space-y-5 xl:sticky xl:top-5">
          <Card>
            <h2 className="font-heading text-base font-semibold">Status</h2>
            <p className="mb-3 mt-1 text-xs text-muted-foreground">
              Status is derived. Complete needs every must-do task done, and a status on every DD item.
            </p>
            <dl className="text-sm">
              {stage.must_do_total > 0 && (
                <div className="flex justify-between border-b border-border/60 py-2">
                  <dt className="text-muted-foreground">Must-do tasks</dt>
                  <dd className="font-semibold">
                    {stage.must_do_resolved} / {stage.must_do_total}
                  </dd>
                </div>
              )}
              {others.length > 0 && (
                <div className="flex justify-between border-b border-border/60 py-2">
                  <dt className="text-muted-foreground">Optional and custom</dt>
                  <dd className="font-semibold">
                    {others.filter(isTaskResolved).length} / {others.length}
                  </dd>
                </div>
              )}
              {detail.dd_items.length > 0 && (
                <>
                  <div className="flex justify-between border-b border-border/60 py-2">
                    <dt className="text-muted-foreground">DD items complete</dt>
                    <dd className="font-semibold">
                      {ddYes} / {detail.dd_items.length}
                    </dd>
                  </div>
                  <div className="flex justify-between py-2">
                    <dt className="text-muted-foreground">DD items with no status</dt>
                    <dd className={cn('font-semibold', ddBlank > 0 && 'text-warning')}>{ddBlank}</dd>
                  </div>
                </>
              )}
            </dl>
            {stage.status === 'completed' ? (
              <div className="mt-3 rounded-lg border border-success/30 bg-success/10 px-3.5 py-3 text-sm text-success">
                Complete{detail.completed_by_name ? `, marked by ${detail.completed_by_name}` : ''}. QA signed off.
              </div>
            ) : needsStart ? (
              <div className="mt-3 rounded-lg border border-border bg-muted/40 px-3.5 py-3 text-sm text-muted-foreground">
                Start the module to create its {must.length || stage.must_do_total} must-do tasks.
              </div>
            ) : (
              gated && (
                <div
                  className={cn(
                    'mt-3 rounded-lg border px-3.5 py-3 text-sm',
                    qa.passed ? 'border-success/30 bg-success/10 text-success' : 'border-warning/40 bg-warning/10 text-warning'
                  )}
                >
                  {qa.passed
                    ? 'QA check passes. This can be marked complete.'
                    : `${qa.reasons.join('. ')}. Every DD item needs Yes, No, In progress or N/A before this can complete.`}
                </div>
              )
            )}
          </Card>

          {guide.templates.length > 0 && (
            <Card>
              <h2 className="font-heading text-base font-semibold">Templates</h2>
              <p className="mb-2 mt-1 text-xs text-muted-foreground">From the Templates library.</p>
              <ul className="space-y-2 text-sm">
                {guide.templates.map((t) => (
                  <li key={t} className="flex items-center gap-2.5">
                    <span className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-md bg-info/10 text-[10px] font-bold text-info">
                      {t.split(' ').slice(0, 2).map((w) => w[0]).join('').toUpperCase()}
                    </span>
                    {t}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {runWith && (
            <Card>
              <h2 className="font-heading text-base font-semibold">Run with</h2>
              <p className="mt-2 rounded-lg bg-muted/40 px-3.5 py-3 text-xs leading-relaxed text-muted-foreground">
                {runWith}
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
