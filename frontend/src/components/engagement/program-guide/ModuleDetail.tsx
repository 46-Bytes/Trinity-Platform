import { ArrowLeft, ArrowRight, Award, Info } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useToolLaunchers, type DiagnosticSummary, type ToolKey } from '@/hooks/useToolLaunchers';
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
import type { ModuleDeliverables } from '@/store/slices/deliverablesReducer';
import type { ProgramGuideInsights, ProgramGuideModule, ProgramGuideView } from '@/store/slices/programGuideReducer';
import { ModuleContentPanel } from './ModuleContentPanel';
import { ModuleDeliverablesPanel } from './ModuleDeliverablesPanel';
import { ModuleDiagnosticPanel } from './ModuleDiagnosticPanel';
import { ModuleSessionsPanel } from './ModuleSessionsPanel';
import { NoteBlocks } from './ModulePrimitives';
import {
  RAG_CLASS,
  SECTION_LABEL_CLASS,
  STATUS_CONFIG,
  formatScore,
  moduleLevelNotes,
  notesForSection,
  statusOf,
} from './moduleDisplay';

interface ModuleDetailProps {
  module: ProgramGuideModule;
  nextModule?: ProgramGuideModule;
  view: ProgramGuideView;
  insights: ProgramGuideInsights | null;
  moduleDeliverables?: ModuleDeliverables;
  engagementId: string;
  diagnostics: DiagnosticSummary[];
  currentUserId?: string | null;
  isAdmin?: boolean;
  rankedCount: number;
  onBack: () => void;
  onGoToNext?: () => void;
  onNavigateToDiagnostic?: () => void;
}

/**
 * How the module reached its position in the order.
 *
 * The mockup carries a hand-written "why this rank" paragraph per module. No
 * such field exists, and inventing one would be worse than saying nothing - it
 * would read as analysis of this client while being a template string. What IS
 * knowable is where the order came from and, when it came from the diagnostic,
 * the score that put the module where it is. That is what this says.
 */
function rankExplanation(
  view: ProgramGuideView,
  module: ProgramGuideModule,
  insights: ProgramGuideInsights | null
): string | null {
  if (module.effective_rank == null) return null;

  const insight = insights?.modules.find((m) => m.module_code === module.module_code);

  if (view.order_source === 'custom') {
    return 'An advisor set this order by hand for this engagement, overriding the recommended sequence.';
  }

  if (view.order_source === 'diagnostic' && insight?.score != null) {
    return `Positioned by this client’s diagnostic: ${insight.score.toFixed(1)} of 5${
      insight.severity ? ` (${insight.severity.toLowerCase()})` : ''
    }. The weakest-scoring modules are sequenced first.`;
  }

  if (view.order_source === 'diagnostic') {
    return 'The diagnostic did not score this module, so it falls after the scored ones in default program order.';
  }

  return 'No completed diagnostic for this engagement yet, so the program runs in its default order.';
}

export function ModuleDetail({
  module,
  nextModule,
  view,
  insights,
  moduleDeliverables,
  engagementId,
  diagnostics,
  currentUserId,
  isAdmin = false,
  rankedCount,
  onBack,
  onGoToNext,
  onNavigateToDiagnostic,
}: ModuleDetailProps) {
  const { anyLoading, tools } = useToolLaunchers(engagementId, diagnostics, currentUserId, isAdmin);

  const insight = insights?.modules.find((m) => m.module_code === module.module_code);
  const status = statusOf(moduleDeliverables?.status);
  const statusConfig = STATUS_CONFIG[status];
  const why = rankExplanation(view, module, insights);

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="sm" onClick={onBack} className="gap-2 text-muted-foreground">
        <ArrowLeft className="h-4 w-4" />
        Back to modules
      </Button>

      <div className="card-trinity p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-[240px] flex-1">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              {module.module_code}
              {module.effective_rank != null && ` · Rank ${module.effective_rank} of ${rankedCount}`}
            </p>
            <h2 className="font-heading text-2xl font-bold tracking-tight mt-1">{module.title}</h2>
            {module.focus && <p className="mt-1.5 text-sm text-muted-foreground">{module.focus}</p>}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {insight?.rag && (
              <span className={cn('status-badge', RAG_CLASS[insight.rag] ?? 'bg-muted text-muted-foreground')}>
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
                {insight.severity ? `${insight.rag} / ${insight.severity}` : insight.rag}
              </span>
            )}
            <span className={cn('status-badge', statusConfig.badgeClass)}>
              <statusConfig.icon className="h-3 w-3" />
              {statusConfig.label}
            </span>
            <span className="text-xl font-bold">
              {formatScore(insight?.score)}
              <span className="text-sm font-medium text-muted-foreground"> /5</span>
            </span>
          </div>
        </div>

        {why && (
          <p className="mt-4 flex items-start gap-2 rounded-r-lg border-l-2 border-accent bg-muted/40 px-4 py-3 text-sm leading-relaxed text-muted-foreground">
            <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-accent" />
            <span>
              <span className="font-semibold text-foreground">Why this position. </span>
              {why}
            </span>
          </p>
        )}
      </div>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-[1fr_340px]">
        <div className="min-w-0 space-y-4">
          <ModuleDiagnosticPanel insight={insight} hasScores={Boolean(insights?.has_scores)} />

          {/* Notes with no section belong to the module as a whole. */}
          {moduleLevelNotes(module.notes).length > 0 && (
            <div className="card-trinity p-6">
              <p className={SECTION_LABEL_CLASS}>
                <Info className="h-3.5 w-3.5" />
                About this module
              </p>
              <NoteBlocks notes={moduleLevelNotes(module.notes)} />
            </div>
          )}

          <ModuleContentPanel module={module} />

          <ModuleSessionsPanel
            module={module}
            tools={tools}
            anyToolLoading={anyLoading}
            onNavigateToDiagnostic={onNavigateToDiagnostic}
          />
        </div>

        <div className="space-y-4 lg:sticky lg:top-4">
          <ModuleDeliverablesPanel
            engagementId={engagementId}
            moduleCode={module.module_code}
            moduleDeliverables={moduleDeliverables}
          />

          {notesForSection(module.notes, 'deliverables').length > 0 && (
            <div className="card-trinity p-6">
              <p className={SECTION_LABEL_CLASS}>
                <Info className="h-3.5 w-3.5" />
                On these deliverables
              </p>
              <NoteBlocks notes={notesForSection(module.notes, 'deliverables')} />
            </div>
          )}

          {module.quality_standards && module.quality_standards.length > 0 && (
            <div className="card-trinity p-6">
              <p className={SECTION_LABEL_CLASS}>
                <Award className="h-3.5 w-3.5" />
                Quality standards
              </p>
              <p className="mb-3 text-xs text-muted-foreground">
                What a well-run {module.module_code} looks like.
              </p>
              <ul className="space-y-2">
                {module.quality_standards.map((standard, index) => (
                  <li key={index} className="relative pl-4 text-sm leading-relaxed text-muted-foreground">
                    <span className="absolute left-0 top-[0.6rem] h-1.5 w-1.5 rounded-full bg-success" />
                    {standard}
                  </li>
                ))}
              </ul>
              <NoteBlocks notes={notesForSection(module.notes, 'quality_standards')} className="mt-3" />
            </div>
          )}
        </div>
      </div>

      {nextModule && (
        <button
          type="button"
          onClick={() => onGoToNext?.()}
          className="card-trinity flex w-full items-center justify-between bg-primary/5 px-6 py-3.5 text-left transition-colors hover:bg-primary/10"
        >
          <span>
            <span className="block text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Next module
            </span>
            <span className="text-sm font-medium">
              {nextModule.module_code} · {nextModule.title}
            </span>
          </span>
          <span className="flex items-center gap-1 text-sm font-medium text-primary">
            Open
            <ArrowRight className="h-3.5 w-3.5" />
          </span>
        </button>
      )}

      {(['bba', 'strategy_workbook', 'strategic_business_plan'] as ToolKey[]).map((key) => (
        <AlertDialog
          key={key}
          open={tools[key].dialog.open}
          onOpenChange={(open) => !open && tools[key].cancelDialog()}
        >
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{tools[key].dialog.title}</AlertDialogTitle>
              <AlertDialogDescription>{tools[key].dialog.description}</AlertDialogDescription>
              <p className="mt-2 text-sm font-medium text-destructive">{tools[key].dialog.warning}</p>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={tools[key].continueExisting}>Continue Existing</AlertDialogAction>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={tools[key].startFresh}
              >
                Start Fresh
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      ))}
    </div>
  );
}
