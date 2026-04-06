import { PLAN_SECTIONS } from './sectionConfig';
import type { SBPSection } from '@/store/slices/strategicBusinessPlanReducer';
import { cn } from '@/lib/utils';
import { CheckCircle2, Circle, Loader2, PenLine, AlertCircle } from 'lucide-react';

interface SectionSidebarProps {
  sections: SBPSection[];
  currentIndex: number;
  onSelect: (index: number) => void;
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  pending: <Circle className="w-4 h-4 text-muted-foreground" />,
  drafting: <Loader2 className="w-4 h-4 text-primary animate-spin" />,
  drafted: <PenLine className="w-4 h-4 text-blue-600" />,
  revision_requested: <AlertCircle className="w-4 h-4 text-orange-500" />,
  approved: <CheckCircle2 className="w-4 h-4 text-green-600" />,
};

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pending',
  drafting: 'Drafting...',
  drafted: 'Ready for review',
  revision_requested: 'Revision requested',
  approved: 'Approved',
};

export function SectionSidebar({ sections, currentIndex, onSelect }: SectionSidebarProps) {
  const approvedCount = sections.filter((s) => s.status === 'approved').length;
  const requiredCount = PLAN_SECTIONS.filter((s) => s.required).length;

  return (
    <div className="w-72 flex-shrink-0 border-r overflow-y-auto">
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
          return (
            <button
              key={section.key}
              onClick={() => onSelect(index)}
              className={cn(
                'w-full text-left px-3 py-2.5 rounded-md flex items-start gap-2 transition-colors text-sm',
                isActive ? 'bg-primary/10 text-primary' : 'hover:bg-muted',
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
                  {!config?.required && ' (optional)'}
                </span>
              </span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
