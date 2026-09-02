import { useState } from 'react';
import {
  BookOpen,
  ChevronDown,
  ClipboardCheck,
  ClipboardList,
  Clock,
  FileText,
  Loader2,
  ShieldAlert,
  Wrench,
  CalendarClock,
  type LucideIcon,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import type { ToolKey } from '@/hooks/useToolLaunchers';
import type { ModuleSession, ProgramGuideModule } from '@/store/slices/programGuideReducer';
import { BulletList, NoteBlocks, Prose, ReferenceTable } from './ModulePrimitives';
import {
  SECTION_LABEL_CLASS,
  SOURCE_LABEL_CLASS,
  isToolPending,
  notesForSection,
  ownerAndDuration,
  tablesForSection,
  unsectionedTables,
} from './moduleDisplay';

const TOOL_ICONS: Record<string, LucideIcon> = {
  diagnostic: ClipboardCheck,
  bba: FileText,
  strategy_workbook: BookOpen,
  strategic_business_plan: ClipboardList,
};

interface ToolLauncher {
  loading: boolean;
  run: () => void;
}

interface ModuleSessionsPanelProps {
  module: ProgramGuideModule;
  tools: Record<ToolKey, ToolLauncher>;
  anyToolLoading: boolean;
  onNavigateToDiagnostic?: () => void;
}

/**
 * The delivery half of the module card: how the sessions run, which tools
 * support them, what happens afterwards, and what the advisor must not do.
 *
 * The agenda is the densest content in the program - V7 alone has three
 * sessions and twenty agenda items - so sessions collapse, with the first open.
 * Collapsible rather than Accordion because an advisor working a multi-session
 * module needs to compare two agendas side by side, which single-open would
 * prevent.
 */
export function ModuleSessionsPanel({
  module,
  tools,
  anyToolLoading,
  onNavigateToDiagnostic,
}: ModuleSessionsPanelProps) {
  const sessions = module.sessions ?? [];
  const recommendedTools = module.recommended_tools ?? [];
  const postSession = module.post_session_actions;
  const betweenSessions = module.between_sessions;
  const guardrails = module.guardrails;

  return (
    <div className="card-trinity space-y-6 p-6">
      <span className={cn(SOURCE_LABEL_CLASS, 'bg-muted text-muted-foreground')}>
        <BookOpen className="h-3 w-3" />
        Module card · the same for every client
      </span>

      {sessions.length > 0 && (
        <section>
          <p className={SECTION_LABEL_CLASS}>
            <Clock className="h-3.5 w-3.5" />
            Sessions
          </p>

          <p className="mb-3 rounded-lg bg-warning/10 px-3 py-2 text-xs leading-relaxed text-warning">
            Times are a guide only. Run the session in whatever shape works with this client.
          </p>

          <div className="space-y-2">
            {sessions.map((session, index) => (
              <SessionBlock
                key={session.key}
                session={session}
                index={index}
                total={sessions.length}
                defaultOpen={index === 0}
              />
            ))}
          </div>

          <NoteBlocks notes={notesForSection(module.notes, 'sessions')} className="mt-3" />
        </section>
      )}

      {betweenSessions && (betweenSessions.items?.length || betweenSessions.owner) && (
        <section>
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <p className={cn(SECTION_LABEL_CLASS, 'mb-0')}>
              <CalendarClock className="h-3.5 w-3.5" />
              Between sessions
            </p>
            {ownerAndDuration(betweenSessions.owner, betweenSessions.duration) && (
              <span className="text-xs text-muted-foreground">
                {ownerAndDuration(betweenSessions.owner, betweenSessions.duration)}
              </span>
            )}
          </div>
          <BulletList items={betweenSessions.items ?? []} />
          <NoteBlocks notes={notesForSection(module.notes, 'between_sessions')} className="mt-3" />
        </section>
      )}

      {recommendedTools.length > 0 && (
        <section>
          <p className={SECTION_LABEL_CLASS}>
            <Wrench className="h-3.5 w-3.5" />
            Trinity tools
          </p>

          <div className="space-y-2">
            {recommendedTools.map((tool) => {
              const ToolIcon = TOOL_ICONS[tool.tool_key] ?? Wrench;
              const pending = isToolPending(tool.status);
              const launcher = tool.tool_key === 'diagnostic' ? null : tools[tool.tool_key as ToolKey];

              return (
                <div
                  key={tool.tool_key}
                  className="flex items-center justify-between gap-3 rounded-lg bg-primary/5 px-3 py-2.5"
                >
                  <div className="flex min-w-0 items-start gap-2.5">
                    <ToolIcon className="mt-0.5 h-4 w-4 flex-shrink-0 text-primary" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium">{tool.label}</p>
                      {tool.when && (
                        <p className="text-xs text-muted-foreground">
                          Used {tool.when} · standalone, usable outside this engagement
                        </p>
                      )}
                    </div>
                  </div>

                  {/*
                    A tool with no launcher used to render as nothing at all, so
                    six modules silently lost a tool their own content names. The
                    `status` field exists precisely so the card can say "not
                    built yet" instead of dropping it.
                  */}
                  {pending ? (
                    <span className="status-badge flex-shrink-0 whitespace-nowrap bg-muted text-muted-foreground">
                      Not built yet
                    </span>
                  ) : tool.tool_key === 'diagnostic' ? (
                    <Button variant="outline" size="sm" onClick={() => onNavigateToDiagnostic?.()}>
                      Open
                    </Button>
                  ) : launcher ? (
                    <Button variant="outline" size="sm" disabled={anyToolLoading} onClick={launcher.run}>
                      {launcher.loading ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : null}
                      Run
                    </Button>
                  ) : (
                    <span className="status-badge flex-shrink-0 whitespace-nowrap bg-muted text-muted-foreground">
                      No launcher
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          <NoteBlocks notes={notesForSection(module.notes, 'recommended_tools')} className="mt-3" />
        </section>
      )}

      {postSession && (postSession.items?.length || postSession.owner) && (
        <section>
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <p className={cn(SECTION_LABEL_CLASS, 'mb-0')}>
              <ClipboardList className="h-3.5 w-3.5" />
              Post-session actions
            </p>
            {ownerAndDuration(postSession.owner, postSession.duration) && (
              <span className="text-xs text-muted-foreground">
                {ownerAndDuration(postSession.owner, postSession.duration)}
              </span>
            )}
          </div>
          <BulletList items={postSession.items ?? []} />
          <NoteBlocks notes={notesForSection(module.notes, 'post_session_actions')} className="mt-3" />
        </section>
      )}

      {guardrails?.must_not && guardrails.must_not.length > 0 && (
        <section className="rounded-xl bg-destructive/5 p-4">
          <p className={cn(SECTION_LABEL_CLASS, 'text-destructive')}>
            <ShieldAlert className="h-3.5 w-3.5" />
            Guardrails
          </p>
          <ul className="space-y-2">
            {guardrails.must_not.map((item, index) => (
              <li key={index} className="relative pl-4 text-sm leading-relaxed text-muted-foreground">
                <span className="absolute left-0 top-[0.7rem] h-0.5 w-2.5 rounded-full bg-destructive" />
                <span className="font-medium text-foreground">Advisors must not</span> {item}
              </li>
            ))}
          </ul>
          {guardrails.note && <Prose text={guardrails.note} className="mt-3" />}
          <NoteBlocks notes={notesForSection(module.notes, 'guardrails')} className="mt-3" />
        </section>
      )}

      {/* Any matrix with no named section still gets rendered rather than lost. */}
      {unsectionedTables(module.tables).map((table) => (
        <ReferenceTable key={table.key} table={table} />
      ))}
      {tablesForSection(module.tables, 'sessions').map((table) => (
        <ReferenceTable key={table.key} table={table} />
      ))}
    </div>
  );
}

function SessionBlock({
  session,
  index,
  total,
  defaultOpen,
}: {
  session: ModuleSession;
  index: number;
  total: number;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const meta = [session.duration, session.format].filter(Boolean).join(' · ');

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="overflow-hidden rounded-lg border border-border">
        <CollapsibleTrigger className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50">
          <span className="text-sm font-semibold">
            {total > 1 ? `Session ${index + 1}: ` : ''}
            {session.title}
          </span>
          <span className="flex flex-shrink-0 items-center gap-2 text-xs text-muted-foreground">
            {meta}
            <ChevronDown className={cn('h-4 w-4 transition-transform', open && 'rotate-180')} />
          </span>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="border-t border-border px-4 py-3">
            {session.note && <Prose text={session.note} className="mb-3" />}

            <ol className="divide-y divide-border/50">
              {session.agenda.map((item, agendaIndex) => (
                <li key={item.key} className="flex gap-4 py-3 first:pt-0 last:pb-0">
                  <span className="w-20 flex-shrink-0 pt-0.5 text-right text-[11px] font-semibold text-muted-foreground">
                    {item.duration}
                  </span>

                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-foreground">
                      {agendaIndex + 1}. {item.title}
                    </p>

                    {item.intro && <Prose text={item.intro} className="mt-1" />}
                    {item.detail && <Prose text={item.detail} className="mt-1" />}

                    {/*
                      Term/definition pairs, used where a step branches by
                      business-model shape. Not questions, so not rendered as
                      them - the advisor picks one branch and ignores the rest.
                    */}
                    {item.options && item.options.length > 0 && (
                      <dl className="mt-2 space-y-1.5 rounded-lg bg-muted/40 px-3 py-2.5">
                        {item.options.map((option) => (
                          <div key={option.key}>
                            <dt className="inline text-sm font-semibold text-foreground">{option.term}: </dt>
                            <dd className="inline text-sm leading-relaxed text-muted-foreground">
                              {option.definition}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    )}

                    {item.questions && item.questions.length > 0 && (
                      <div className="mt-2 space-y-3 rounded-lg bg-muted/40 px-3 py-2.5">
                        {item.questions.map((group, groupIndex) => (
                          <div key={groupIndex}>
                            {/* Only a handful of groups carry a label; the rest are simply "Questions". */}
                            <p className="mb-1 text-[10px] font-bold uppercase tracking-wider text-accent">
                              {group.label || 'Questions'}
                            </p>
                            <ul className="space-y-1">
                              {group.items.map((question, questionIndex) => (
                                <li
                                  key={questionIndex}
                                  className="text-sm italic leading-relaxed text-muted-foreground"
                                >
                                  {question}
                                </li>
                              ))}
                            </ul>
                          </div>
                        ))}
                      </div>
                    )}

                    {item.note && (
                      <p className="mt-2 border-l-2 border-primary/40 py-1 pl-3 text-sm leading-relaxed text-muted-foreground whitespace-pre-line">
                        {item.note}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}
