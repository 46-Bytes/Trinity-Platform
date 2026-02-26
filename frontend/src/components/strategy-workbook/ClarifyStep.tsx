import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { setClarificationNotes } from '@/store/slices/strategyWorkbookReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

interface ClarifyStepProps {
  onComplete: () => void;
}

export function ClarifyStep({ onComplete }: ClarifyStepProps) {
  const dispatch = useAppDispatch();
  const { clarificationNotes, clarificationQuestions, isPrechecking } = useAppSelector(
    (state) => state.strategyWorkbook
  );

  const handleContinue = () => {
    onComplete();
  };

  const hasNotes = clarificationNotes.trim().length > 0;
  const hasQuestions = clarificationQuestions && clarificationQuestions.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Clarify Ambiguities</CardTitle>
        <CardDescription>
          The AI has reviewed your documents and found some points that should be clarified before
          extraction.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isPrechecking && !hasQuestions ? (
          <p className="text-sm text-muted-foreground">Reviewing your documents for ambiguities…</p>
        ) : hasQuestions ? (
          <>
            <div className="space-y-2">
              <p className="text-sm font-semibold">
                Please answer these questions so we can extract the data correctly:
              </p>
              <ul className="list-decimal list-inside text-sm text-foreground space-y-1 ml-1">
                {clarificationQuestions.map((q, idx) => (
                  <li key={idx}>{q}</li>
                ))}
              </ul>
            </div>

            <textarea
              className="mt-1 w-full rounded-md border bg-background p-2 text-sm outline-none focus-visible:ring-1 focus-visible:ring-primary"
              rows={4}
              placeholder="Type your answers or clarifications here…"
              value={clarificationNotes}
              onChange={(e) => dispatch(setClarificationNotes(e.target.value))}
            />

            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>
                Your answers will be sent with the extraction and used only to resolve these
                ambiguities.
              </span>
            </div>

            <Button className="w-full" size="lg" onClick={handleContinue}>
              Continue to Extraction
            </Button>
          </>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              No significant ambiguities were detected in your documents. You can proceed directly
              to extraction.
            </p>
            <Button className="w-full" size="lg" onClick={handleContinue}>
              Continue to Extraction
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}


