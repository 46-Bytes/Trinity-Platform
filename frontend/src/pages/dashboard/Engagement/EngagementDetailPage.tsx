import { useParams, useNavigate } from 'react-router-dom';
import { useEffect, useState, useMemo } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from '@/components/ui/button';
import { ToolSurvey } from '@/components/engagement/tools/ToolSurvey';
import { EngagementChatbot } from '@/components/engagement/chatbot';
import { GeneratedFilesList } from '@/components/engagement/overview';
import type { GeneratedFileProps } from '@/components/engagement/overview';
import { TasksList } from '@/components/engagement/tasks';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface FileMetadata {
  file_name: string;
  file_type: string;
  file_size?: number;
  relative_path?: string;
  media_id?: string;
  openai_file_id?: string;
  question_field_name?: string;
}

export default function EngagementDetailPage() {
  const { engagementId } = useParams<{ engagementId: string }>();
  const navigate = useNavigate();
  const [diagnostics, setDiagnostics] = useState<any[]>([]);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);

  // Fetch diagnostics for this engagement
  useEffect(() => {
    if (!engagementId) return;

    const fetchDiagnostics = async () => {
      setIsLoadingFiles(true);
      try {
        const token = localStorage.getItem('auth_token');
        if (!token) return;

        const response = await fetch(`${API_BASE_URL}/api/diagnostics/engagement/${engagementId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data = await response.json();
          setDiagnostics(Array.isArray(data) ? data : []);
        }
      } catch (error) {
        console.error('Failed to fetch diagnostics:', error);
      } finally {
        setIsLoadingFiles(false);
      }
    };

    fetchDiagnostics();
  }, [engagementId]);

  // Extract files from diagnostic responses and completed reports
  const files: GeneratedFileProps[] = useMemo(() => {
    const extractedFiles: GeneratedFileProps[] = [];

    diagnostics.forEach((diagnostic) => {
      // Add completed diagnostic report PDF if diagnostic is completed
      if (diagnostic.status === 'completed') {
        const reportFileName = `Diagnostic Report - ${new Date(diagnostic.completed_at || diagnostic.updated_at).toLocaleDateString()}.pdf`;
        extractedFiles.push({
          id: `diagnostic-report-${diagnostic.id}`,
          name: reportFileName,
          type: 'pdf',
          generatedAt: new Date(diagnostic.completed_at || diagnostic.updated_at),
          generatedBy: undefined,
          size: undefined, // Report is generated on-demand, size unknown
          toolType: 'diagnostic',
          diagnosticId: diagnostic.id, // Store diagnostic ID for download
        });
      }

      // Extract uploaded files from user_responses
      const userResponses = diagnostic.user_responses || {};
      
      // Iterate through all response fields
      Object.entries(userResponses).forEach(([fieldName, fieldValue]) => {
        // Handle both array and single file metadata
        const fileMetadatas: FileMetadata[] = Array.isArray(fieldValue) 
          ? fieldValue 
          : fieldValue ? [fieldValue] : [];

        fileMetadatas.forEach((fileMeta: any) => {
          // Check if this is a file metadata object (has file_name)
          if (fileMeta && typeof fileMeta === 'object' && fileMeta.file_name) {
            // Extract file extension to determine type
            const fileName = fileMeta.file_name || '';
            const extension = fileName.split('.').pop()?.toLowerCase() || 'txt';
            
            // Map extension to file type
            let fileType: 'pdf' | 'docx' | 'xlsx' | 'pptx' | 'txt' = 'txt';
            if (extension === 'pdf') fileType = 'pdf';
            else if (['doc', 'docx'].includes(extension)) fileType = 'docx';
            else if (['xls', 'xlsx'].includes(extension)) fileType = 'xlsx';
            else if (['ppt', 'pptx'].includes(extension)) fileType = 'pptx';

            // Format file size
            const fileSize = fileMeta.file_size 
              ? fileMeta.file_size > 1024 * 1024 
                ? `${(fileMeta.file_size / (1024 * 1024)).toFixed(1)} MB`
                : `${(fileMeta.file_size / 1024).toFixed(0)} KB`
              : undefined;

            extractedFiles.push({
              id: fileMeta.media_id || `${diagnostic.id}-${fieldName}-${fileName}`,
              name: fileName,
              type: fileType,
              generatedAt: new Date(diagnostic.created_at || diagnostic.updated_at),
              generatedBy: undefined, // Could fetch user name if needed
              size: fileSize,
              toolType: 'diagnostic',
              relativePath: fileMeta.relative_path, // Store for download
            });
          }
        });
      });
    });

    // Sort by date (newest first)
    return extractedFiles.sort((a, b) => b.generatedAt.getTime() - a.generatedAt.getTime());
  }, [diagnostics]);

  const handleDownload = async (fileId: string) => {
    // Find the file to get its metadata
    const file = files.find(f => f.id === fileId);
    if (!file) {
      toast.error('File not found');
      return;
    }

    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        toast.error('Not authenticated');
        return;
      }

      // Show loading toast
      const loadingToast = toast.loading('Preparing download...');

      // Check if this is a diagnostic report (has diagnosticId)
      if (file.diagnosticId) {
        // Download diagnostic report PDF
        const response = await fetch(`${API_BASE_URL}/api/diagnostics/${file.diagnosticId}/download`, {
          headers: {
            'Authorization': `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          const errorText = await response.text();
          toast.dismiss(loadingToast);
          toast.error(`Failed to download report: ${errorText || 'Unexpected error'}`);
          return;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const disposition = response.headers.get('Content-Disposition') || '';
        const match = disposition.match(/filename="(.+)"/);
        const filename = match?.[1] || file.name;

        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        toast.dismiss(loadingToast);
        toast.success(`Downloaded ${file.name}`);
      } else if (file.relativePath) {
        // Download uploaded file using relative path
        // TODO: Implement when backend download endpoint is available
        toast.dismiss(loadingToast);
        toast.info('File download will be available soon');
        console.log('Download requested for uploaded file:', file.name, file.relativePath);
      } else {
        toast.dismiss(loadingToast);
        toast.error('Download not available for this file');
        console.error('No download method available for file:', file);
      }
    } catch (error) {
      toast.error('Failed to download file');
      console.error('Error downloading file:', error);
    }
  };

  if (!engagementId) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Engagement not found</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Engagement Details</h1>
        <p className="text-muted-foreground mt-1">Manage your client engagement</p>
      </div>
      
      <Tabs defaultValue="overview" className="w-full">
        <div className="flex items-center gap-4 mb-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/dashboard/engagements')}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
          <TabsList className="grid w-fit grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="tasks">Tasks</TabsTrigger>
            <TabsTrigger value="diagnostic">Diagnostic</TabsTrigger>
            <TabsTrigger value="chatbot">Chat Bot</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="overview" className="mt-6">
          <div className="space-y-6">
            {/* Engagement Summary Card */}
            <div className="card-trinity p-6">
              <h2 className="text-xl font-semibold mb-4">Engagement Overview</h2>
              <p className="text-muted-foreground">
                Engagement overview and details will be displayed here.
              </p>
              {/* TODO: Add engagement overview content */}
            </div>

            {/* Generated Files Section */}
            <div className="card-trinity p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">Generated Files</h2>
                {!isLoadingFiles && (
                  <span className="text-sm text-muted-foreground">
                    {files.length} file{files.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
              {isLoadingFiles ? (
                <div className="text-center py-8 text-muted-foreground">Loading files...</div>
              ) : (
                <GeneratedFilesList files={files} onDownload={handleDownload} />
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="tasks" className="mt-6">
          <div className="card-trinity p-6">
            <TasksList engagementId={engagementId} />
          </div>
        </TabsContent>

        <TabsContent value="diagnostic" className="mt-6">
          <div className="card-trinity p-6">
            <ToolSurvey engagementId={engagementId} toolType="diagnostic" />
          </div>
        </TabsContent>

        <TabsContent value="chatbot" className="mt-6">
          <div className="card-trinity p-6">
            <EngagementChatbot engagementId={engagementId} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

