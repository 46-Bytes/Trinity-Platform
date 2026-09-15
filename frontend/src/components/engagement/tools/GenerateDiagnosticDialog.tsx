import { useEffect, useState } from 'react';
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

export type DiagnosticType = 'value_builder' | 'sale_ready';

const DIAGNOSTIC_TYPE_LABELS: Record<DiagnosticType, string> = {
  value_builder: 'Value Builder',
  sale_ready: 'Sale Ready',
};

interface GenerateDiagnosticDialogProps {
  open: boolean;
  /** The engagement's type when already set; null asks for it first. */
  knownType: DiagnosticType | null;
  isSubmitting: boolean;
  onCancel: () => void;
  onConfirm: (type: DiagnosticType) => void;
}

export function GenerateDiagnosticDialog({
  open,
  knownType,
  isSubmitting,
  onCancel,
  onConfirm,
}: GenerateDiagnosticDialogProps) {
  const [step, setStep] = useState<'type' | 'confirm'>(knownType ? 'confirm' : 'type');
  const [selectedType, setSelectedType] = useState<DiagnosticType | null>(knownType);

  // Start fresh each time the dialog opens.
  useEffect(() => {
    if (open) {
      setStep(knownType ? 'confirm' : 'type');
      setSelectedType(knownType);
    }
  }, [open, knownType]);

  const handleOpenChange = (next: boolean) => {
    if (!next && !isSubmitting) onCancel();
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        {step === 'type' ? (
          <>
            <AlertDialogHeader>
              <AlertDialogTitle>Which diagnostic would you like to create?</AlertDialogTitle>
              <AlertDialogDescription>
                Your choice also becomes this engagement's type.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <RadioGroup
              value={selectedType ?? ''}
              onValueChange={(value) => setSelectedType(value as DiagnosticType)}
              className="gap-2"
            >
              {(Object.keys(DIAGNOSTIC_TYPE_LABELS) as DiagnosticType[]).map((type) => (
                <Label
                  key={type}
                  htmlFor={`diagnostic-type-${type}`}
                  className={cn(
                    'flex cursor-pointer items-center gap-3 rounded-md border p-3 font-normal transition-colors hover:border-muted-foreground/30',
                    selectedType === type && 'border-primary ring-1 ring-primary/40'
                  )}
                >
                  <RadioGroupItem value={type} id={`diagnostic-type-${type}`} />
                  <span className="text-sm font-medium">{DIAGNOSTIC_TYPE_LABELS[type]}</span>
                </Label>
              ))}
            </RadioGroup>
            <AlertDialogFooter>
              <Button type="button" variant="outline" onClick={onCancel}>
                Cancel
              </Button>
              <Button type="button" onClick={() => setStep('confirm')} disabled={!selectedType}>
                Continue
              </Button>
            </AlertDialogFooter>
          </>
        ) : (
          <>
            <AlertDialogHeader>
              <AlertDialogTitle>Generate diagnostic</AlertDialogTitle>
              <AlertDialogDescription>
                Are you sure you want to generate the{' '}
                <span className="font-semibold">
                  {selectedType ? DIAGNOSTIC_TYPE_LABELS[selectedType] : ''}
                </span>{' '}
                diagnostic?
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <Button type="button" variant="outline" onClick={onCancel} disabled={isSubmitting}>
                Cancel
              </Button>
              <Button
                type="button"
                onClick={() => selectedType && onConfirm(selectedType)}
                disabled={isSubmitting || !selectedType}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                    Generating...
                  </>
                ) : (
                  'Confirm & Generate'
                )}
              </Button>
            </AlertDialogFooter>
          </>
        )}
      </AlertDialogContent>
    </AlertDialog>
  );
}
