/**
 * POC: File Upload Page
 * This is a standalone POC page, separate from the main application.
 */
import { FileUploadPOC } from '@/components/poc/FileUploadPOC';

export default function FileUploadPOCPage() {
  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">File Upload POC</h1>
        <p className="text-muted-foreground">
          Proof of Concept for file upload with OpenAI Files API integration
        </p>
      </div>
      <FileUploadPOC />
    </div>
  );
}
