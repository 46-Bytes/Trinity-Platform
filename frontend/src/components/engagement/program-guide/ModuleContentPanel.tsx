import { BookOpen, ListChecks, Target, Inbox } from 'lucide-react';

import { cn } from '@/lib/utils';
import type { ProgramGuideModule } from '@/store/slices/programGuideReducer';
import { BulletList, NoteBlocks, Prose, ReferenceTable } from './ModulePrimitives';
import {
  SECTION_LABEL_CLASS,
  SOURCE_LABEL_CLASS,
  inputSourceConfig,
  notesForSection,
  ownerAndDuration,
  tablesForSection,
} from './moduleDisplay';

interface ModuleContentPanelProps {
  module: ProgramGuideModule;
}

/**
 * The first half of the authored module card: what the module is for, what it
 * must produce, what it needs to start, and how the advisor prepares.
 *
 * Labelled "static" because it is identical for every client. The distinction
 * from the generated panel above it is the whole reason both carry a source
 * label - an advisor reading a guardrail needs to know it is program policy,
 * not something inferred about this business.
 */
export function ModuleContentPanel({ module }: ModuleContentPanelProps) {
  const preparation = ownerAndDuration(
    module.preparation_summary?.owner,
    module.preparation_summary?.duration
  );
  const inputs = module.required_inputs ?? [];
  const outcomes = module.core_outcomes ?? [];
  const checklist = module.preparation_checklist ?? [];

  return (
    <div className="card-trinity space-y-6 p-6">
      <span className={cn(SOURCE_LABEL_CLASS, 'bg-muted text-muted-foreground')}>
        <BookOpen className="h-3 w-3" />
        Module card · the same for every client
      </span>

      {module.purpose && (
        <section>
          <p className={SECTION_LABEL_CLASS}>
            <Target className="h-3.5 w-3.5" />
            Purpose
          </p>
          <Prose text={module.purpose} />
        </section>
      )}

      {outcomes.length > 0 && (
        <section>
          <p className={SECTION_LABEL_CLASS}>
            <Target className="h-3.5 w-3.5" />
            Core outcomes
          </p>
          <BulletList items={outcomes} />
          <NoteBlocks notes={notesForSection(module.notes, 'core_outcomes')} className="mt-3" />
        </section>
      )}

      {inputs.length > 0 && (
        <section>
          <p className={SECTION_LABEL_CLASS}>
            <Inbox className="h-3.5 w-3.5" />
            Required inputs
          </p>

          <div className="mb-2 flex items-center justify-between border-b border-border pb-2 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
            <span>Input</span>
            <span>Source</span>
          </div>

          <div className="divide-y divide-border/50">
            {inputs.map((input) => {
              const source = inputSourceConfig(input.source);
              return (
                <div key={input.key} className="flex items-start justify-between gap-4 py-2.5">
                  <div className="min-w-0">
                    <p className="text-sm leading-relaxed text-muted-foreground">{input.label}</p>
                    {/*
                      Part A: no module may assume an earlier one has run. Where
                      an input comes from another module, the spec requires a
                      stated fallback - so it is shown, not stored and hidden.
                    */}
                    {input.fallback && (
                      <p className="mt-1 rounded bg-muted/50 px-2 py-1.5 text-xs leading-relaxed text-muted-foreground">
                        <span className="font-semibold">If unavailable: </span>
                        {input.fallback}
                      </p>
                    )}
                  </div>
                  <span className={cn('status-badge flex-shrink-0 whitespace-nowrap', source.className)}>
                    <source.icon className="h-3 w-3" />
                    {input.source}
                    {input.source_note ? ` · ${input.source_note}` : ''}
                  </span>
                </div>
              );
            })}
          </div>

          <NoteBlocks notes={notesForSection(module.notes, 'required_inputs')} className="mt-3" />
        </section>
      )}

      {(checklist.length > 0 || preparation) && (
        <section>
          <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
            <p className={cn(SECTION_LABEL_CLASS, 'mb-0')}>
              <ListChecks className="h-3.5 w-3.5" />
              Preparation
            </p>
            {preparation && <span className="text-xs text-muted-foreground">{preparation}</span>}
          </div>
          <BulletList items={checklist.map((item) => item.text)} />
          <NoteBlocks notes={notesForSection(module.notes, 'preparation')} className="mt-3" />
        </section>
      )}

      {tablesForSection(module.tables, 'business_model_shape').map((table) => (
        <section key={table.key}>
          <ReferenceTable table={table} />
          <NoteBlocks notes={notesForSection(module.notes, 'business_model_shape')} className="mt-3" />
        </section>
      ))}
    </div>
  );
}
