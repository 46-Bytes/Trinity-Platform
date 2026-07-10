import { cn } from '@/lib/utils';
import type { ProgramGuideModule } from '@/store/slices/programGuideReducer';

interface ProgramGuideStepperProps {
  modules: ProgramGuideModule[];
  activeModuleCode: string | null;
  onSelect: (moduleCode: string) => void;
}

/**
 * Numbered circle stepper for all 13 modules (M0..M12), position-based
 * labels (index in the current effective order, not the module's V-code).
 * Two visual states only - current vs other - no completion tracking.
 */
export function ProgramGuideStepper({ modules, activeModuleCode, onSelect }: ProgramGuideStepperProps) {
  return (
    <div className="flex items-center justify-between w-full overflow-x-auto overflow-y-visible py-1">
      {modules.map((module, index) => {
        const isActive = module.module_code === activeModuleCode;
        const isLast = index === modules.length - 1;
        return (
          <div key={module.module_code} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <button
                type="button"
                onClick={() => onSelect(module.module_code)}
                title={module.title}
                aria-current={isActive ? 'step' : undefined}
                className={cn(
                  'flex h-8 w-8 items-center justify-center rounded-full border text-xs font-semibold transition-all duration-200',
                  isActive
                    ? 'border-primary bg-primary text-primary-foreground shadow-md ring-4 ring-primary/15 scale-110'
                    : 'border-border bg-background text-muted-foreground hover:border-primary/40 hover:text-primary hover:scale-105'
                )}
              >
                {index}
              </button>
              <span className={cn('text-[10px]', isActive ? 'text-primary font-medium' : 'text-muted-foreground')}>
                M{index}
              </span>
            </div>
            {!isLast && <div className="h-px flex-1 min-w-[6px] bg-border self-start mt-4" />}
          </div>
        );
      })}
    </div>
  );
}
