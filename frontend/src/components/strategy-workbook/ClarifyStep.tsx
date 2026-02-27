import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { setClarificationAnswer } from '@/store/slices/strategyWorkbookReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2 } from 'lucide-react';

interface ClarifyStepProps {
  onComplete: () => void;
}

export function ClarifyStep({ onComplete }: ClarifyStepProps) {
  const dispatch = useAppDispatch();
  const { clarificationAnswers, clarificationQuestions, isPrechecking } = useAppSelector(
    (state) => state.strategyWorkbook
  );

  const handleContinue = () => {
    onComplete();
  };

  const hasQuestions = clarificationQuestions && clarificationQuestions.length > 0;
  const allAnswered = hasQuestions && clarificationQuestions.every(
    (_, idx) => (clarificationAnswers[idx] || '').trim().length > 0
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {isPrechecking ? 'Reviewing Documents' : 'Clarify Ambiguities'}
        </CardTitle>
        <CardDescription>
          {isPrechecking
            ? 'The AI is reviewing your documents for ambiguities. This may take a moment...'
            : hasQuestions
              ? 'The AI has reviewed your documents and found some points that should be clarified before extraction.'
              : 'No significant ambiguities were detected in your documents.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isPrechecking ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Analyzing your documents for potential ambiguities...
          </div>
        ) : hasQuestions ? (
          <>
            <p className="text-sm font-semibold">
              Please answer these questions so we can extract the data correctly:
            </p>

            <div className="space-y-4">
              {clarificationQuestions.map((q, idx) => (
                <div key={idx} className="space-y-1.5">
                  <label className="text-sm font-medium text-foreground">
                    {idx + 1}. {q}
                  </label>
                  <textarea
                    className="w-full rounded-md border bg-background p-2 text-sm outline-none focus-visible:ring-1 focus-visible:ring-primary"
                    rows={2}
                    placeholder="Type your answer here…"
                    value={clarificationAnswers[idx] || ''}
                    onChange={(e) => dispatch(setClarificationAnswer({ index: idx, value: e.target.value }))}
                  />
                </div>
              ))}
            </div>

            <div className="text-xs text-muted-foreground">
              Your answers will be sent with the extraction and used only to resolve these
              ambiguities.
            </div>

            <Button className="w-full" size="lg" onClick={handleContinue} disabled={!allAnswered}>
              Continue to Extraction
            </Button>
          </>
        ) : (
          <>
            <p className="text-sm text-muted-foreground">
              You can proceed directly to extraction.
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


