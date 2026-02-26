import { useEffect, useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { extractData, setClarificationNotes } from '@/store/slices/strategyWorkbookReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Sparkles, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';

interface ExtractStepProps {
  workbookId: string;
  onComplete: () => void;
  isExtracting: boolean;
}

// Helper function to format section titles
const formatSectionTitle = (key: string): string => {
  return key
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

// Helper function to render data as simple list - one item per line
const renderDataAsList = (value: any, parentKey?: string): React.ReactNode => {
  if (value === null || value === undefined) {
    return (
      <div className="py-1 text-sm text-muted-foreground italic">
        {parentKey ? `${formatSectionTitle(parentKey)}: Not specified` : 'Not specified'}
      </div>
    );
  }

  if (typeof value === 'string') {
    if (!value.trim()) {
      return null;
    }
    return (
      <div className="py-1 text-sm">
        {parentKey ? (
          <>
            <span className="font-medium text-foreground">{formatSectionTitle(parentKey)}: </span>
            <span className="text-foreground">{value}</span>
          </>
        ) : (
          <span className="text-foreground">{value}</span>
        )}
      </div>
    );
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return (
      <div className="py-1 text-base">
        {parentKey ? (
          <>
            <span className="font-medium text-foreground">{formatSectionTitle(parentKey)}: </span>
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
      return (
        <div className="py-1 text-sm text-muted-foreground italic">
          {parentKey ? `${formatSectionTitle(parentKey)}: No items` : 'No items'}
        </div>
      );
    }

    return (
      <div className="space-y-1">
        {value.map((item, index) => {
          if (typeof item === 'object' && item !== null) {
            // For objects in arrays, show each property on its own line
            return (
              <div key={index} className="pl-4 border-l-2 border-muted space-y-1 py-2">
                {Object.entries(item).map(([k, v]) => (
                  <div key={k}>
                    {renderDataAsList(v, k)}
                  </div>
                ))}
              </div>
            );
          } else {
            // Simple array items - show as bullet points
            return (
              <div key={index} className="py-1 text-base pl-4">
                <span className="text-foreground">• {String(item)}</span>
              </div>
            );
          }
        })}
      </div>
    );
  }

  if (typeof value === 'object') {
    // For objects, show each key-value pair on its own line
    return (
      <div className="space-y-1">
        {Object.entries(value).map(([k, v]) => (
          <div key={k}>
            {renderDataAsList(v, k)}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="py-1 text-base text-foreground">
      {parentKey ? `${formatSectionTitle(parentKey)}: ${String(value)}` : String(value)}
    </div>
  );
};

export function ExtractStep({ workbookId, onComplete, isExtracting }: ExtractStepProps) {
  const dispatch = useAppDispatch();
  const { currentWorkbook, error, clarificationNotes } = useAppSelector(
    (state) => state.strategyWorkbook
  );

  // Track which accordion section is open
  const [openSection, setOpenSection] = useState<string | undefined>(undefined);

  const handleExtract = async () => {
    try {
      const result = await dispatch(extractData(workbookId)).unwrap();
      if (result.status === 'ready') {
        // Don't auto-advance, let user review the data first
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to extract data');
    }
  };

  const extractionStatus = currentWorkbook?.status;
  const extractedData = currentWorkbook?.extracted_data;

  // When extracted data becomes available, default to first section
  useEffect(() => {
    if (extractionStatus === 'ready' && extractedData && !openSection) {
      const keys = Object.keys(extractedData);
      if (keys.length > 0) {
        setOpenSection(keys[0]);
      }
    }
  }, [extractionStatus, extractedData, openSection]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Step 2: Extract Strategic Data</CardTitle>
        <CardDescription>
          AI will analyze your uploaded documents and extract strategic information
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">

        {extractionStatus === 'extracting' && (
          <Alert>
            <Loader2 className="h-4 w-4 animate-spin" />
            <AlertDescription>
              Analyzing documents and extracting strategic information. This may take a few minutes...
            </AlertDescription>
          </Alert>
        )}

        {extractionStatus === 'ready' && (
          <Alert className="border-green-500 bg-green-50">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">
              Data extraction completed successfully! Review the extracted data below before generating the workbook.
            </AlertDescription>
          </Alert>
        )}

        {extractionStatus === 'failed' && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Extraction failed. Please try again or check your documents.
            </AlertDescription>
          </Alert>
        )}

        {extractionStatus === 'draft' && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Click the button below to start extracting strategic information from your uploaded documents.
              The AI will identify:
            </p>
            <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1 ml-4">
              <li>Vision, Mission, and Values</li>
              <li>Business goals and market segmentation</li>
              <li>SWOT analysis and PESTEL factors</li>
              <li>Competitor insights and growth opportunities</li>
              <li>Financial targets and strategic priorities</li>
            </ul>
            <Button
              onClick={handleExtract}
              disabled={isExtracting}
              className="w-full"
              size="lg"
            >
              {isExtracting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Extracting...
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-2" />
                  Start Extraction
                </>
              )}
            </Button>
          </div>
        )}

        {extractionStatus === 'ready' && extractedData && (
          <div className="space-y-4">
            {/* If the AI detected ambiguities, show its questions and a clarification text field */}
            {Array.isArray((extractedData as any).clarification_questions) &&
              (extractedData as any).clarification_questions.length > 0 && (
                <div className="space-y-2 p-3 border rounded-md bg-muted/50">
                  <p className="text-sm font-semibold">
                    The AI found some ambiguities and suggests clarifying these points:
                  </p>
                  <ul className="list-decimal list-inside text-sm text-foreground space-y-1 ml-1">
                    {(extractedData as any).clarification_questions.map((q: string, idx: number) => (
                      <li key={idx}>{q}</li>
                    ))}
                  </ul>
                  <p className="text-xs text-muted-foreground">
                    Provide brief answers or clarifications below. The AI will use these only to
                    resolve unclear areas on the next extraction and will not override explicit
                    statements in your documents.
                  </p>
                  <textarea
                    className="mt-1 w-full rounded-md border bg-background p-2 text-sm outline-none focus-visible:ring-1 focus-visible:ring-primary"
                    rows={4}
                    placeholder="Type your answers to the above questions here, then click &quot;Re-run Extraction with Clarifications&quot;."
                    value={clarificationNotes}
                    onChange={(e) => dispatch(setClarificationNotes(e.target.value))}
                  />
                  <div className="flex justify-end">
                    <Button
                      size="sm"
                      variant="default"
                      onClick={handleExtract}
                      disabled={isExtracting}
                    >
                      {isExtracting ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Re-running...
                        </>
                      ) : (
                        'Re-run Extraction with Clarifications'
                      )}
                    </Button>
                  </div>
                </div>
              )}

            <div className="flex items-center justify-between">
              <h4 className="text-lg font-semibold">Extracted Strategic Data</h4>
              <span className="text-sm text-muted-foreground">
                {Object.keys(extractedData).length} sections
              </span>
            </div>

            <Accordion
              type="single"
              collapsible
              className="w-full space-y-2"
              value={openSection}
              onValueChange={(val) => {
                setOpenSection(val || undefined);
              }}
            >
              {Object.entries(extractedData).map(([key, value]) => (
                <AccordionItem 
                  key={key} 
                  value={key} 
                  className="border rounded-md px-4 bg-card"
                >
                  <AccordionTrigger 
                    className="hover:no-underline font-medium py-3 cursor-pointer"
                    onClick={(e) => {
                      e.stopPropagation();
                    }}
                  >
                    {formatSectionTitle(key)}
                  </AccordionTrigger>
                  <AccordionContent className="pt-2 pb-4">
                    <div className="space-y-1">
                      {renderDataAsList(value)}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              ))}
            </Accordion>

            <Button
              onClick={onComplete}
              className="w-full"
              size="lg"
            >
              Continue to Generation
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
