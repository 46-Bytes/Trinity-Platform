/**
 * Follow-up tools tab for an engagement.
 * Always shows BBA Builder and Strategy Workbook tools.
 * If a completed diagnostic exists, it can optionally be used as context.
 */
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
import { Button } from '@/components/ui/button';
import { BookOpen, FileText, Loader2, Wrench, ClipboardList } from 'lucide-react';
import { useToolLaunchers, type DiagnosticSummary } from '@/hooks/useToolLaunchers';

export interface FollowUpToolsTabProps {
  engagementId: string;
  diagnostics: DiagnosticSummary[];
  diagnosticTags?: Record<string, string>;
  currentUserId?: string | null;
  isAdmin?: boolean;
}

export function FollowUpToolsTab({
  engagementId,
  diagnostics,
  currentUserId,
  isAdmin = false,
}: FollowUpToolsTabProps) {
  const { effectiveDiagnosticId, anyLoading, tools } = useToolLaunchers(
    engagementId,
    diagnostics,
    currentUserId,
    isAdmin
  );

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold flex items-center gap-2">
          <Wrench className="h-5 w-5 text-muted-foreground" />
          AI Tools
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Run AI-powered tools for this engagement.
          {effectiveDiagnosticId && ' A completed diagnostic will be used as context.'}
        </p>
      </div>

      {/* Tool list */}
      <div className="border rounded-lg overflow-hidden divide-y">
        {/* Recommendations Report Builder */}
        <div className="flex items-center justify-between gap-4 p-4 hover:bg-muted/30 transition-colors">
          <div className="flex items-center gap-4 min-w-0">
            <div className="flex-shrink-0 p-2 rounded-md bg-muted">
              <FileText className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <p className="font-medium text-sm">Recommendations Report Builder</p>
              <p className="text-sm text-muted-foreground mt-0.5">
                Generate a Business Benchmark Analysis{effectiveDiagnosticId ? ' from your diagnostic data' : ' for this engagement'}.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="flex-shrink-0"
            disabled={anyLoading}
            onClick={tools.bba.run}
          >
            {tools.bba.loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <FileText className="h-4 w-4 mr-2" />}
            Run
          </Button>
        </div>

        {/* Strategy Workbook Creator */}
        <div className="flex items-center justify-between gap-4 p-4 hover:bg-muted/30 transition-colors">
          <div className="flex items-center gap-4 min-w-0">
            <div className="flex-shrink-0 p-2 rounded-md bg-muted">
              <BookOpen className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <p className="font-medium text-sm">Strategy Workbook Creator</p>
              <p className="text-sm text-muted-foreground mt-0.5">
                Create a strategic planning workbook{effectiveDiagnosticId ? ' based on your diagnostic insights' : ' for this engagement'}.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="flex-shrink-0"
            disabled={anyLoading}
            onClick={tools.strategy_workbook.run}
          >
            {tools.strategy_workbook.loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <BookOpen className="h-4 w-4 mr-2" />}
            Run
          </Button>
        </div>

        {/* Strategic Business Plan */}
        <div className="flex items-center justify-between gap-4 p-4 hover:bg-muted/30 transition-colors">
          <div className="flex items-center gap-4 min-w-0">
            <div className="flex-shrink-0 p-2 rounded-md bg-muted">
              <ClipboardList className="h-5 w-5 text-muted-foreground" />
            </div>
            <div className="min-w-0">
              <p className="font-medium text-sm">Strategic Business Plan</p>
              <p className="text-sm text-muted-foreground mt-0.5">
                Build a professional Strategic Business Plan{effectiveDiagnosticId ? ' from your diagnostic and strategy workbook' : ' for this engagement'}.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="flex-shrink-0"
            disabled={anyLoading}
            onClick={tools.strategic_business_plan.run}
          >
            {tools.strategic_business_plan.loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <ClipboardList className="h-4 w-4 mr-2" />}
            Run
          </Button>
        </div>
      </div>

      {/* Confirmation dialog when a progressed BBA already exists */}
      <AlertDialog open={tools.bba.dialog.open} onOpenChange={(open) => !open && tools.bba.cancelDialog()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{tools.bba.dialog.title}</AlertDialogTitle>
            <AlertDialogDescription>{tools.bba.dialog.description}</AlertDialogDescription>
            <p className="text-sm text-destructive mt-2 font-medium">{tools.bba.dialog.warning}</p>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={tools.bba.cancelDialog}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={tools.bba.continueExisting}>Continue Existing</AlertDialogAction>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={tools.bba.startFresh}
            >
              Start Fresh
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Confirmation dialog when a strategic business plan already exists */}
      <AlertDialog open={tools.strategic_business_plan.dialog.open} onOpenChange={(open) => !open && tools.strategic_business_plan.cancelDialog()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{tools.strategic_business_plan.dialog.title}</AlertDialogTitle>
            <AlertDialogDescription>{tools.strategic_business_plan.dialog.description}</AlertDialogDescription>
            <p className="text-sm text-destructive mt-2 font-medium">{tools.strategic_business_plan.dialog.warning}</p>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={tools.strategic_business_plan.cancelDialog}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={tools.strategic_business_plan.continueExisting}>Continue Existing</AlertDialogAction>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={tools.strategic_business_plan.startFresh}
            >
              Start Fresh
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Confirmation dialog when a strategy workbook already exists */}
      <AlertDialog open={tools.strategy_workbook.dialog.open} onOpenChange={(open) => !open && tools.strategy_workbook.cancelDialog()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{tools.strategy_workbook.dialog.title}</AlertDialogTitle>
            <AlertDialogDescription>{tools.strategy_workbook.dialog.description}</AlertDialogDescription>
            <p className="text-sm text-destructive mt-2 font-medium">{tools.strategy_workbook.dialog.warning}</p>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={tools.strategy_workbook.cancelDialog}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={tools.strategy_workbook.continueExisting}>Continue Existing</AlertDialogAction>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={tools.strategy_workbook.startFresh}
            >
              Start Fresh
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
