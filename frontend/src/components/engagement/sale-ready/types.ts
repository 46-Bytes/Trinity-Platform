/**
 * The Sale Ready API contract (backend/app/schemas/sale_ready.py), served under
 * /api/sale-ready/engagements/{id}. Field names are snake_case to mirror the
 * FastAPI response. Counts and status are always server-derived; the UI never
 * computes a stage's status itself.
 */

export type StageType = 'pre_module' | 'module' | 'post_module';

/** Display status, derived on the server from stage state, tasks and DD items. */
export type StageStatus = 'not_started' | 'in_progress' | 'completed';

export type DDStatus = 'yes' | 'in_progress' | 'no' | 'not_applicable';
export type GapHandling = 'fix' | 'disclose' | 'refer';
export type TaskSection = 'must_do' | 'optional' | 'client_specific';

/** Sale Ready's own per-task marks. Null on every ordinary task. */
export type TaskState = 'not_applicable' | 'blocked' | null;

export interface SaleReadyPerson {
  id: string;
  name: string;
  role: string;
}

export interface RoadmapStage {
  stage_code: string;
  /** P1-P7 for phases, M1-M8 for modules. */
  display_code: string | null;
  title: string;
  stage_type: StageType;
  /** 'sale_planner' | 'closeout' for stages with their own screen. */
  ui_variant: string | null;
  status: StageStatus;
  /** Modules only: 1-based position in the effective order. */
  effective_rank: number | null;
  /** Modules only: true for M8, which the advisor cannot move. */
  is_pinned_last: boolean;
  /** False until the advisor starts a module and its tasks are created. */
  tasks_created: boolean;
  must_do_total: number;
  must_do_resolved: number;
  dd_total: number;
  dd_yes: number;
  start_date: string | null;
  due_date: string | null;
}

export interface RoadmapProgress {
  phases_completed: number;
  phases_total: number;
  modules_completed: number;
  modules_total: number;
  must_do_resolved: number;
  must_do_total: number;
  dd_yes: number;
  dd_total: number;
  percent: number;
}

export interface GapSummary {
  total: number;
  fix: number;
  disclose: number;
  refer: number;
  unhandled: number;
}

export interface SaleReadyRoadmap {
  engagement_id: string;
  /** Where the module order came from, as in the Program Guide. */
  order_source: 'diagnostic' | 'custom' | 'default';
  phases: RoadmapStage[];
  /** Already in effective order, pinned module last. */
  modules: RoadmapStage[];
  post_phases: RoadmapStage[];
  progress: RoadmapProgress;
  gaps: GapSummary;
  lead_advisor_name: string | null;
  closeout: { is_closed: boolean; closed_at: string | null; referred_to_benchmark: boolean };
  sale_planner_issues: { addressed: number; total: number };
}

export interface DDItem {
  id: string;
  item_key: string;
  stage_code: string;
  stage_title: string;
  category_code: string;
  category: string;
  sub_item_code: string;
  sub_item: string | null;
  document_required: string | null;
  action_step: string | null;
  display_order: number;
  status: DDStatus | null;
  /** Stored choice; only counts while status is 'no'. */
  gap_handling: GapHandling | null;
  flag_for_m8: boolean;
  responsible_user_id: string | null;
  notes: string | null;
  date_completed: string | null;
  status_changed_at: string | null;
}

export interface DDStats {
  total: number;
  yes: number;
  in_progress: number;
  no: number;
  not_applicable: number;
  no_status: number;
  flagged: number;
  referred: number;
}

export interface DDChecklist {
  items: DDItem[];
  stats: DDStats;
  stages: { stage_code: string; title: string }[];
  people: SaleReadyPerson[];
}

export type DDItemUpdate = Partial<
  Pick<DDItem, 'status' | 'gap_handling' | 'notes' | 'responsible_user_id' | 'flag_for_m8'>
>;

export interface StageTask {
  id: string;
  title: string;
  description: string | null;
  section: TaskSection;
  group_title: string | null;
  status: string;
  /** 'not_applicable' or 'blocked'; null otherwise. Never written to `status`. */
  sale_ready_state: TaskState;
  assigned_to_user_id: string | null;
  due_date: string | null;
  notes: string | null;
  from_template: boolean;
}

export interface StageQA {
  passed: boolean;
  open_must_do: number;
  dd_without_status: number;
  reasons: string[];
}

export interface StageDetail {
  stage: RoadmapStage;
  task_creation: 'on_engagement_create' | 'on_start';
  lead_advisor_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  completed_by_name: string | null;
  updated_at: string | null;
  qa: StageQA;
  tasks: StageTask[];
  /** Tasks starting the stage would create; empty once they exist. */
  template_preview: { title: string; section: TaskSection; group_title: string | null }[];
  dd_items: DDItem[];
  /** M8 only: DD items flagged for review across every stage. */
  flagged_for_review: DDItem[];
  ui_config: Record<string, unknown> | null;
  /** This engagement's frozen stage guide. Empty on engagements that predate snapshots. */
  guide: Partial<StageGuideContent>;
  people: SaleReadyPerson[];
}

export interface StageUpdate {
  start_date?: string | null;
  due_date?: string | null;
  lead_advisor_id?: string | null;
}

export interface StageTaskUpdate {
  status?: string;
  sale_ready_state?: TaskState;
  assigned_to_user_id?: string | null;
  due_date?: string | null;
  notes?: string | null;
}

// ---------------------------------------------------------------- Sale Planner and Close-out
export interface PlannerOption {
  key: string;
  label: string;
}

export interface SalePlannerConfig {
  sale_types: PlannerOption[];
  sale_structures: PlannerOption[];
  value_proposition_structures: PlannerOption[];
  marketing_questions: PlannerOption[];
  issues: PlannerOption[];
}

export interface PlannerIssue {
  addressed: boolean;
  note: string;
}

export interface SalePlanner {
  config: SalePlannerConfig;
  sale_type: string | null;
  sale_structures: string[];
  value_propositions: Record<string, string>;
  marketing_answers: Record<string, string>;
  issues: Record<string, PlannerIssue>;
  issues_addressed: number;
  issues_total: number;
  updated_at: string | null;
  updated_by_name: string | null;
}

/** sale_type and sale_structures replace; the maps merge by key, and null removes a key. */
export interface SalePlannerUpdate {
  sale_type?: string | null;
  sale_structures?: string[];
  value_propositions?: Record<string, string | null>;
  marketing_answers?: Record<string, string | null>;
  // A partial entry patches only the fields it carries; null removes the issue.
  issues?: Record<string, Partial<PlannerIssue> | null>;
}

export interface Closeout {
  fresh_appraisal_required: boolean;
  referred_to_benchmark: boolean;
  ongoing_assistance: string | null;
  is_closed: boolean;
  closed_at: string | null;
  closed_by_name: string | null;
  engagement_status: string;
  engagement_completed_at: string | null;
  /** Whether the current user may close or reopen the program. */
  can_close: boolean;
}

export type CloseoutUpdate = Partial<
  Pick<Closeout, 'fresh_appraisal_required' | 'referred_to_benchmark' | 'ongoing_assistance'>
>;

/** A stage's guide content, as stored on the engagement's snapshot. */
export interface StageGuideContent {
  purpose: string;
  steps: string[];
  watch: string[];
  templates: string[];
  run_with: string | null;
}

/** The engagement's frozen program guide. */
export interface SaleReadyGuide {
  program: {
    workflow?: { stage: string; label: string }[];
    rules?: { title: string; body: string }[];
  };
  stages: Record<string, Partial<StageGuideContent>>;
}
