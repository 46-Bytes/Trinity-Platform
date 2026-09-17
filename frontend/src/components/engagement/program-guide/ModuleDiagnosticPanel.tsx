import { Activity, AlertTriangle, Sparkles } from 'lucide-react';

import { cn } from '@/lib/utils';
import type { ModuleInsight } from '@/store/slices/programGuideReducer';
import { RAG_CLASS, SECTION_LABEL_CLASS, SOURCE_LABEL_CLASS, formatScore } from './moduleDisplay';

interface ModuleDiagnosticPanelProps {
  insight?: ModuleInsight;
  hasScores: boolean;
}

/**
 * The per-client half of a module card: what the diagnostic measured here.
 *
 * Everything here is generated, and it is labelled as such - the panel sits
 * directly above the authored module card, and the two must not read as the
 * same kind of content. One is the same for every client; this one is not.
 *
 * The empty states are the point of this component as much as the populated
 * one. An engagement may have no completed diagnostic at all, or one that never
 * scored this particular module, and both are ordinary states rather than
 * failures. A module with no score says so instead of showing a zero.
 */
export function ModuleDiagnosticPanel({ insight, hasScores }: ModuleDiagnosticPanelProps) {
  const scored = insight?.score != null;
  const thinEvidence =
    typeof insight?.answered_questions === 'number' && insight.answered_questions > 0 && insight.answered_questions < 5;

  return (
    <div className="card-trinity p-6">
      <span className={cn(SOURCE_LABEL_CLASS, 'bg-info/10 text-info mb-4')}>
        <Sparkles className="h-3 w-3" />
        Generated · from this client's diagnostic
      </span>

      <div>
        <p className={SECTION_LABEL_CLASS}>
          <Activity className="h-3.5 w-3.5" />
          Current state
        </p>

        {scored ? (
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-3xl font-bold leading-none">
              {formatScore(insight?.score)}
              <span className="text-base font-medium text-muted-foreground"> /5</span>
            </span>
            {insight?.rag && (
              <span
                className={cn('status-badge', RAG_CLASS[insight.rag] ?? 'bg-muted text-muted-foreground')}
              >
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
                {insight.severity ? `${insight.rag} / ${insight.severity}` : insight.rag}
              </span>
            )}
            {/*
              The score is not just a measurement here, it is the reason for the
              module's position in the program. Saying so on the card is what
              stops the rank reading as an unexplained editorial decision.
            */}
            {insight?.effective_rank != null && (
              <span className="text-xs text-muted-foreground">
                Sequenced {insight.effective_rank}
                {insight.effective_rank === 1 ? 'st' : insight.effective_rank === 2 ? 'nd' : insight.effective_rank === 3 ? 'rd' : 'th'} on this score
              </span>
            )}
          </div>
        ) : (
          <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            {hasScores
              ? 'The latest diagnostic did not score this module, so its position comes from the default program order.'
              : 'No completed diagnostic for this engagement yet. Complete the diagnostic to score this module and set the program order.'}
          </p>
        )}
      </div>

      {(hasScores || thinEvidence) && (
        <div className="mt-5 space-y-2 border-t border-border pt-4">
          {typeof insight?.answered_questions === 'number' && (
            <p className="text-xs text-muted-foreground">
              Scored from {insight.answered_questions} diagnostic{' '}
              {insight.answered_questions === 1 ? 'question' : 'questions'}.
            </p>
          )}

          {/*
            Roughly a third of the diagnostic is conditional, so a service
            business never sees the ERP, retail or warehousing questions. A
            module scored on three answers is not comparable to one scored on
            eighteen, and both currently rank the same way - worth saying on the
            card rather than leaving an advisor to infer it.
          */}
          {thinEvidence && (
            <p className="flex items-start gap-2 rounded-lg bg-warning/10 p-3 text-xs text-warning">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
              <span>
                Thin evidence. This score rests on few applicable answers, so treat it as less certain than
                a module scored across many.
              </span>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
