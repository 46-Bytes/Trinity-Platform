import { CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Loader2,
  ArrowRight,
  Target,
  ListChecks,
  Wrench,
  Package,
  FileText,
  BookOpen,
  ClipboardList,
  ClipboardCheck,
  type LucideIcon,
} from 'lucide-react';
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
import { cn } from '@/lib/utils';
import { useToolLaunchers, type DiagnosticSummary, type ToolKey } from '@/hooks/useToolLaunchers';
import type { ProgramGuideModule } from '@/store/slices/programGuideReducer';

interface ModuleCardProps {
  module: ProgramGuideModule;
  nextModule?: ProgramGuideModule;
  engagementId: string;
  diagnostics: DiagnosticSummary[];
  currentUserId?: string | null;
  isAdmin?: boolean;
  onNavigateToDiagnostic?: () => void;
  onGoToNext?: () => void;
}

const SECTION_LABEL_CLASS = 'flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-primary mb-2';

const TOOL_ICONS: Record<string, LucideIcon> = {
  diagnostic: ClipboardCheck,
  bba: FileText,
  strategy_workbook: BookOpen,
  strategic_business_plan: ClipboardList,
};

export function ModuleCard({
  module,
  nextModule,
  engagementId,
  diagnostics,
  currentUserId,
  isAdmin = false,
  onNavigateToDiagnostic,
  onGoToNext,
}: ModuleCardProps) {
  const { anyLoading, tools } = useToolLaunchers(engagementId, diagnostics, currentUserId, isAdmin);

  const recommendedTools = module.recommended_tools || [];

  return (
    <div className="card-trinity overflow-hidden">
      <CardContent className="space-y-5 pt-6">
        {module.purpose && (
          <div>
            <p className={SECTION_LABEL_CLASS}>
              <Target className="h-3.5 w-3.5" />
              Purpose
            </p>
            <p className="text-sm text-muted-foreground">{module.purpose}</p>
          </div>
        )}

        {module.preparation_checklist && module.preparation_checklist.length > 0 && (
          <div>
            <p className={SECTION_LABEL_CLASS}>
              <ListChecks className="h-3.5 w-3.5" />
              Preparation
            </p>
            <ul className="space-y-1.5">
              {module.preparation_checklist.map((item) => (
                <li key={item.key} className="flex items-start gap-2 text-sm">
                  <Checkbox disabled checked={false} className="mt-0.5" />
                  <span>{item.text}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {recommendedTools.length > 0 && (
          <div>
            <p className={SECTION_LABEL_CLASS}>
              <Wrench className="h-3.5 w-3.5" />
              Trinity Tools to Use
            </p>
            <div className="space-y-2">
              {recommendedTools.map((tool) => {
                const toolKey = tool.tool_key as ToolKey | 'diagnostic';
                const ToolIcon = TOOL_ICONS[tool.tool_key] ?? Wrench;
                if (toolKey === 'diagnostic') {
                  return (
                    <div
                      key={tool.tool_key}
                      className="flex items-center justify-between gap-3 rounded-md bg-primary/5 px-3 py-2 transition-colors hover:bg-primary/10"
                    >
                      <span className="text-sm flex items-center gap-2">
                        <ToolIcon className="h-4 w-4 text-primary flex-shrink-0" />
                        {tool.label}
                      </span>
                      <Button variant="outline" size="sm" onClick={() => onNavigateToDiagnostic?.()}>
                        Open
                      </Button>
                    </div>
                  );
                }
                const launcher = tools[toolKey as ToolKey];
                if (!launcher) return null;
                return (
                  <div
                    key={tool.tool_key}
                    className="flex items-center justify-between gap-3 rounded-md bg-primary/5 px-3 py-2 transition-colors hover:bg-primary/10"
                  >
                    <span className="text-sm flex items-center gap-2">
                      <ToolIcon className="h-4 w-4 text-primary flex-shrink-0" />
                      {tool.label}
                    </span>
                    <Button variant="outline" size="sm" disabled={anyLoading} onClick={launcher.run}>
                      {launcher.loading ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-2" /> : null}
                      Run
                    </Button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {module.deliverables && module.deliverables.length > 0 && (
          <div>
            <p className={SECTION_LABEL_CLASS}>
              <Package className="h-3.5 w-3.5" />
              Deliverables
            </p>
            <div className="flex flex-wrap gap-2">
              {module.deliverables.map((d) => (
                <Badge key={d} variant="secondary" className="font-normal rounded-full bg-success/10 text-success hover:bg-success/10">
                  {d}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>

      {nextModule && (
        <button
          type="button"
          onClick={() => onGoToNext?.()}
          className={cn(
            'w-full border-t bg-primary/5 px-6 py-3 flex items-center justify-between',
            'transition-colors hover:bg-primary/10 text-left'
          )}
        >
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Next module</p>
            <p className="text-sm font-medium">{nextModule.title}</p>
          </div>
          <span className="text-sm font-medium text-primary flex items-center gap-1">
            Open
            <ArrowRight className="h-3.5 w-3.5" />
          </span>
        </button>
      )}

      {(['bba', 'strategy_workbook', 'strategic_business_plan'] as ToolKey[]).map((key) => (
        <AlertDialog key={key} open={tools[key].dialog.open} onOpenChange={(open) => !open && tools[key].cancelDialog()}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{tools[key].dialog.title}</AlertDialogTitle>
              <AlertDialogDescription>{tools[key].dialog.description}</AlertDialogDescription>
              <p className="text-sm text-destructive mt-2 font-medium">{tools[key].dialog.warning}</p>
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
