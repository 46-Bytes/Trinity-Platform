import { PLAN_SECTIONS } from './sectionConfig';
import type { SBPSection } from '@/store/slices/strategicBusinessPlanReducer';
import { cn } from '@/lib/utils';
import { CheckCircle2, Circle, Loader2, PenLine, AlertCircle, SkipForward, ChevronUp, ChevronDown } from 'lucide-react';

interface SectionSidebarProps {
  sections: SBPSection[];
  currentIndex: number;
  onSelect: (index: number) => void;
  onReorder: (fromIndex: number, toIndex: number) => void;
  isDisabled?: boolean;
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending:            <Circle       className="w-2 h-2 text-muted-foreground" />,
  drafting:           <Loader2      className="w-2 h-2 text-primary animate-spin" />,
  drafted:            <PenLine      className="w-2 h-2 text-blue-600" />,
  revision_requested: <AlertCircle  className="w-2 h-2 text-orange-500" />,
  approved:           <CheckCircle2 className="w-2 h-2 text-green-600" />,
  skipped:            <SkipForward  className="w-2 h-2 text-muted-foreground" />,
};

const STATUS_LABEL: Record<string, string> = {
  pending:            'Pending',
  drafting:           'Drafting...',
  drafted:            'Ready for review',
  revision_requested: 'Revision requested',
  approved:           'Approved',
  skipped:            'Skipped',
};

export function SectionSidebar({ sections, currentIndex, onSelect, onReorder, isDisabled }: SectionSidebarProps) {
  const approvedCount = sections.filter((s) => s.status === 'approved').length;
  const requiredCount = PLAN_SECTIONS.filter((s) => s.required).length;

  return (
    <div className={cn('w-72 flex-shrink-0 border-r overflow-y-auto', isDisabled && 'opacity-50 pointer-events-none')}>
      <div className="p-4 border-b">
        <h3 className="font-semibold text-sm">Plan Sections</h3>
        <p className="text-xs text-muted-foreground mt-1">
          {approvedCount} / {requiredCount} required sections approved
        </p>
        <div className="w-full bg-muted rounded-full h-1.5 mt-2">
          <div
            className="bg-green-500 h-1.5 rounded-full transition-all"
            style={{ width: `${(approvedCount / requiredCount) * 100}%` }}
          />
        </div>
      </div>
      <nav className="p-2">
        {sections.map((section, index) => {
          const config = PLAN_SECTIONS.find((c) => c.key === section.key);
          const isActive = index === currentIndex;
          const isSkipped = section.status === 'skipped';

          return (
            <div key={section.key} className="flex items-stretch gap-1 mb-0.5">
              {/* Reorder buttons */}
              <div className="flex flex-col justify-center gap-0.5 py-1">
                <button
                  onClick={() => onReorder(index, index - 1)}
                  disabled={index === 0}
                  className="p-0.5 rounded hover:bg-muted disabled:opacity-20 disabled:cursor-not-allowed"
                  title="Move up"
                >
                  <ChevronUp className="w-3 h-3 text-muted-foreground" />
                </button>
                <button
                  onClick={() => onReorder(index, index + 1)}
                  disabled={index === sections.length - 1}
                  className="p-0.5 rounded hover:bg-muted disabled:opacity-20 disabled:cursor-not-allowed"
                  title="Move down"
                >
                  <ChevronDown className="w-3 h-3 text-muted-foreground" />
                </button>
              </div>

              {/* Section row */}
              <button
                onClick={() => onSelect(index)}
                className={cn(
                  'flex-1 text-left px-2.5 py-2 rounded-md flex items-start gap-2 transition-colors text-xs',
                  isActive ? 'bg-primary/10 text-primary' : 'hover:bg-muted',
                  isSkipped && 'opacity-50',
                )}
              >
                <span className="mt-0.5 flex-shrink-0">
                  {STATUS_ICON[section.status] || STATUS_ICON.pending}
                </span>
                <span className="flex-1 min-w-0">
                  <span className={cn('block truncate', isActive && 'font-medium')}>
                    {index + 1}. {section.title}
                  </span>
                  <span className="block text-xs text-muted-foreground mt-0.5">
                    {STATUS_LABEL[section.status] || 'Pending'}
                    {!config?.required && section.status !== 'skipped' && ' · optional'}
                  </span>
                </span>
              </button>
            </div>
          );
        })}
      </nav>
    </div>
  );
}
