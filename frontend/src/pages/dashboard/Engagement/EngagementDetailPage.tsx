import { useParams, useNavigate } from 'react-router-dom';
import { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { ArrowLeft } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from '@/components/ui/button';
import { ToolSurvey } from '@/components/engagement/tools/ToolSurvey';
import { EngagementChatbot } from '@/components/engagement/chatbot';
import { GeneratedFilesList } from '@/components/engagement/overview';
import type { GeneratedFileProps } from '@/components/engagement/overview';
import { TasksList } from '@/components/engagement/tasks';
import { toast } from 'sonner';
import { useAppSelector, useAppDispatch } from '@/store/hooks';
import { useAuth } from '@/context/AuthContext';
import { fetchMediaTags, updateMediaTag, updateDiagnosticTag } from '@/store/slices/tagReducer';
import { isAdminRole, formatRoleForDisplay } from '@/lib/utils';

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
  const dispatch = useAppDispatch();
  const { user } = useAuth();
  const [diagnostics, setDiagnostics] = useState<any[]>([]);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [engagement, setEngagement] = useState<{ client_name?: string } | null>(null);
  const [isLoadingEngagement, setIsLoadingEngagement] = useState(false);
  const fetchInFlightRef = useRef(false);
  
  // Get tags from Redux store
  const { mediaTags, diagnosticTags } = useAppSelector((state) => state.tag);
  
  // Check user role for file filtering
  const isAdmin = user?.role === 'admin' || user?.role === 'firm_admin';
  const isAdvisor = user?.role === 'advisor' || user?.role === 'firm_advisor';
  const isClient = user?.role === 'client';
  
  // Listen to Redux diagnostic state to detect when diagnostic is submitted
  const reduxDiagnostic = useAppSelector((state) => state.diagnostic.diagnostic);

  // Fetch engagement details to get client name
  const fetchEngagement = useCallback(async () => {
    if (!engagementId) return;
    
    setIsLoadingEngagement(true);
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return;

      const response = await fetch(`${API_BASE_URL}/api/engagements/${engagementId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const engagementData = await response.json();
        setEngagement(engagementData);
      }
    } catch (error) {
      console.error('Failed to fetch engagement:', error);
    } finally {
      setIsLoadingEngagement(false);
    }
  }, [engagementId]);

  // Fetch engagement details on mount
  useEffect(() => {
    fetchEngagement();
  }, [fetchEngagement]);

  // Fetch diagnostics for this engagement
  const fetchDiagnostics = useCallback(async () => {
    if (!engagementId) return;
    // Prevent duplicate in-flight calls (e.g., multiple effects firing on mount)
    if (fetchInFlightRef.current) return;
    
    fetchInFlightRef.current = true;
    setIsLoadingFiles(true);
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) return;

      // First, get the list of diagnostics for this engagement
      const listResponse = await fetch(`${API_BASE_URL}/api/diagnostics/engagement/${engagementId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (listResponse.ok) {
        const diagnosticList = await listResponse.json();
        const diagnosticsArray = Array.isArray(diagnosticList) ? diagnosticList : [];
        
        console.log('[fetchDiagnostics] Diagnostics list:', diagnosticsArray.map((d: any) => ({ id: d.id, status: d.status })));
        
        // Fetch full details for each diagnostic to get user_responses
        const fullDiagnostics = await Promise.all(
          diagnosticsArray.map(async (diag: any) => {
            try {
              const detailResponse = await fetch(`${API_BASE_URL}/api/diagnostics/${diag.id}`, {
                headers: {
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json',
                },
              });
              
              if (detailResponse.ok) {
                const fullDetail = await detailResponse.json();
                // Ensure status is preserved (handle both snake_case and camelCase)
                const finalStatus = fullDetail.status || diag.status || 'draft';
                console.log(`[fetchDiagnostics] Diagnostic ${diag.id} status: ${finalStatus}`);
                return {
                  ...fullDetail,
                  status: finalStatus,
                };
              }
              // Fallback to list item if detail fetch fails, but preserve status
              const fallbackStatus = diag.status || 'draft';
              console.log(`[fetchDiagnostics] Diagnostic ${diag.id} fallback status: ${fallbackStatus}`);
              return {
                ...diag,
                status: fallbackStatus,
              };
            } catch (error) {
              console.error(`Failed to fetch diagnostic ${diag.id} details:`, error);
              // Fallback to list item on error, but preserve status
              return {
                ...diag,
                status: diag.status || 'draft',
              };
            }
          })
        );
        
        console.log('[fetchDiagnostics] Final diagnostics:', fullDiagnostics.map((d: any) => ({ 
          id: d.id, 
          status: d.status,
          created_by_user_id: d.created_by_user_id || d.createdByUserId,
          createdByUserId: d.createdByUserId || d.created_by_user_id,
          user_responses_keys: d.user_responses ? Object.keys(d.user_responses) : []
        })));
        console.log('[fetchDiagnostics] Current user for comparison:', {
          userId: user?.id,
          role: user?.role
        });
        setDiagnostics(fullDiagnostics);
      }
    } catch (error) {
      console.error('Failed to fetch diagnostics:', error);
    } finally {
      setIsLoadingFiles(false);
      fetchInFlightRef.current = false;
    }
  }, [engagementId]);

  // Fetch media tags for uploaded files using Redux
  useEffect(() => {
    if (diagnostics.length > 0) {
      const diagnosticIds = diagnostics.map((d: any) => d.id);
      dispatch(fetchMediaTags(diagnosticIds));
    }
  }, [diagnostics, dispatch]);

  // Refresh diagnostics when overview tab is selected
  useEffect(() => {
    if (activeTab === 'overview') {
      fetchDiagnostics();
    }
  }, [activeTab, fetchDiagnostics]);

  // Listen for file upload events from diagnostic tab
  useEffect(() => {
    const handleFileUpload = (event: CustomEvent) => {
      const { engagementId: eventEngagementId } = event.detail;
      // Only refresh if the event is for this engagement
      if (eventEngagementId === engagementId) {
        console.log('[EngagementDetailPage] File uploaded, refreshing diagnostics...');
        fetchDiagnostics();
      }
    };

    window.addEventListener('diagnostic-file-uploaded', handleFileUpload as EventListener);
    
    return () => {
      window.removeEventListener('diagnostic-file-uploaded', handleFileUpload as EventListener);
    };
  }, [engagementId, fetchDiagnostics]);

  // Listen for diagnostic submission - immediately refresh when status becomes "processing"
  useEffect(() => {
    if (reduxDiagnostic && reduxDiagnostic.status === 'processing') {
      console.log('[EngagementDetailPage] Diagnostic submitted, status is processing - refreshing diagnostics list');
      // Immediately fetch diagnostics to show the processing file
      fetchDiagnostics();
      
      // Also set up immediate polling (check status every 5 seconds initially, then back to 30)
      const quickPollInterval = setInterval(async () => {
        try {
          const token = localStorage.getItem('auth_token');
          if (!token) return;

          const statusResponse = await fetch(`${API_BASE_URL}/api/diagnostics/${reduxDiagnostic.id}/status`, {
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
          });
          
          if (statusResponse.ok) {
            const statusData = await statusResponse.json();
            
            // Update diagnostics state immediately
            setDiagnostics(prev => prev.map(d => 
              d.id === reduxDiagnostic.id 
                ? { ...d, status: statusData.status }
                : d
            ));
            
            // If completed, stop quick polling and fetch full details
            if (statusData.status === 'completed' || statusData.status === 'failed') {
              clearInterval(quickPollInterval);
              fetchDiagnostics();
            }
          }
        } catch (error) {
          console.error('Failed to check diagnostic status:', error);
        }
      }, 5000); // Poll every 5 seconds for quick updates

      // Stop quick polling after 2 minutes (fall back to regular 30s polling)
      const timeout = setTimeout(() => {
        clearInterval(quickPollInterval);
      }, 1 * 60 * 1000);

      return () => {
        clearInterval(quickPollInterval);
        clearTimeout(timeout);
      };
    }
  }, [reduxDiagnostic?.status, reduxDiagnostic?.id, fetchDiagnostics]);

  // Poll for diagnostics that are processing (lightweight status check only)
  useEffect(() => {
    // Get current processing diagnostics
    const processingDiagnostics = diagnostics.filter(d => d.status === 'processing');
    
    if (processingDiagnostics.length === 0 || !engagementId) {
      return;
    }

    const pollInterval = setInterval(async () => {
      try {
        const token = localStorage.getItem('auth_token');
        if (!token) return;

        // Get fresh list of processing diagnostics (in case status changed)
        const currentProcessing = diagnostics.filter(d => d.status === 'processing');
        if (currentProcessing.length === 0) {
          return; // No more processing diagnostics, stop polling
        }

        // Check status for each processing diagnostic (lightweight call)
        const statusChecks = await Promise.all(
          currentProcessing.map(async (diag: any) => {
            try {
              const statusResponse = await fetch(`${API_BASE_URL}/api/diagnostics/${diag.id}/status`, {
                headers: {
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json',
                },
              });
              
              if (statusResponse.ok) {
                const statusData = await statusResponse.json();
                return { id: diag.id, ...statusData };
              }
              return null;
            } catch (error) {
              console.error(`Failed to check status for diagnostic ${diag.id}:`, error);
              return null;
            }
          })
        );

        // Update diagnostics state with new statuses (to show processing chip)
        let statusChanged = false;
        const updatedDiagnostics = diagnostics.map((diag: any) => {
          const statusData = statusChecks.find((s: any) => s && s.id === diag.id);
          if (statusData) {
            // Update status if it changed
            if (statusData.status !== diag.status) {
              statusChanged = true;
            }
            // Always update to ensure status is current (for processing chip visibility)
            return { ...diag, status: statusData.status };
          }
          return diag;
        });

        // Always update state to keep processing chip visible
        setDiagnostics(updatedDiagnostics);

        // If status changed to completed/failed, fetch full details
        if (statusChanged) {
          fetchDiagnostics();
        }
      } catch (error) {
        console.error('Failed to poll diagnostic status:', error);
      }
    }, 30000);

    return () => clearInterval(pollInterval);
  }, [diagnostics, engagementId, fetchDiagnostics]);

  // Extract generated files (diagnostic reports) from diagnostics
  const generatedFiles: GeneratedFileProps[] = useMemo(() => {
    const extractedFiles: GeneratedFileProps[] = [];
    
    console.log('[GeneratedFiles] Starting extraction. Current user:', {
      id: user?.id,
      role: user?.role,
      isAdmin: isAdmin
    });
    console.log('[GeneratedFiles] Diagnostics to process:', diagnostics.map((d: any) => ({
      id: d.id,
      created_by_user_id: d.created_by_user_id,
      createdByUserId: d.createdByUserId,
      completed_by_user_id: d.completed_by_user_id,
      completedByUserId: d.completedByUserId
    })));

    // Helper function to normalize UUID strings for comparison
    const normalizeUUID = (uuid: string | null | undefined): string | null => {
      if (!uuid) return null;
      const str = String(uuid).trim().toLowerCase();
      // Remove any surrounding quotes or braces
      return str.replace(/^["'{]|["'}]$/g, '');
    };

    diagnostics.forEach((diagnostic) => {
      // Handle both snake_case and camelCase status
      const status = diagnostic.status || (diagnostic as any).status;

      // Determine if this diagnostic already has a generated report
      const completedAt = diagnostic.completed_at || (diagnostic as any).completedAt || null;
      const reportHtml =
        diagnostic.report_html ||
        (diagnostic as any).reportHtml ||
        diagnostic.ai_analysis?.advisorReport ||
        (diagnostic as any).aiAnalysis?.advisorReport;
      const hasReport = !!(completedAt && reportHtml);
      
      // For admins: only show diagnostic reports from diagnostics they created or completed
      // (Diagnostic reports are tied to the diagnostic creator/completer)
      if (isAdmin && user?.id) {
        const createdByUserId = diagnostic.created_by_user_id || diagnostic.createdByUserId;
        const completedByUserId = diagnostic.completed_by_user_id || diagnostic.completedByUserId;
        const currentUserId = normalizeUUID(user.id);
        
        // Normalize UUIDs for comparison
        const diagnosticCreatedUserId = normalizeUUID(createdByUserId);
        const diagnosticCompletedUserId = normalizeUUID(completedByUserId);
        
        // Check if admin created OR completed this diagnostic
        const isCreatedByAdmin = diagnosticCreatedUserId && currentUserId && diagnosticCreatedUserId === currentUserId;
        const isCompletedByAdmin = diagnosticCompletedUserId && currentUserId && diagnosticCompletedUserId === currentUserId;
        
        console.log('[GeneratedFiles] Admin check for diagnostic:', {
          diagnosticId: diagnostic.id,
          currentUserId,
          diagnosticCreatedUserId,
          diagnosticCompletedUserId,
          isCreatedByAdmin,
          isCompletedByAdmin,
          willShow: isCreatedByAdmin || isCompletedByAdmin
        });
        
        if (!isCreatedByAdmin && !isCompletedByAdmin) {
          console.log('[GeneratedFiles] Skipping diagnostic - not created or completed by admin');
          return; // Skip diagnostic reports not created or completed by admin
        }
      }
      
      // Debug: Log diagnostic status
      if (status === 'processing' || status === 'completed' || hasReport) {
        console.log('[GeneratedFiles] Diagnostic found:', {
          id: diagnostic.id,
          status: status,
          hasReport,
          isProcessing: status === 'processing'
        });
      }
      
      // Add diagnostic report PDF if:
      // - Diagnostic is currently completed or processing, OR
      // - A report was already generated (hasReport) even if status is now in_progress/draft
      if (status === 'completed' || status === 'processing' || hasReport) {
        const baseDate = completedAt || diagnostic.updated_at || (diagnostic as any).updatedAt || diagnostic.created_at || (diagnostic as any).createdAt;
        const reportFileName = `Diagnostic Report - ${new Date(baseDate).toLocaleDateString()}.pdf`;

        const completedByUserRole = (diagnostic as any).completed_by_user_role || (diagnostic as any).completedByUserRole;
        const createdByUserRole = (diagnostic as any).created_by_user_role || (diagnostic as any).createdByUserRole;
        const generatedByRole = completedByUserRole || createdByUserRole;
        
        extractedFiles.push({
          id: `diagnostic-report-${diagnostic.id}`,
          name: reportFileName,
          type: 'pdf',
          generatedAt: new Date(baseDate),
          generatedBy: undefined,
          generatedByRole: generatedByRole && isAdminRole(generatedByRole) ? generatedByRole : undefined,
          size: undefined, // Report is generated on-demand, size unknown
          toolType: 'diagnostic',
          diagnosticId: diagnostic.id, // Store diagnostic ID for download
          isProcessing: status === 'processing', // Mark as processing - show chip and hide download
          tag: diagnosticTags[diagnostic.id] || (diagnostic as any).tag || undefined, // Include tag from Redux store or diagnostic
        });
      }
    });

    console.log('[GeneratedFiles] Total files extracted:', extractedFiles.length, extractedFiles.map(f => ({ name: f.name, isProcessing: f.isProcessing })));

    // Sort by date (newest first)
    return extractedFiles.sort((a, b) => b.generatedAt.getTime() - a.generatedAt.getTime());
  }, [diagnostics, isAdmin, user?.id, diagnosticTags]);

  // Extract uploaded files from diagnostic user_responses
  const uploadedFiles: GeneratedFileProps[] = useMemo(() => {
    const extractedFiles: GeneratedFileProps[] = [];
    
    console.log('[UploadedFiles] Starting extraction. Current user:', {
      id: user?.id,
      role: user?.role,
      isAdmin: isAdmin
    });
    console.log('[UploadedFiles] Total diagnostics to process:', diagnostics.length);
    console.log('[UploadedFiles] Diagnostics to process:', diagnostics.map((d: any) => ({
      id: d.id,
      created_by_user_id: d.created_by_user_id,
      createdByUserId: d.createdByUserId,
      user_responses_keys: d.user_responses ? Object.keys(d.user_responses) : []
    })));

    diagnostics.forEach((diagnostic) => {
      // Note: We filter at the file level for admins, not at the diagnostic level
      
      // Extract uploaded files from user_responses
      // Support both snake_case (from API) and camelCase (from reducer)
      const userResponses = diagnostic.user_responses || diagnostic.userResponses || {};
      
      // Iterate through all response fields
      Object.entries(userResponses).forEach(([fieldName, fieldValue]) => {
        // Skip null/undefined values
        if (!fieldValue) return;
        
        let fileMetadatas: any[] = [];
        
        if (Array.isArray(fieldValue)) {
          // It's an array - check if items are file metadata objects
          fileMetadatas = fieldValue.filter(item => 
            item && 
            typeof item === 'object' && 
            !Array.isArray(item) &&
            item !== null &&
            (('file_name' in item && item.file_name) || ('fileName' in item && (item as any).fileName)) // Support both snake_case and camelCase
          );
        } else if (typeof fieldValue === 'object' && fieldValue !== null && !Array.isArray(fieldValue)) {
          // Check if it's a single file metadata object
          // Use 'in' operator to safely check for properties
          if (('file_name' in fieldValue && fieldValue.file_name) || 
              ('fileName' in fieldValue && (fieldValue as any).fileName)) {
            fileMetadatas = [fieldValue];
          }
        }

        fileMetadatas.forEach((fileMeta: any) => {
          // Support both snake_case (file_name) and camelCase (fileName) from backend
          const fileName = fileMeta.file_name || fileMeta.fileName || '';
          
          if (!fileName) {
            return;
          }
          
          // For admins: only show files they uploaded themselves
          if (isAdmin && user?.id) {
            // Get uploaded_by_user_id from file metadata (support both snake_case and camelCase)
            const uploadedByUserId = fileMeta.uploaded_by_user_id || fileMeta.uploadedByUserId;
            const currentUserId = String(user.id);
            const fileUploaderId = uploadedByUserId ? String(uploadedByUserId) : null;
            
            // If file doesn't have uploader info, filter it out for admins (safety: old files)
            if (!fileUploaderId) {
              console.log('[UploadedFiles] Admin filtering out file (no uploaded_by_user_id):', {
                fileName: fileName,
                diagnosticId: diagnostic.id
              });
              return;
            }
            
            // If file was uploaded by someone else, filter it out
            if (fileUploaderId !== currentUserId) {
              console.log('[UploadedFiles] Admin filtering out file (different uploader):', {
                fileName: fileName,
                fileUploaderId: fileUploaderId,
                currentUserId: currentUserId,
                diagnosticId: diagnostic.id
              });
              return;
            }
          }

          // Determine if this file was uploaded by an admin (for labeling in UI)
          const uploadedByRoleRaw = fileMeta.uploaded_by_role || fileMeta.uploadedByRole;
          const uploadedByRole = uploadedByRoleRaw ? String(uploadedByRoleRaw).toLowerCase().trim() : null;
          // Use exact role matching instead of includes('admin')
          const uploadedByAdmin = uploadedByRole && isAdminRole(uploadedByRole);

          // Extract file extension to determine type
          const extension = fileName.split('.').pop()?.toLowerCase() || 'txt';
          
          // Map extension to file type
          let fileType: 'pdf' | 'docx' | 'xlsx' | 'pptx' | 'txt' = 'txt';
          if (extension === 'pdf') fileType = 'pdf';
          else if (['doc', 'docx'].includes(extension)) fileType = 'docx';
          else if (['xls', 'xlsx'].includes(extension)) fileType = 'xlsx';
          else if (['ppt', 'pptx'].includes(extension)) fileType = 'pptx';

          // Format file size (support both snake_case and camelCase)
          const fileSizeValue = fileMeta.file_size || fileMeta.fileSize;
          const fileSize = fileSizeValue
            ? fileSizeValue > 1024 * 1024 
              ? `${(fileSizeValue / (1024 * 1024)).toFixed(1)} MB`
              : `${(fileSizeValue / 1024).toFixed(0)} KB`
            : undefined;

          // Support both snake_case and camelCase for relative_path
          const relativePath = fileMeta.relative_path || fileMeta.relativePath;

          const mediaId = fileMeta.media_id || fileMeta.mediaId;
          // Get tag from Redux store (mediaTags) or from fileMeta as fallback
          const fileTag = mediaId ? (mediaTags[mediaId] || fileMeta.tag || undefined) : (fileMeta.tag || undefined);
          
          extractedFiles.push({
            id: mediaId || `${diagnostic.id}-${fieldName}-${fileName}-${Date.now()}`,
            name: fileName,
            type: fileType,
            generatedAt: new Date(diagnostic.created_at || diagnostic.updated_at || diagnostic.createdAt || diagnostic.updatedAt || new Date()),
            generatedBy: undefined, // Could fetch user name if needed
            size: fileSize,
            toolType: 'diagnostic',
            relativePath: relativePath, // Store for download
            mediaId: mediaId, // Store media ID for tag updates
            tag: fileTag, // Include tag from Media model or metadata
            uploadedByAdmin: uploadedByAdmin, // Keep for backward compatibility
            uploadedByRole: uploadedByAdmin ? uploadedByRole : undefined, // Pass role only if admin
          });
        });
      });
    });

    // Sort by date (newest first)
    return extractedFiles.sort((a, b) => b.generatedAt.getTime() - a.generatedAt.getTime());
  }, [diagnostics, isAdmin, user?.id, mediaTags]);

  const handleTagUpdate = async (fileId: string, tag: string | null, mediaId?: string) => {
    try {
      // If it's an uploaded file (has mediaId), update via Redux
      if (mediaId) {
        await dispatch(updateMediaTag({ mediaId, tag })).unwrap();
        // Refresh media tags to ensure we have the latest
        const diagnosticIds = diagnostics.map((d: any) => d.id);
        dispatch(fetchMediaTags(diagnosticIds));
        toast.success('Tag updated successfully');
      } else {
        // For generated files (diagnostic reports), use diagnostic tag API
        // Extract diagnostic ID from fileId (format: diagnostic-report-{diagnosticId})
        const diagnosticId = fileId.replace('diagnostic-report-', '');
        await dispatch(updateDiagnosticTag({ diagnosticId, tag })).unwrap();
        // Refresh diagnostics to get updated tag
        await fetchDiagnostics();
        toast.success('Tag updated successfully');
      }
    } catch (error) {
      console.error('Failed to update tag:', error);
      toast.error(error instanceof Error ? error.message : 'Failed to update tag');
    }
  };

  const handleDownload = async (fileId: string) => {
    // Find the file in either generated or uploaded files
    const file = [...generatedFiles, ...uploadedFiles].find(f => f.id === fileId);
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
    <div className="w-full mx-auto px-0 sm:px-1 md:px-3 lg:px-6 py-2 sm:py-3 md:py-6" style={{ width: '100%', boxSizing: 'border-box', maxWidth: '100vw', overflowX: 'clip', paddingLeft: 'clamp(0px, 1vw, 24px)', paddingRight: 'clamp(0px, 1vw, 24px)' }}>
      <div className="mb-4 sm:mb-6" style={{ width: '100%', maxWidth: '100%' }}>
        <h1 className="text-2xl sm:text-3xl font-bold break-words" style={{ maxWidth: '100%' }}>
          {isLoadingEngagement ? 'Loading...' : (engagement?.client_name || 'Engagement Details')}
        </h1>
        <p className="text-muted-foreground mt-1 break-words" style={{ maxWidth: '100%' }}>Manage your client engagement</p>
      </div>
      
      <Tabs defaultValue="overview" className="w-full min-w-0">
        <div className="flex items-center gap-4 mb-4 flex-wrap">
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
            {/* Engagement Summary Card - Hidden for admins */}
            {!isAdmin && (
              <div className="card-trinity p-6">
                <h2 className="text-xl font-semibold mb-4">Engagement Overview</h2>
                <p className="text-muted-foreground">
                  Engagement overview and details will be displayed here.
                </p>
                {/* TODO: Add engagement overview content */}
              </div>
            )}

            {/* Generated Files Section - Visible to all, but filtered by role */}
            <div className="card-trinity p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">Generated Files</h2>
                {!isLoadingFiles && (
                  <span className="text-sm text-muted-foreground">
                    {generatedFiles.length} file{generatedFiles.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
              {isLoadingFiles ? (
                <div className="text-center py-8 text-muted-foreground">Loading files...</div>
              ) : (
                <GeneratedFilesList 
                  files={generatedFiles} 
                  onDownload={handleDownload}
                  onTagUpdate={handleTagUpdate}
                />
              )}
            </div>

            {/* Uploaded Files Section - Visible to all, but filtered by role */}
            <div className="card-trinity p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold">Uploaded Files</h2>
                {!isLoadingFiles && (
                  <span className="text-sm text-muted-foreground">
                    {uploadedFiles.length} file{uploadedFiles.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>
              {isLoadingFiles ? (
                <div className="text-center py-8 text-muted-foreground">Loading files...</div>
              ) : (
                <GeneratedFilesList 
                  files={uploadedFiles} 
                  onDownload={handleDownload}
                  onTagUpdate={handleTagUpdate}
                  emptyMessage={{
                    title: 'No uploaded files yet',
                    description: 'Files uploaded during the diagnostic will appear here'
                  }}
                />
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="tasks" className="mt-6">
          <div className="card-trinity p-6">
            <TasksList engagementId={engagementId} />
          </div>
        </TabsContent>

        <TabsContent value="diagnostic" className="mt-4 sm:mt-6 w-full" style={{ width: '100%', maxWidth: '100%', overflowX: 'clip' }}>
          <div className="card-trinity px-0 sm:px-1 md:px-3 lg:px-6 py-2 sm:py-3 md:py-6 w-full" style={{ width: '100%', boxSizing: 'border-box', maxWidth: '100%', overflowX: 'clip', paddingLeft: 'clamp(0px, 1vw, 24px)', paddingRight: 'clamp(0px, 1vw, 24px)' }}>
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

