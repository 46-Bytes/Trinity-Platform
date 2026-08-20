import { Activity, AlertTriangle, Sparkles } from 'lucide-react';

import { cn } from '@/lib/utils';
import type { ModuleInsight } from '@/store/slices/programGuideReducer';
import { SECTION_LABEL_CLASS, SOURCE_LABEL_CLASS } from './moduleDisplay';

interface ModuleDiagnosticPanelProps {
  insight?: ModuleInsight;
  hasScores: boolean;
  hasFindings: boolean;
}

/** BBA authors these as free text; anything unrecognised falls through to neutral. */
const IMPACT_CLASS: Record<string, string> = {
  high: 'bg-destructive/10 text-destructive',
  medium: 'bg-warning/10 text-warning',
  low: 'bg-muted text-muted-foreground',
};

/**
 * The per-client half of a module card: what the diagnostic measured and what
 * the Recommendations Report Builder found.
 *
 * Everything here is generated, and it is labelled as such - the panel sits
 * directly above the authored module card, and the two must not read as the
 * same kind of content. One is the same for every client; this one is not.
 *
 * The empty states are the point of this component as much as the populated
 * one. An engagement may have a diagnostic and no BBA, a BBA and no diagnostic,
 * or neither, and each of those is an ordinary state rather than a failure. A
 * module with no score says so instead of showing a zero.
 */
export function ModuleDiagnosticPanel({ insight, hasScores, hasFindings }: ModuleDiagnosticPanelProps) {
  const findings = insight?.findings ?? [];
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

        {findings.length > 0 ? (
          <ul className="space-y-3">
            {findings.map((finding) => (
              <li key={`${finding.rank}-${finding.title}`} className="border-l-2 border-border pl-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-medium text-foreground">{finding.title}</span>
                  {finding.impact && (
                    <span
                      className={cn(
                        'status-badge',
                        IMPACT_CLASS[finding.impact.toLowerCase()] ?? 'bg-muted text-muted-foreground'
                      )}
                    >
                      {finding.impact} impact
                    </span>
                  )}
                  {finding.urgency && (
                    <span className="text-[11px] text-muted-foreground">{finding.urgency}</span>
                  )}
                </div>
                {finding.summary && (
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{finding.summary}</p>
                )}
                {/*
                  The raw text the finding was matched on. Matching is documented
                  as fragile across module renames, and a finding that reads
                  wrong on a module is the only signal that it landed here by
                  mistake - so the advisor gets to see what it matched.
                */}
                {finding.priority_area && (
                  <p className="mt-1 text-[11px] text-muted-foreground/70">
                    Matched on “{finding.priority_area}”
                  </p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            {hasFindings
              ? 'The Recommendations Report Builder produced no findings against this module. Its position comes from the default program order.'
              : 'No Recommendations Report Builder findings for this engagement yet. Run the Report Builder to populate this section and set the module order.'}
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

          {hasScores && insight?.score == null && (
            <p className="text-xs text-muted-foreground">
              This module was not scored by the latest diagnostic.
            </p>
          )}
        </div>
      )}

      {!hasScores && (
        <p className="mt-5 border-t border-border pt-4 text-xs text-muted-foreground">
          No completed diagnostic for this engagement, so there is no score or RAG for any module yet.
        </p>
      )}
    </div>
  );
}
