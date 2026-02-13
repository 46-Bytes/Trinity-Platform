/**
 * POC: File Upload Page
 * This is a standalone POC page, separate from the main application.
 */
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FileUploadPOC } from '@/components/poc/FileUploadPOC';

export default function FileUploadPOCPage() {
  const { engagementId } = useParams<{ engagementId: string }>();
  const navigate = useNavigate();
  
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
        <h1 className="text-3xl font-bold mb-2">BBA Diagnostic Report Tool</h1>
        <p className="text-muted-foreground">
          Proof of Concept for file upload with OpenAI Files API integration
        </p>
      </div>
      <FileUploadPOC engagementId={engagementId} />
    </div>
  );
}
