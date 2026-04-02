import { useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { generatePresentation } from '@/store/slices/strategicBusinessPlanReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, Presentation, Download, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';

interface PresentationStepProps {
  planId: string;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function PresentationStep({ planId }: PresentationStepProps) {
  const dispatch = useAppDispatch();
  const { currentPlan, isGeneratingPresentation } = useAppSelector((s) => s.strategicBusinessPlan);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  const slides = currentPlan?.presentation_slides;
  const clientName = currentPlan?.client_name || 'Client';

  const handleGenerate = () => {
    dispatch(generatePresentation(planId));
  };

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(
        `${API_BASE_URL}/api/strategic-business-plan/${planId}/presentation/export`,
        { headers: { 'Authorization': `Bearer ${token}` }, credentials: 'include' },
      );
      if (!response.ok) throw new Error('Failed to download presentation');

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Strategic_Business_Plan_Presentation_${clientName.replace(/\s+/g, '_')}.pptx`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      setDownloaded(true);
      toast.success('Presentation downloaded!');
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Download failed');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Presentation className="w-5 h-5" />
          Presentation Generator (Optional)
        </CardTitle>
        <CardDescription>
          Generate a PowerPoint presentation summarising the Strategic Business Plan.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!slides ? (
          <div className="flex flex-col items-center py-8 space-y-4">
            {isGeneratingPresentation ? (
              <>
                <Loader2 className="w-10 h-10 animate-spin text-primary" />
                <p className="text-muted-foreground">Generating presentation slides...</p>
              </>
            ) : (
              <>
                <p className="text-muted-foreground text-center max-w-md">
                  Click below to generate a presentation from the approved Strategic Business Plan.
                </p>
                <Button onClick={handleGenerate} size="lg">
                  <Presentation className="w-4 h-4 mr-2" />
                  Generate Presentation
                </Button>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-600" />
              <p className="font-medium text-sm">
                Presentation generated ({(slides as any)?.slides?.length || 0} slides)
              </p>
            </div>
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <p className="font-medium text-sm">
                  Strategic_Business_Plan_Presentation_{clientName.replace(/\s+/g, '_')}.pptx
                </p>
              </div>
              <Button
                onClick={handleDownload}
                disabled={isDownloading}
                variant={downloaded ? 'outline' : 'default'}
              >
                {isDownloading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : downloaded ? (
                  <CheckCircle2 className="w-4 h-4 mr-2 text-green-600" />
                ) : (
                  <Download className="w-4 h-4 mr-2" />
                )}
                {downloaded ? 'Downloaded' : 'Download .pptx'}
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
