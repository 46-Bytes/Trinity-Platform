import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowDown, ArrowUp, Plus, RotateCcw, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  type AdminDDTemplate,
  type AdminGuide,
  type AdminStage,
  type AdminTaskTemplate,
  type ProgramRule,
  type StageGuide,
  type WorkflowStep,
  createDDTemplate,
  createTaskTemplate,
  fetchAdminGuide,
  fetchDDCategories,
  fetchDDTemplates,
  fetchTaskTemplates,
  reorderDDTemplates,
  reorderTaskTemplates,
  retireDDTemplate,
  retireTaskTemplate,
  updateDDTemplate,
  updateProgramGuide,
  updateStageGuide,
  updateTaskTemplate,
} from '@/store/slices/saleReadyAdminReducer';

/** Master content only. Live engagements keep the copy they were created with. */
const FUTURE_ONLY =
  'Changes here apply to Sale Ready engagements created from now on. Engagements already running keep the content they started with.';

/**
 * Temporarily hides the two program-level editors - "How the Sale Ready program
 * runs" (workflow) and "Program rules" - from the Program Guide tab.
 *
 * UI only. The backend, the API and the stored content are untouched: the
 * workflow and rules are still seeded, still served to the Program guide tab on
 * an engagement, and still frozen into each engagement's snapshot. Set this back
 * to true to bring the two editors back; nothing else needs to change.
 */
const SHOW_PROGRAM_LEVEL_GUIDE = false;

const SECTION_LABEL: Record<string, string> = { must_do: 'Must-do', optional: 'Optional' };

// ----------------------------------------------------------------------
// The draft
//
// Nothing on this page talks to the API until Save Changes is pressed. Every
// edit, add, reorder, remove and restore is applied to a local copy of the
// master content; Save diffs that copy against what the server last gave us and
// submits the difference. The draft therefore has to live above the tabs -
// Radix unmounts an inactive TabsContent, so anything held inside a section
// would be thrown away when the admin switches tab.
// ----------------------------------------------------------------------
const TEMP_PREFIX = 'new:';
const isTemp = (id: string) => id.startsWith(TEMP_PREFIX);
const tempId = () => `${TEMP_PREFIX}${Math.random().toString(36).slice(2)}${Date.now().toString(36)}`;

const taskGroupKey = (t: Pick<AdminTaskTemplate, 'stage_code' | 'section'>) => `${t.stage_code}|${t.section}`;
const ddGroupKey = (d: Pick<AdminDDTemplate, 'category_code' | 'sub_item_code'>) =>
  `${d.category_code}|${d.sub_item_code}`;

interface Draft {
  guide: AdminGuide;
  tasks: AdminTaskTemplate[];
  dd: AdminDDTemplate[];
  /** Groups the admin dragged with the arrows; only these get a reorder request. */
  reorderedTaskGroups: string[];
  reorderedDDGroups: string[];
}

/** The work Save has to do. Empty in every field means nothing is pending. */
interface SavePlan {
  createTasks: AdminTaskTemplate[];
  createDD: AdminDDTemplate[];
  updateTasks: { id: string; changes: Record<string, unknown> }[];
  updateDD: { id: string; changes: Record<string, unknown> }[];
  restoreTasks: string[];
  restoreDD: string[];
  retireTasks: string[];
  retireDD: string[];
  programGuide: { workflow?: WorkflowStep[]; rules?: ProgramRule[] } | null;
  stageGuides: { stageCode: string; changes: Partial<StageGuide> }[];
  reorderTaskGroups: string[];
  reorderDDGroups: string[];
}

const EMPTY_PLAN: SavePlan = {
  createTasks: [], createDD: [], updateTasks: [], updateDD: [],
  restoreTasks: [], restoreDD: [], retireTasks: [], retireDD: [],
  programGuide: null, stageGuides: [], reorderTaskGroups: [], reorderDDGroups: [],
};

const planSize = (p: SavePlan) =>
  p.createTasks.length + p.createDD.length + p.updateTasks.length + p.updateDD.length +
  p.restoreTasks.length + p.restoreDD.length + p.retireTasks.length + p.retireDD.length +
  (p.programGuide ? 1 : 0) + p.stageGuides.length + p.reorderTaskGroups.length + p.reorderDDGroups.length;

const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

/** Diff the draft against what the server last gave us. Used for both the dirty flag and Save. */
function buildPlan(
  draft: Draft | null,
  guide: AdminGuide | null,
  tasks: AdminTaskTemplate[],
  dd: AdminDDTemplate[]
): SavePlan {
  if (!draft || !guide) return EMPTY_PLAN;
  const plan: SavePlan = { ...EMPTY_PLAN, createTasks: [], createDD: [], updateTasks: [], updateDD: [],
    restoreTasks: [], restoreDD: [], retireTasks: [], retireDD: [], stageGuides: [],
    reorderTaskGroups: [], reorderDDGroups: [], programGuide: null };

  const serverTasks = new Map(tasks.map((t) => [t.id, t]));
  const serverDD = new Map(dd.map((d) => [d.id, d]));

  for (const row of draft.tasks) {
    if (isTemp(row.id)) { plan.createTasks.push(row); continue; }
    const before = serverTasks.get(row.id);
    if (!before) continue;
    const changes: Record<string, unknown> = {};
    if (row.title !== before.title) changes.title = row.title;
    if ((row.description ?? '') !== (before.description ?? '')) changes.description = row.description ?? '';
    if (Object.keys(changes).length) plan.updateTasks.push({ id: row.id, changes });
    if (row.is_active && !before.is_active) plan.restoreTasks.push(row.id);
    if (!row.is_active && before.is_active) plan.retireTasks.push(row.id);
  }
  for (const row of draft.dd) {
    if (isTemp(row.id)) { plan.createDD.push(row); continue; }
    const before = serverDD.get(row.id);
    if (!before) continue;
    const changes: Record<string, unknown> = {};
    if ((row.document_required ?? '') !== (before.document_required ?? '')) {
      changes.document_required = row.document_required ?? '';
    }
    if ((row.action_step ?? '') !== (before.action_step ?? '')) changes.action_step = row.action_step ?? '';
    if (Object.keys(changes).length) plan.updateDD.push({ id: row.id, changes });
    if (row.is_active && !before.is_active) plan.restoreDD.push(row.id);
    if (!row.is_active && before.is_active) plan.retireDD.push(row.id);
  }

  const programChanges: { workflow?: WorkflowStep[]; rules?: ProgramRule[] } = {};
  if (!same(draft.guide.program.workflow, guide.program.workflow)) {
    programChanges.workflow = draft.guide.program.workflow;
  }
  if (!same(draft.guide.program.rules, guide.program.rules)) programChanges.rules = draft.guide.program.rules;
  if (Object.keys(programChanges).length) plan.programGuide = programChanges;

  const serverStages = new Map(guide.stages.map((s) => [s.stage_code, s]));
  for (const stage of draft.guide.stages) {
    const before = serverStages.get(stage.stage_code);
    if (!before) continue;
    const changes: Partial<StageGuide> = {};
    for (const key of ['purpose', 'steps', 'watch', 'templates', 'run_with'] as const) {
      if (!same(stage.guide[key], before.guide[key])) {
        (changes as Record<string, unknown>)[key] = stage.guide[key];
      }
    }
    if (Object.keys(changes).length) plan.stageGuides.push({ stageCode: stage.stage_code, changes });
  }

  // A group is only reordered if its running order actually differs from the
  // server's. The markers say which groups to check, not which to send: moving a
  // row down and back up again leaves the marker set but changes nothing, and
  // without this the page would stay dirty and post a reorder that is a no-op.
  const taskOrder = (rows: AdminTaskTemplate[], group: string) =>
    rows.filter((t) => taskGroupKey(t) === group && t.is_active)
      .sort((a, b) => a.default_order - b.default_order).map((t) => t.id);
  const ddOrder = (rows: AdminDDTemplate[], group: string) =>
    rows.filter((i) => ddGroupKey(i) === group && i.is_active)
      .sort((a, b) => a.default_order - b.default_order).map((i) => i.id);

  plan.reorderTaskGroups = draft.reorderedTaskGroups.filter(
    (group) => !same(taskOrder(draft.tasks, group), taskOrder(tasks, group))
  );
  plan.reorderDDGroups = draft.reorderedDDGroups.filter(
    (group) => !same(ddOrder(draft.dd, group), ddOrder(dd, group))
  );
  return plan;
}

function buildDraft(guide: AdminGuide, tasks: AdminTaskTemplate[], dd: AdminDDTemplate[]): Draft {
  return {
    guide: JSON.parse(JSON.stringify(guide)) as AdminGuide,
    tasks: tasks.map((t) => ({ ...t })),
    dd: dd.map((d) => ({ ...d })),
    reorderedTaskGroups: [],
    reorderedDDGroups: [],
  };
}

// ----------------------------------------------------------------------
// Fields
// ----------------------------------------------------------------------
function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cn('card-trinity p-4 sm:p-6', className)}>{children}</section>;
}

const parseLines = (text: string) => text.split('\n').map((l) => l.trim()).filter(Boolean);

/**
 * A textarea whose lines are a list.
 *
 * Holds the raw text locally and reports the parsed lines on every keystroke, so
 * Save Changes lights up immediately. The parsed value is never fed back into
 * the box while typing - trimming and dropping blank lines mid-edit would fight
 * the cursor - so the effect below only resyncs when the value changes for some
 * other reason, such as a save completing.
 */
function LinesField({
  label, value, placeholder, disabled, onChange,
}: {
  label: string;
  value: string[];
  placeholder?: string;
  disabled?: boolean;
  onChange: (lines: string[]) => void;
}) {
  const [text, setText] = useState(() => value.join('\n'));
  useEffect(() => {
    if (value.join('\n') !== parseLines(text).join('\n')) setText(value.join('\n'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return (
    <div>
      <Label className="mb-1.5 block text-sm font-semibold">{label}</Label>
      <p className="mb-1.5 text-xs text-muted-foreground">One per line.</p>
      <Textarea
        value={text}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(e) => { setText(e.target.value); onChange(parseLines(e.target.value)); }}
        className="min-h-[120px] text-sm"
      />
    </div>
  );
}

/** Plain text, fully controlled by the draft - no parsing, so no local copy needed. */
function TextField({
  label, value, multiline = true, placeholder, disabled, onChange,
}: {
  label: string;
  value: string;
  multiline?: boolean;
  placeholder?: string;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  const props = {
    value,
    disabled,
    placeholder,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange(e.target.value),
  };
  return (
    <div>
      <Label className="mb-1.5 block text-sm font-semibold">{label}</Label>
      {multiline ? <Textarea {...props} className="min-h-[88px] text-sm" />
                 : <Input {...props} className="text-sm" />}
    </div>
  );
}

/** The badge on a row that is pending a create or a remove. */
function PendingBadge({ kind }: { kind: 'new' | 'removed' }) {
  return (
    <span
      className={cn(
        'rounded-full px-2 py-0.5 text-[11px] font-semibold',
        kind === 'new' ? 'bg-primary/10 text-primary' : 'bg-destructive/10 text-destructive'
      )}
    >
      {kind === 'new' ? 'new' : 'Will be removed on save'}
    </span>
  );
}

// ----------------------------------------------------------------------
// Program guide
// ----------------------------------------------------------------------
/**
 * Which stage, group, category and sub-item the admin is looking at.
 *
 * Held by the page rather than by the sections, so it survives the remount
 * Discard uses to clear their input state. Where you are is navigation, not
 * unsaved work, so Discard leaves it alone.
 */
interface Selection {
  guideStage: string;
  setGuideStage: (v: string) => void;
  taskStage: string;
  setTaskStage: (v: string) => void;
  taskSection: 'must_do' | 'optional';
  setTaskSection: (v: 'must_do' | 'optional') => void;
  ddCategory: string;
  setDdCategory: (v: string) => void;
  ddSubItem: string;
  setDdSubItem: (v: string) => void;
}

interface SectionProps {
  draft: Draft;
  setDraft: (fn: (d: Draft) => Draft) => void;
  disabled: boolean;
  selection: Selection;
  onRemove: (kind: 'task' | 'dd', id: string, label: string) => void;
}

function ProgramGuideSection({ draft, setDraft, disabled, selection }: Omit<SectionProps, 'onRemove'>) {
  const { guideStage: stageCode, setGuideStage: setStageCode } = selection;
  const stages = draft.guide.stages;
  const stage: AdminStage | undefined = stages.find((s) => s.stage_code === stageCode) ?? stages[0];

  const editStage = (changes: Partial<StageGuide>) => {
    if (!stage) return;
    setDraft((d) => ({
      ...d,
      guide: {
        ...d.guide,
        stages: d.guide.stages.map((s) =>
          s.stage_code === stage.stage_code ? { ...s, guide: { ...s.guide, ...changes } } : s
        ),
      },
    }));
  };
  const editProgram = (changes: { workflow?: WorkflowStep[]; rules?: ProgramRule[] }) =>
    setDraft((d) => ({ ...d, guide: { ...d.guide, program: { ...d.guide.program, ...changes } } }));

  const workflowLines = draft.guide.program.workflow.map((w) => `${w.stage} | ${w.label}`);
  const ruleLines = draft.guide.program.rules.map((r) => `${r.title} | ${r.body}`);

  return (
    <div className="space-y-5">
      {SHOW_PROGRAM_LEVEL_GUIDE && (
        <>
          <Card>
            <h2 className="font-heading text-base font-semibold">How the Sale Ready program runs</h2>
            <p className="mb-4 mt-1 text-xs text-muted-foreground">
              The workflow shown on the Program guide tab. Each line is <code>stage code | label</code>, where the code
              is one of the 15 stages or <code>modules</code>.
            </p>
            <LinesField
              label="Workflow steps"
              value={workflowLines}
              disabled={disabled}
              onChange={(lines) =>
                editProgram({
                  workflow: lines.map((line) => {
                    const [stagePart, ...rest] = line.split('|');
                    return { stage: stagePart.trim(), label: rest.join('|').trim() };
                  }),
                })
              }
            />
          </Card>

          <Card>
            <h2 className="font-heading text-base font-semibold">Program rules</h2>
            <p className="mb-4 mt-1 text-xs text-muted-foreground">
              Each line is <code>title | body</code>.
            </p>
            <LinesField
              label="Rules"
              value={ruleLines}
              disabled={disabled}
              onChange={(lines) =>
                editProgram({
                  rules: lines.map((line) => {
                    const [titlePart, ...rest] = line.split('|');
                    return { title: titlePart.trim(), body: rest.join('|').trim() };
                  }),
                })
              }
            />
          </Card>
        </>
      )}

      <Card>
        {/* items-start so the "Stage guide" heading and the "Stage" label share a top edge. */}
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="font-heading text-base font-semibold">Stage guide</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              The guide shown inside each stage. The 15 stages themselves are fixed.
            </p>
          </div>
          <div className="w-full sm:w-96">
            <Label className="mb-1.5 block text-sm font-semibold">Stage</Label>
            <Select value={stage?.stage_code ?? ''} onValueChange={setStageCode}>
              <SelectTrigger aria-label="Stage" className="text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {stages.map((s) => (
                  <SelectItem key={s.stage_code} value={s.stage_code}>
                    {s.display_code ? `${s.display_code} · ` : ''}
                    {s.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {stage && (
          <div className="space-y-4">
            <TextField
              label="Purpose"
              value={stage.guide.purpose}
              disabled={disabled}
              onChange={(purpose) => editStage({ purpose })}
            />
            <LinesField
              label="How it runs"
              value={stage.guide.steps}
              disabled={disabled}
              onChange={(steps) => editStage({ steps })}
            />
            <LinesField
              label="Watch for"
              value={stage.guide.watch}
              disabled={disabled}
              onChange={(watch) => editStage({ watch })}
            />
            {/* Only for stages that already list templates; the six with none hide the field. */}
            {stage.guide.templates.length > 0 && (
              <LinesField
                label="Templates"
                value={stage.guide.templates}
                disabled={disabled}
                onChange={(templates) => editStage({ templates })}
              />
            )}
            {stage.stage_type === 'module' && (
              <TextField
                label="Run with"
                value={stage.guide.run_with ?? ''}
                multiline={false}
                disabled={disabled}
                placeholder="Modules that commonly run alongside this one"
                onChange={(run_with) => editStage({ run_with })}
              />
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

// ----------------------------------------------------------------------
// Row controls shared by both lists
// ----------------------------------------------------------------------
function RowControls({
  disabled, pendingRemoval, canMoveUp, canMoveDown, onMove, onRemove, onRestore,
}: {
  disabled: boolean;
  pendingRemoval: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  onMove: (delta: number) => void;
  onRemove: () => void;
  onRestore: () => void;
}) {
  return (
    <div className="flex flex-shrink-0 items-center gap-1">
      <Button variant="ghost" size="icon" aria-label="Move up" disabled={disabled || pendingRemoval || !canMoveUp}
        onClick={() => onMove(-1)}>
        <ArrowUp className="h-4 w-4" />
      </Button>
      <Button variant="ghost" size="icon" aria-label="Move down" disabled={disabled || pendingRemoval || !canMoveDown}
        onClick={() => onMove(1)}>
        <ArrowDown className="h-4 w-4" />
      </Button>
      {pendingRemoval ? (
        <Button variant="ghost" size="icon" aria-label="Restore" disabled={disabled} onClick={onRestore}>
          <RotateCcw className="h-4 w-4" />
        </Button>
      ) : (
        <Button variant="ghost" size="icon" aria-label="Remove" disabled={disabled} onClick={onRemove}>
          <Trash2 className="h-4 w-4 text-destructive" />
        </Button>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------
// Task templates
// ----------------------------------------------------------------------
function TaskTemplatesSection({ draft, setDraft, disabled, selection, onRemove }: SectionProps) {
  const { taskStage: stageCode, setTaskStage: setStageCode, taskSection: section, setTaskSection: setSection } =
    selection;
  // Local on purpose: text typed but not yet added is unsaved input, so Discard clears it.
  const [newTitle, setNewTitle] = useState('');

  const stages = draft.guide.stages;
  const stage = stages.find((s) => s.stage_code === stageCode) ?? stages[0];

  const rows = useMemo(
    () => draft.tasks.filter((t) => t.stage_code === stage?.stage_code && t.section === section),
    [draft.tasks, stage, section]
  );
  const active = rows.filter((r) => r.is_active);

  const edit = (id: string, changes: Partial<AdminTaskTemplate>) =>
    setDraft((d) => ({ ...d, tasks: d.tasks.map((t) => (t.id === id ? { ...t, ...changes } : t)) }));

  const move = (row: AdminTaskTemplate, delta: number) => {
    const key = taskGroupKey(row);
    setDraft((d) => {
      const group = d.tasks.filter((t) => taskGroupKey(t) === key && t.is_active);
      const from = group.findIndex((t) => t.id === row.id);
      const to = from + delta;
      if (from < 0 || to < 0 || to >= group.length) return d;
      const reordered = [...group];
      [reordered[from], reordered[to]] = [reordered[to], reordered[from]];
      // Renumber the group the way the server would, so the new order is data.
      const order = new Map(reordered.map((t, i) => [t.id, i + 1]));
      return {
        ...d,
        tasks: d.tasks.map((t) => (order.has(t.id) ? { ...t, default_order: order.get(t.id)! } : t)),
        reorderedTaskGroups: d.reorderedTaskGroups.includes(key)
          ? d.reorderedTaskGroups
          : [...d.reorderedTaskGroups, key],
      };
    });
  };

  const add = () => {
    if (!stage || !newTitle.trim()) return;
    const last = Math.max(0, ...rows.map((r) => r.default_order));
    const row: AdminTaskTemplate = {
      id: tempId(),
      stage_code: stage.stage_code,
      template_key: 'new',
      section,
      group_title: null,
      title: newTitle.trim(),
      description: null,
      priority: 'medium',
      default_order: last + 1,
      due_offset_days: null,
      is_active: true,
    };
    setDraft((d) => ({ ...d, tasks: [...d.tasks, row] }));
    setNewTitle('');
  };

  const sorted = [...rows].sort((a, b) => a.default_order - b.default_order);

  return (
    <Card>
      <h2 className="font-heading text-base font-semibold">Task templates</h2>
      <p className="mb-4 mt-1 text-xs text-muted-foreground">
        Master templates, not tasks inside an engagement. Client-specific tasks are added by the advisor and are never
        templated.
      </p>

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <Label className="mb-1.5 block text-sm font-semibold">Stage</Label>
          <Select value={stage?.stage_code ?? ''} onValueChange={setStageCode}>
            <SelectTrigger aria-label="Stage" className="text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {stages.map((s) => (
                <SelectItem key={s.stage_code} value={s.stage_code}>
                  {s.display_code ? `${s.display_code} · ` : ''}
                  {s.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="mb-1.5 block text-sm font-semibold">Group</Label>
          <Select value={section} onValueChange={(v) => setSection(v as 'must_do' | 'optional')}>
            <SelectTrigger aria-label="Group" className="text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="must_do">Must-do</SelectItem>
              <SelectItem value="optional">Optional</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        {sorted.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No {SECTION_LABEL[section].toLowerCase()} templates for this stage yet.
          </p>
        )}
        {sorted.map((row) => {
          const index = active.findIndex((r) => r.id === row.id);
          return (
            <div
              key={row.id}
              className={cn(
                'flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-start sm:gap-3',
                !row.is_active && 'opacity-60'
              )}
            >
              <span className="mt-1 flex w-28 flex-shrink-0 flex-col gap-1">
                <span className="font-mono text-[11px] text-muted-foreground">{row.template_key}</span>
                {isTemp(row.id) && <PendingBadge kind="new" />}
              </span>
              <div className="flex-1 space-y-2">
                <Input
                  value={row.title}
                  disabled={disabled || !row.is_active}
                  aria-label="Title"
                  className="text-sm"
                  onChange={(e) => edit(row.id, { title: e.target.value })}
                />
                <Textarea
                  value={row.description ?? ''}
                  disabled={disabled || !row.is_active}
                  aria-label="Description"
                  placeholder="Description (optional)"
                  className="min-h-[44px] text-xs"
                  onChange={(e) => edit(row.id, { description: e.target.value })}
                />
                {!row.is_active && <PendingBadge kind="removed" />}
              </div>
              <RowControls
                disabled={disabled}
                pendingRemoval={!row.is_active}
                canMoveUp={index > 0}
                canMoveDown={index >= 0 && index < active.length - 1}
                onMove={(delta) => move(row, delta)}
                onRemove={() => onRemove('task', row.id, row.title)}
                onRestore={() => edit(row.id, { is_active: true })}
              />
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <Input
          value={newTitle}
          disabled={disabled}
          placeholder={`Add a ${SECTION_LABEL[section].toLowerCase()} task template`}
          onChange={(e) => setNewTitle(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
          className="text-sm"
        />
        <Button onClick={add} disabled={disabled || !newTitle.trim()} className="flex-shrink-0">
          <Plus className="mr-1.5 h-4 w-4" />
          Add
        </Button>
      </div>
    </Card>
  );
}

// ----------------------------------------------------------------------
// DD checklist
// ----------------------------------------------------------------------
function DDChecklistSection({ draft, setDraft, disabled, selection, onRemove }: SectionProps) {
  const categories = useAppSelector((s) => s.saleReadyAdmin.ddCategories);
  const { ddCategory: categoryCode, setDdCategory: setCategoryCode, ddSubItem: subItemCode,
    setDdSubItem: setSubItemCode } = selection;
  // Local on purpose: text typed but not yet added is unsaved input, so Discard clears it.
  const [newDoc, setNewDoc] = useState('');

  const category = categories.find((c) => c.category_code === categoryCode) ?? categories[0];
  const subItem = category?.sub_items.find((s) => s.sub_item_code === subItemCode) ?? category?.sub_items[0];

  const rows = useMemo(
    () =>
      draft.dd.filter(
        (i) => i.category_code === category?.category_code && i.sub_item_code === subItem?.sub_item_code
      ),
    [draft.dd, category, subItem]
  );
  const active = rows.filter((r) => r.is_active);

  const edit = (id: string, changes: Partial<AdminDDTemplate>) =>
    setDraft((d) => ({ ...d, dd: d.dd.map((i) => (i.id === id ? { ...i, ...changes } : i)) }));

  const move = (row: AdminDDTemplate, delta: number) => {
    const key = ddGroupKey(row);
    setDraft((d) => {
      const group = d.dd.filter((i) => ddGroupKey(i) === key && i.is_active);
      const from = group.findIndex((i) => i.id === row.id);
      const to = from + delta;
      if (from < 0 || to < 0 || to >= group.length) return d;
      const reordered = [...group];
      [reordered[from], reordered[to]] = [reordered[to], reordered[from]];
      // The server renumbers from the group's lowest existing order; mirror that.
      const base = Math.min(...group.map((i) => i.default_order));
      const order = new Map(reordered.map((i, idx) => [i.id, base + idx]));
      return {
        ...d,
        dd: d.dd.map((i) => (order.has(i.id) ? { ...i, default_order: order.get(i.id)! } : i)),
        reorderedDDGroups: d.reorderedDDGroups.includes(key) ? d.reorderedDDGroups : [...d.reorderedDDGroups, key],
      };
    });
  };

  const add = () => {
    if (!category || !subItem || !newDoc.trim()) return;
    const last = Math.max(0, ...draft.dd.map((i) => i.default_order));
    const row: AdminDDTemplate = {
      id: tempId(),
      item_key: 'new',
      stage_code: subItem.stage_code,
      category_code: category.category_code,
      category: category.category,
      sub_item_code: subItem.sub_item_code,
      sub_item: subItem.sub_item,
      document_required: newDoc.trim(),
      action_step: null,
      default_order: last + 1,
      is_active: true,
    };
    setDraft((d) => ({ ...d, dd: [...d.dd, row] }));
    setNewDoc('');
  };

  const sorted = [...rows].sort((a, b) => a.default_order - b.default_order);

  return (
    <Card>
      <h2 className="font-heading text-base font-semibold">Due diligence checklist</h2>
      <p className="mb-4 mt-1 text-xs text-muted-foreground">
        The master checklist. Categories and sub-items are fixed; a new item is filed under an existing sub-item, which
        sets its stage.
      </p>

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <Label className="mb-1.5 block text-sm font-semibold">Category</Label>
          <Select
            value={category?.category_code ?? ''}
            onValueChange={(v) => { setCategoryCode(v); setSubItemCode(''); }}
          >
            <SelectTrigger aria-label="Category" className="text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {categories.map((c) => (
                <SelectItem key={c.category_code} value={c.category_code}>
                  {c.category_code}. {c.category}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="mb-1.5 block text-sm font-semibold">Sub-item</Label>
          <Select value={subItem?.sub_item_code ?? ''} onValueChange={setSubItemCode}>
            <SelectTrigger aria-label="Sub-item" className="text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(category?.sub_items ?? []).map((s) => (
                <SelectItem key={s.sub_item_code} value={s.sub_item_code}>
                  {s.sub_item_code} {s.sub_item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        {sorted.length === 0 && (
          <p className="py-6 text-center text-sm text-muted-foreground">No items under this sub-item yet.</p>
        )}
        {sorted.map((row) => {
          const index = active.findIndex((r) => r.id === row.id);
          return (
            <div
              key={row.id}
              className={cn(
                'flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-start sm:gap-3',
                !row.is_active && 'opacity-60'
              )}
            >
              <span className="mt-1 flex w-24 flex-shrink-0 flex-col gap-1">
                <span className="font-mono text-[11px] text-muted-foreground">{row.item_key}</span>
                {isTemp(row.id) && <PendingBadge kind="new" />}
              </span>
              <div className="flex-1 space-y-2">
                <Textarea
                  value={row.document_required ?? ''}
                  disabled={disabled || !row.is_active}
                  aria-label="Document required"
                  placeholder="Document required"
                  className="min-h-[44px] text-sm"
                  onChange={(e) => edit(row.id, { document_required: e.target.value })}
                />
                <Textarea
                  value={row.action_step ?? ''}
                  disabled={disabled || !row.is_active}
                  aria-label="Action step"
                  placeholder="Action step (optional)"
                  className="min-h-[44px] text-xs"
                  onChange={(e) => edit(row.id, { action_step: e.target.value })}
                />
                {!row.is_active && <PendingBadge kind="removed" />}
              </div>
              <RowControls
                disabled={disabled}
                pendingRemoval={!row.is_active}
                canMoveUp={index > 0}
                canMoveDown={index >= 0 && index < active.length - 1}
                onMove={(delta) => move(row, delta)}
                onRemove={() => onRemove('dd', row.id, row.document_required ?? row.item_key)}
                onRestore={() => edit(row.id, { is_active: true })}
              />
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-col gap-2 sm:flex-row">
        <Input
          value={newDoc}
          disabled={disabled}
          placeholder="Add a checklist item: the document required"
          onChange={(e) => setNewDoc(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && add()}
          className="text-sm"
        />
        <Button onClick={add} disabled={disabled || !newDoc.trim()} className="flex-shrink-0">
          <Plus className="mr-1.5 h-4 w-4" />
          Add
        </Button>
      </div>
    </Card>
  );
}

// ----------------------------------------------------------------------
export default function SaleReadyManagementPage() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { guide, taskTemplates, ddTemplates, isLoading, error } = useAppSelector((s) => s.saleReadyAdmin);

  const isAdmin = user?.role === 'super_admin' || user?.role === 'admin';
  const [draft, setDraft] = useState<Draft | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState<{ kind: 'task' | 'dd'; id: string; label: string } | null>(null);
  // Bumped by Discard to remount the three sections. See `discard` below.
  const [sectionKey, setSectionKey] = useState(0);
  // Where the admin is looking. Lives here so the remount does not move them.
  const [guideStage, setGuideStage] = useState('');
  const [taskStage, setTaskStage] = useState('');
  const [taskSection, setTaskSection] = useState<'must_do' | 'optional'>('must_do');
  const [ddCategory, setDdCategory] = useState('');
  const [ddSubItem, setDdSubItem] = useState('');

  useEffect(() => {
    if (!isAdmin) {
      navigate('/dashboard', { replace: true });
      return;
    }
    dispatch(fetchAdminGuide());
    dispatch(fetchTaskTemplates());
    dispatch(fetchDDCategories());
    dispatch(fetchDDTemplates());
  }, [dispatch, isAdmin, navigate]);

  // First load only. After that the draft is ours until a save replaces it.
  useEffect(() => {
    if (draft === null && guide) setDraft(buildDraft(guide, taskTemplates, ddTemplates));
  }, [draft, guide, taskTemplates, ddTemplates]);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  const plan = useMemo(
    () => buildPlan(draft, guide, taskTemplates, ddTemplates),
    [draft, guide, taskTemplates, ddTemplates]
  );
  const isDirty = planSize(plan) > 0;

  // Refresh, tab close and navigation away from the app. In-app sidebar
  // navigation is deliberately not blocked - this router is a BrowserRouter,
  // so react-router's blocker is unavailable without migrating the whole app.
  useEffect(() => {
    if (!isDirty) return;
    const warn = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [isDirty]);

  const applyRemoval = useCallback(() => {
    if (!confirmRemove) return;
    const { kind, id } = confirmRemove;
    setDraft((d) => {
      if (!d) return d;
      // A row that was only ever pending has nothing to retire - drop it.
      if (isTemp(id)) {
        return kind === 'task'
          ? { ...d, tasks: d.tasks.filter((t) => t.id !== id) }
          : { ...d, dd: d.dd.filter((i) => i.id !== id) };
      }
      return kind === 'task'
        ? { ...d, tasks: d.tasks.map((t) => (t.id === id ? { ...t, is_active: false } : t)) }
        : { ...d, dd: d.dd.map((i) => (i.id === id ? { ...i, is_active: false } : i)) };
    });
    setConfirmRemove(null);
  }, [confirmRemove]);

  const reload = useCallback(async () => {
    const [freshGuide, freshTasks, freshDD] = await Promise.all([
      dispatch(fetchAdminGuide()).unwrap(),
      dispatch(fetchTaskTemplates()).unwrap(),
      dispatch(fetchDDTemplates()).unwrap(),
    ]);
    setDraft(buildDraft(freshGuide, freshTasks, freshDD));
  }, [dispatch]);

  /**
   * Submit the plan in dependency order.
   *
   * Creates first, because a reorder has to name real ids. Reorder last,
   * because the endpoint checks the submitted ids against the group's current
   * active rows - only once the creates and removes have landed does that set
   * match what the admin sees. A failed step stops the run: pressing on would
   * send a reorder for a set that does not exist.
   */
  const save = async () => {
    if (!draft || !isDirty) return;
    setIsSaving(true);
    const realId = new Map<string, string>();
    try {
      for (const row of plan.createTasks) {
        const created = await dispatch(createTaskTemplate({
          stage_code: row.stage_code,
          section: row.section,
          title: row.title,
          ...(row.description ? { description: row.description } : {}),
        })).unwrap();
        realId.set(row.id, created.id);
      }
      for (const row of plan.createDD) {
        const created = await dispatch(createDDTemplate({
          category_code: row.category_code,
          sub_item_code: row.sub_item_code,
          document_required: row.document_required ?? '',
          ...(row.action_step ? { action_step: row.action_step } : {}),
        })).unwrap();
        realId.set(row.id, created.id);
      }

      for (const u of plan.updateTasks) await dispatch(updateTaskTemplate(u)).unwrap();
      for (const u of plan.updateDD) await dispatch(updateDDTemplate(u)).unwrap();

      for (const id of plan.restoreTasks) {
        await dispatch(updateTaskTemplate({ id, changes: { is_active: true } })).unwrap();
      }
      for (const id of plan.restoreDD) {
        await dispatch(updateDDTemplate({ id, changes: { is_active: true } })).unwrap();
      }

      for (const id of plan.retireTasks) await dispatch(retireTaskTemplate(id)).unwrap();
      for (const id of plan.retireDD) await dispatch(retireDDTemplate(id)).unwrap();

      if (plan.programGuide) await dispatch(updateProgramGuide(plan.programGuide)).unwrap();
      for (const s of plan.stageGuides) {
        await dispatch(updateStageGuide({ stageCode: s.stageCode, changes: s.changes })).unwrap();
      }

      for (const key of plan.reorderTaskGroups) {
        const ids = draft.tasks
          .filter((t) => taskGroupKey(t) === key && t.is_active)
          .sort((a, b) => a.default_order - b.default_order)
          .map((t) => realId.get(t.id) ?? t.id);
        if (ids.length > 1) await dispatch(reorderTaskTemplates(ids)).unwrap();
      }
      for (const key of plan.reorderDDGroups) {
        const ids = draft.dd
          .filter((i) => ddGroupKey(i) === key && i.is_active)
          .sort((a, b) => a.default_order - b.default_order)
          .map((i) => realId.get(i.id) ?? i.id);
        if (ids.length > 1) await dispatch(reorderDDTemplates(ids)).unwrap();
      }

      await reload();
      toast.success('Changes saved');
    } catch (e) {
      toast.error(`${String(e)} - reloading to show what was saved`);
      await reload().catch(() => undefined);
    } finally {
      setIsSaving(false);
    }
  };

  /**
   * Throw the draft away and start again from the server state we already hold.
   *
   * No request: the store still has exactly what the API last returned, so
   * rebuilding from it reverts every tab at once - temp rows disappear, removals
   * and restores revert, reorder markers and default_order reset, and the guide
   * comes back as a fresh deep clone. Refetching here would only add a way for
   * Discard to fail.
   */
  const discard = () => {
    if (!guide) return;
    setDraft(buildDraft(guide, taskTemplates, ddTemplates));
    // Remount the sections so their own state goes too. The draft covers saved-
    // shaped changes, but each section also holds input that never reached it:
    // the text sitting in an Add box, and the raw text inside every LinesField.
    // Bumping the key clears all of it without having to enumerate it, which is
    // what stops a field added later from being quietly missed. The selection
    // dropdowns are held by this component, so they survive and the admin stays
    // on the stage, group and sub-item they were working on.
    setSectionKey((k) => k + 1);
    toast.success('Changes discarded');
  };

  if (!isAdmin) return null;

  const selection: Selection = {
    guideStage, setGuideStage,
    taskStage, setTaskStage,
    taskSection, setTaskSection,
    ddCategory, setDdCategory,
    ddSubItem, setDdSubItem,
  };

  const sectionProps = draft
    ? { draft, setDraft: setDraft as (fn: (d: Draft) => Draft) => void, disabled: isSaving, selection,
        onRemove: (kind: 'task' | 'dd', id: string, label: string) => setConfirmRemove({ kind, id, label }) }
    : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="font-heading text-2xl font-bold">Sale Ready Management</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{FUTURE_ONLY}</p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          {isDirty && (
            <span className="text-xs font-semibold text-warning">
              {planSize(plan)} unsaved change{planSize(plan) === 1 ? '' : 's'}
            </span>
          )}
          <Button variant="outline" disabled={!isDirty || isSaving} onClick={discard}>
            Discard
          </Button>
          <Button disabled={!isDirty || isSaving} onClick={save}>
            {isSaving ? 'Saving…' : 'Save Changes'}
          </Button>
        </div>
      </div>

      {!sectionProps ? (
        <Card>{isLoading ? 'Loading…' : 'Loading the Sale Ready content…'}</Card>
      ) : (
        <Tabs defaultValue="guide">
          <TabsList className="mb-6 h-auto w-full flex-wrap justify-start gap-x-6 gap-y-1 rounded-none border-b border-border bg-transparent p-0">
            <TabsTrigger value="guide">Program Guide</TabsTrigger>
            <TabsTrigger value="tasks">Task Templates</TabsTrigger>
            <TabsTrigger value="dd">DD Checklist</TabsTrigger>
          </TabsList>
          <TabsContent value="guide">
            <ProgramGuideSection key={sectionKey} draft={sectionProps.draft}
              setDraft={sectionProps.setDraft} disabled={sectionProps.disabled}
              selection={sectionProps.selection} />
          </TabsContent>
          <TabsContent value="tasks">
            <TaskTemplatesSection key={sectionKey} {...sectionProps} />
          </TabsContent>
          <TabsContent value="dd">
            <DDChecklistSection key={sectionKey} {...sectionProps} />
          </TabsContent>
        </Tabs>
      )}

      <AlertDialog open={confirmRemove !== null} onOpenChange={(open) => !open && setConfirmRemove(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this {confirmRemove?.kind === 'dd' ? 'checklist item' : 'task template'}?</AlertDialogTitle>
            <AlertDialogDescription>
              {confirmRemove?.label}
              <span className="mt-2 block">
                It is marked for removal here and nothing changes in the database until you press Save Changes.
                Engagements already running keep it either way.
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={applyRemoval}>Remove</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
