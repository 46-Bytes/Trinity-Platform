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
import { WORKBOOK_SECTION_ORDER } from './sectionConfig';

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
      const displayValue = value.replace(/\\n/g, '\n');
      return (
        <div className="py-1 text-sm">
          {parentKey ? (
            <>
              <span className="font-bold text-foreground">{formatSectionTitle(parentKey)}: </span>
              <span className="text-foreground whitespace-pre-line">{displayValue}</span>
            </>
          ) : (
            <span className="text-foreground whitespace-pre-line">{displayValue}</span>
          )}
        </div>
      );
    }

    if (typeof value === 'number' || typeof value === 'boolean') {
      return (
        <div className="py-1 text-sm">
          {parentKey ? (
            <>
              <span className="font-bold text-foreground">{formatSectionTitle(parentKey)}: </span>
              <span className="text-foreground">{String(value)}</span>
            </>
          ) : (
            <span className="text-foreground">{String(value)}</span>
          )}
        </div>
      );
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        return null;
      }

      return (
        <div className="space-y-1">
          {parentKey && (
            <div className="py-1 text-sm font-bold text-foreground">
              {formatSectionTitle(parentKey)}:
            </div>
          )}
          {value.map((item, index) => {
            if (typeof item === 'object' && item !== null) {
              return (
                <div
                  key={index}
                  className="pl-4 border-l-2 border-muted space-y-1 py-1.5"
                >
                  {Object.entries(item).map(([k, v]) => (
                    <div key={k}>{renderDataAsList(v, k)}</div>
                  ))}
                </div>
              );
            }

            return (
              <div key={index} className="py-0.5 text-sm pl-4">
                <span className="text-foreground">• {String(item)}</span>
              </div>
            );
          })}
        </div>
      );
    }

    if (typeof value === 'object') {
      return (
        <div className="space-y-1">
          {Object.entries(value).map(([k, v]) => (
            <div key={k}>{renderDataAsList(v, k)}</div>
          ))}
        </div>
      );
    }

    return (
      <div className="py-1 text-sm text-foreground">
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

            <div className="p-5 bg-muted rounded-lg">
              <h4 className="text-base font-semibold mb-4">Extracted Data Summary</h4>
              {/* One full-width row per section, each collapsible to show detailed data */}
              <Accordion type="single" collapsible className="w-full space-y-3">
                {WORKBOOK_SECTION_ORDER
                  .filter(({ key }) => extractedData[key] != null && hasMeaningfulContent(extractedData[key]))
                  .map(({ key, label }) => {
                    const value = extractedData[key];
                    return (
                      <AccordionItem
                        key={key}
                        value={key}
                        className="border rounded-md bg-background"
                      >
                        <AccordionTrigger className="px-4 py-3 flex items-center justify-between hover:no-underline">
                          <span className="font-semibold text-base text-foreground truncate pr-3">
                            {label}
                          </span>
                        </AccordionTrigger>
                        <AccordionContent className="px-4 pb-4 pt-0">
                          <div className="mt-2 space-y-1">
                            {hasMeaningfulContent(value) ? (
                              renderDataAsList(value)
                            ) : (
                              <div className="py-1 text-sm text-muted-foreground italic">
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

