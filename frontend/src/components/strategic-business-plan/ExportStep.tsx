import { useState } from 'react';
import { useAppSelector } from '@/store/hooks';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Download, FileText, Users, Loader2, CheckCircle2, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';

interface ExportStepProps {
  planId: string;
  onComplete: () => void;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export function ExportStep({ planId, onComplete }: ExportStepProps) {
  const { currentPlan } = useAppSelector((s) => s.strategicBusinessPlan);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isDownloadingEmployee, setIsDownloadingEmployee] = useState(false);
  const [includeEmployee, setIncludeEmployee] = useState(false);
  const [mainDownloaded, setMainDownloaded] = useState(false);
  const [employeeDownloaded, setEmployeeDownloaded] = useState(false);

  const clientName = currentPlan?.client_name || 'Client';

  const handleDownload = async (variant: 'main' | 'employee') => {
    const isEmployee = variant === 'employee';
    const setter = isEmployee ? setIsDownloadingEmployee : setIsDownloading;
    setter(true);

    try {
      const token = localStorage.getItem('auth_token');
      const endpoint = isEmployee
        ? `${API_BASE_URL}/api/strategic-business-plan/${planId}/export/employee-docx`
        : `${API_BASE_URL}/api/strategic-business-plan/${planId}/export/docx`;

      const response = await fetch(endpoint, {
        headers: { 'Authorization': `Bearer ${token}` },
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to download document');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const year = new Date().getFullYear();
      link.setAttribute(
        'download',
        isEmployee
          ? `Employee_Strategy_Document_${clientName.replace(/\s+/g, '_')}_${year}.docx`
          : `Strategic_Business_Plan_${clientName.replace(/\s+/g, '_')}_${year}.docx`,
      );
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      if (isEmployee) setEmployeeDownloaded(true);
      else setMainDownloaded(true);

      toast.success(`${isEmployee ? 'Employee strategy document' : 'Strategic Business Plan'} downloaded!`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Download failed');
    } finally {
      setter(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Main Document */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Strategic Business Plan
          </CardTitle>
          <CardDescription>
            Download the complete Strategic Business Plan as a formatted .docx document.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div>
              <p className="font-medium text-sm">
                Strategic_Business_Plan_{clientName.replace(/\s+/g, '_')}_{new Date().getFullYear()}.docx
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Professional .docx with all approved sections, tables, and matrices
              </p>
            </div>
            <Button
              onClick={() => handleDownload('main')}
              disabled={isDownloading}
              variant={mainDownloaded ? 'outline' : 'default'}
            >
              {isDownloading ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : mainDownloaded ? (
                <CheckCircle2 className="w-4 h-4 mr-2 text-green-600" />
              ) : (
                <Download className="w-4 h-4 mr-2" />
              )}
              {mainDownloaded ? 'Downloaded' : 'Download .docx'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Employee Variant Toggle */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="w-5 h-5" />
            Employee Strategy Document (Optional)
          </CardTitle>
          <CardDescription>
            Generate an employee-facing strategy document. Vision, Mission, Values, and Sustainable Competitive Advantage
            will be identical to the main plan. Content will be simplified for an employee audience.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center space-x-2">
            <Switch
              id="employee-variant"
              checked={includeEmployee}
              onCheckedChange={setIncludeEmployee}
            />
            <Label htmlFor="employee-variant">Generate employee-facing variant</Label>
          </div>
          {includeEmployee && (
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div>
                <p className="font-medium text-sm">
                  Employee_Strategy_Document_{clientName.replace(/\s+/g, '_')}_{new Date().getFullYear()}.docx
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                  Simplified strategy document suitable for sharing with employees
                </p>
              </div>
              <Button
                onClick={() => handleDownload('employee')}
                disabled={isDownloadingEmployee}
                variant={employeeDownloaded ? 'outline' : 'default'}
              >
                {isDownloadingEmployee ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : employeeDownloaded ? (
                  <CheckCircle2 className="w-4 h-4 mr-2 text-green-600" />
                ) : (
                  <Download className="w-4 h-4 mr-2" />
                )}
                {employeeDownloaded ? 'Downloaded' : 'Download .docx'}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Continue to Presentation */}
      <div className="flex justify-end">
        <Button variant="outline" onClick={onComplete} size="lg">
          <ArrowRight className="w-4 h-4 mr-2" />
          Continue to Presentation (Optional)
        </Button>
      </div>
    </div>
  );
}
