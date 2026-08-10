import { useAppDispatch } from '@/store/hooks';
import { extractResponsibilities, type RolesMatrix } from '@/store/slices/rolesMatrixReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Loader2, ScanSearch, ArrowRight, ArrowLeft } from 'lucide-react';
import { toast } from 'sonner';

interface ExtractStepProps {
  matrix: RolesMatrix;
  isExtracting: boolean;
  onComplete: () => void;
  onBack: () => void;
}

export function ExtractStep({ matrix, isExtracting, onComplete, onBack }: ExtractStepProps) {
  const dispatch = useAppDispatch();

  const extracted = matrix.extracted_responsibilities;
  const people = extracted?.people || [];
  const unmatched = extracted?.unmatched_notes || [];
  const hasExtraction = people.length > 0;

  const handleExtract = async () => {
    try {
      await dispatch(extractResponsibilities({ matrixId: matrix.id })).unwrap();
      toast.success('Responsibilities extracted');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to extract responsibilities');
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Extract responsibilities</CardTitle>
          <CardDescription>
            Pull the responsibilities for each confirmed role out of the uploaded documents and notes.
            Nothing is added that was not provided.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={handleExtract} disabled={isExtracting} size="lg" className="w-full">
            {isExtracting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Extracting...
              </>
            ) : (
              <>
                <ScanSearch className="w-4 h-4 mr-2" />
                {hasExtraction ? 'Run extraction again' : 'Extract responsibilities'}
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {hasExtraction && (
        <div className="space-y-4">
          {people.map((person, index) => (
            <Card key={`${person.name ?? 'person'}-${index}`}>
              <CardHeader>
                <CardTitle className="text-base">
                  {person.name || 'Unnamed'}
                  {person.role_title && (
                    <span className="text-muted-foreground font-normal"> — {person.role_title}</span>
                  )}
                </CardTitle>
                <CardDescription>
                  {person.responsibilities?.length || 0} responsibilit
                  {(person.responsibilities?.length || 0) === 1 ? 'y' : 'ies'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {(person.responsibilities || []).map((responsibility, rIndex) => (
                    <li
                      key={rIndex}
                      className="flex flex-wrap items-center gap-2 text-sm border-b last:border-b-0 pb-2 last:pb-0"
                    >
                      <span className="flex-1 min-w-[12rem]">{responsibility.description}</span>
                      {responsibility.time && (
                        <Badge variant="secondary" className="font-normal">
                          {responsibility.time}
                        </Badge>
                      )}
                      {responsibility.retain && <Badge variant="outline">Retain</Badge>}
                      {responsibility.gain && <Badge variant="outline">Gain</Badge>}
                      {responsibility.lose && <Badge variant="outline">Lose</Badge>}
                      {responsibility.action && (
                        <span className="text-muted-foreground">{responsibility.action}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}

          {unmatched.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Not attributed to a person</CardTitle>
                <CardDescription>
                  These were found in the source material but could not be matched to a confirmed role.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="list-disc pl-5 space-y-1 text-sm text-muted-foreground">
                  {unmatched.map((note, index) => (
                    <li key={index}>{note}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-3">
        <Button variant="outline" onClick={onBack} className="sm:w-auto w-full">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to inputs
        </Button>
        <Button onClick={onComplete} disabled={!hasExtraction} className="flex-1">
          Continue to matrix
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}
