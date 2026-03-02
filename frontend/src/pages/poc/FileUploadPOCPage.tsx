/**
 * POC: File Upload Page
 * This is a standalone POC page, separate from the main application.
 */
import { useParams, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FileUploadPOC } from '@/components/poc/FileUploadPOC';

export default function FileUploadPOCPage() {
  const { engagementId } = useParams<{ engagementId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const stateProjectId = (location.state as { bbaProjectId?: string } | null)?.bbaProjectId;
  const queryProjectId = searchParams.get('project_id');
  const initialProjectId = stateProjectId || queryProjectId || undefined;

  return (
    <div className="container mx-auto py-8 px-2">
      <div className="mb-6">
        <div className="mb-6">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/dashboard/engagements')}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
        </div>
        <h1 className="text-3xl font-bold mb-2">Business Diagnostic Report Builder Tool</h1>
        <p className="text-muted-foreground">
          Use this tool to generate client diagnostic reports’
        </p>
      </div>
      <FileUploadPOC engagementId={engagementId} initialProjectId={initialProjectId} />
    </div>
  );
}
