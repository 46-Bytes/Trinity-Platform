import { useState } from 'react';
import { useAppDispatch } from '@/store/hooks';
import { generateWorkbook } from '@/store/slices/strategyWorkbookReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Download, FileSpreadsheet, Loader2, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';

interface GenerateStepProps {
  workbookId: string;
  extractedData?: Record<string, any>;
  onComplete: () => void;
  onDownload: () => void;
  isGenerating: boolean;
  reviewNotes: string;
  onReviewNotesChange: (notes: string) => void;
}

export function GenerateStep({
  workbookId,
  extractedData,
  onComplete,
  onDownload,
  isGenerating,
  reviewNotes,
  onReviewNotesChange,
}: GenerateStepProps) {
  const dispatch = useAppDispatch();
  const [hasGenerated, setHasGenerated] = useState(false);

  // Helper: format section titles nicely
  const formatSectionTitle = (key: string): string => {
    return key
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  // Helper: detect if a value actually contains any meaningful content
  const hasMeaningfulContent = (value: any): boolean => {
    if (value === null || value === undefined) return false;

    if (typeof value === 'string') return value.trim().length > 0;
    if (typeof value === 'number' || typeof value === 'boolean') return true;

    if (Array.isArray(value)) {
      return value.some((item) => hasMeaningfulContent(item));
    }

    if (typeof value === 'object') {
      return Object.values(value).some((v) => hasMeaningfulContent(v));
    }

    return false;
  };

  // Helper: render extracted data in a readable list format
  const renderDataAsList = (value: any, parentKey?: string): React.ReactNode => {
    if (value === null || value === undefined) {
      // Skip completely empty values; top-level will show a generic message if needed
      return null;
    }

    if (typeof value === 'string') {
      if (!value.trim()) return null;
      return (
        <div className="py-0.5 text-xs">
          {parentKey ? (
            <>
              <span className="font-medium text-foreground">{formatSectionTitle(parentKey)}: </span>
              <span className="text-muted-foreground whitespace-pre-line">{value}</span>
            </>
          ) : (
            <span className="text-muted-foreground whitespace-pre-line">{value}</span>
          )}
        </div>
      );
    }

    if (typeof value === 'number' || typeof value === 'boolean') {
      return (
        <div className="py-0.5 text-xs">
          {parentKey ? (
            <>
              <span className="font-medium text-foreground">{formatSectionTitle(parentKey)}: </span>
              <span className="text-muted-foreground">{String(value)}</span>
            </>
          ) : (
            <span className="text-muted-foreground">{String(value)}</span>
          )}
        </div>
      );
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        return (
          <div className="py-0.5 text-xs text-muted-foreground italic">
            {parentKey ? `${formatSectionTitle(parentKey)}: No items` : 'No items'}
          </div>
        );
      }

      return (
        <div className="space-y-0.5">
          {value.map((item, index) => {
            if (typeof item === 'object' && item !== null) {
              return (
                <div
                  key={index}
                  className="pl-3 border-l border-muted space-y-0.5 py-1"
                >
                  {Object.entries(item).map(([k, v]) => (
                    <div key={k}>{renderDataAsList(v, k)}</div>
                  ))}
                </div>
              );
            }

            return (
              <div key={index} className="py-0.5 text-xs pl-3">
                <span className="text-muted-foreground">• {String(item)}</span>
              </div>
            );
          })}
        </div>
      );
    }

    if (typeof value === 'object') {
      return (
        <div className="space-y-0.5">
          {Object.entries(value).map(([k, v]) => (
            <div key={k}>{renderDataAsList(v, k)}</div>
          ))}
        </div>
      );
    }

    return (
      <div className="py-0.5 text-xs text-muted-foreground">
        {parentKey ? `${formatSectionTitle(parentKey)}: ${String(value)}` : String(value)}
      </div>
    );
  };

  const handleGenerate = async () => {
    try {
      const result = await dispatch(generateWorkbook({ workbookId, reviewNotes })).unwrap();
      // Backend marks workbook as 'completed' when generation finishes
      if (result.status === 'completed') {
        setHasGenerated(true);
        onComplete();
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to generate workbook');
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Step 3: Generate Workbook</CardTitle>
        <CardDescription>
          Review the extracted data and generate your prefilled Excel workbook
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {extractedData && (
          <div className="space-y-4">
            <div>
              <Label htmlFor="review-notes">Review Notes (Optional)</Label>
              <Textarea
                id="review-notes"
                placeholder="Add any notes or adjustments before generating the workbook..."
                value={reviewNotes}
                onChange={(e) => onReviewNotesChange(e.target.value)}
                className="mt-2"
                rows={4}
              />
              <p className="text-xs text-muted-foreground mt-1">
                These notes will be saved with the workbook for reference
              </p>
            </div>

            <div className="p-4 bg-muted rounded-lg">
              <h4 className="text-sm font-medium mb-3">Extracted Data Summary</h4>
              {/* One full-width row per section, each collapsible to show detailed data */}
              <Accordion type="single" collapsible className="w-full space-y-2 text-xs">
                {Object.entries(extractedData).map(([key, value]) => {
                  const count = Array.isArray(value)
                    ? value.length
                    : typeof value === 'object' && value !== null
                      ? Object.keys(value).length
                      : 0;

                  return (
                    <AccordionItem
                      key={key}
                      value={key}
                      className="border rounded bg-background"
                    >
                      <AccordionTrigger className="px-3 py-2 flex items-center justify-between hover:no-underline">
                        <span className="capitalize font-medium truncate pr-3">
                          {formatSectionTitle(key)}
                        </span>
                      </AccordionTrigger>
                      <AccordionContent className="px-3 pb-3 pt-0">
                        <div className="mt-2 space-y-0.5">
                          {hasMeaningfulContent(value) ? (
                            renderDataAsList(value)
                          ) : (
                            <div className="py-0.5 text-xs text-muted-foreground italic">
                              No data extracted for this section.
                            </div>
                          )}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  );
                })}
              </Accordion>
            </div>
          </div>
        )}

        {!hasGenerated && (
          <Button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="w-full"
            size="lg"
          >
            {isGenerating ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Generating Workbook...
              </>
            ) : (
              <>
                <FileSpreadsheet className="w-4 h-4 mr-2" />
                Generate Excel Workbook
              </>
            )}
          </Button>
        )}

        {hasGenerated && (
          <Alert className="border-green-500 bg-green-50">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">
              Workbook generated successfully! You can now download it.
            </AlertDescription>
          </Alert>
        )}

        {hasGenerated && (
          <Button
            onClick={onDownload}
            className="w-full"
            size="lg"
            variant="default"
          >
            <Download className="w-4 h-4 mr-2" />
            Download Strategy Workbook
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

