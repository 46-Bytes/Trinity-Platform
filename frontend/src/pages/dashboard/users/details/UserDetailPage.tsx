import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { ArrowLeft, FileText, Download, Calendar, Loader2, User, Mail, Shield, CheckCircle, XCircle, FileIcon, BarChart3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface UserFile {
  id: string;
  file_name: string;
  file_size?: number;
  file_type?: string;
  file_extension?: string;
  created_at: string;
  description?: string;
  question_field_name?: string;
}

interface UserDiagnostic {
  id: string;
  engagement_id: string;
  status: string;
  overall_score?: number;
  report_url?: string;
  created_at: string;
  completed_at?: string;
}

interface UserDetailData {
  id: string;
  email: string;
  name: string;
  first_name?: string;
  last_name?: string;
  role: string;
  email_verified: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_login?: string;
  files: UserFile[];
  diagnostics: UserDiagnostic[];
  engagements_count: number;
}

export default function UserDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user: currentUser } = useAuth();
  
  const [userData, setUserData] = useState<UserDetailData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Check if current user is super_admin
  const isSuperAdmin = currentUser?.role === 'super_admin';

  useEffect(() => {
    if (!isSuperAdmin) {
      setError('Access denied. Only super_admin can view user details.');
      setIsLoading(false);
      return;
    }

    const fetchUserDetails = async () => {
      try {
        setIsLoading(true);
        setError(null);
        
        const token = localStorage.getItem('auth_token');
        if (!token) {
          throw new Error('No authentication token found');
        }

        const response = await fetch(`${API_BASE_URL}/api/users/${id}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          if (response.status === 403) {
            throw new Error('Access denied. Only super_admin can view user details.');
          }
          if (response.status === 404) {
            throw new Error('User not found');
          }
          const errorData = await response.json().catch(() => ({ detail: 'Failed to fetch user details' }));
          throw new Error(errorData.detail || `HTTP ${response.status}: Failed to fetch user details`);
        }

        const data = await response.json();
        setUserData(data);
      } catch (err) {
        console.error('Failed to fetch user details:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch user details');
        toast.error(err instanceof Error ? err.message : 'Failed to fetch user details');
      } finally {
        setIsLoading(false);
      }
    };

    if (id) {
      fetchUserDetails();
    }
  }, [id, isSuperAdmin]);

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return 'N/A';
    }
  };

  const formatFileSize = (bytes?: number) => {
    if (!bytes) return 'N/A';
    if (bytes > 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
    return `${(bytes / 1024).toFixed(0)} KB`;
  };

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, { label: string; className: string }> = {
      completed: { label: 'Completed', className: 'status-success' },
      processing: { label: 'Processing', className: 'status-warning' },
      in_progress: { label: 'In Progress', className: 'status-info' },
      draft: { label: 'Draft', className: 'bg-muted text-muted-foreground' },
      failed: { label: 'Failed', className: 'status-error' },
    };
    
    const statusInfo = statusMap[status] || { label: status, className: 'bg-muted text-muted-foreground' };
    return (
      <span className={cn('status-badge', statusInfo.className)}>
        {statusInfo.label}
      </span>
    );
  };

  const handleDownloadDiagnostic = async (diagnosticId: string) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        toast.error('No authentication token found');
        return;
      }

      const response = await fetch(`${API_BASE_URL}/api/diagnostics/${diagnosticId}/download`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to download diagnostic report');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `diagnostic-report-${diagnosticId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success('Diagnostic report downloaded successfully');
    } catch (err) {
      console.error('Failed to download diagnostic:', err);
      toast.error('Failed to download diagnostic report');
    }
  };

  const handleDownloadFile = async (fileId: string, fileName: string) => {
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) {
        toast.error('No authentication token found');
        return;
      }

      if (!id) {
        toast.error('User ID not found');
        return;
      }

      const response = await fetch(`${API_BASE_URL}/api/users/${id}/files/${fileId}/download`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || 'Failed to download file');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast.success(`Downloaded ${fileName}`);
    } catch (err) {
      console.error('Failed to download file:', err);
      toast.error(err instanceof Error ? err.message : 'Failed to download file');
    }
  };

  if (!isSuperAdmin) {
    return (
      <div className="space-y-6">
        <div className="card-trinity p-6">
          <div className="text-center py-12">
            <Shield className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <h2 className="text-xl font-semibold mb-2">Access Denied</h2>
            <p className="text-muted-foreground">Only super_admin can view user details.</p>
            <Button onClick={() => navigate('/dashboard/users')} className="mt-4">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Users
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="card-trinity p-6">
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 animate-spin text-accent" />
            <span className="ml-2 text-muted-foreground">Loading user details...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !userData) {
    return (
      <div className="space-y-6">
        <div className="card-trinity p-6">
          <div className="text-center py-12">
            <XCircle className="w-12 h-12 mx-auto text-destructive mb-4" />
            <h2 className="text-xl font-semibold mb-2">Error</h2>
            <p className="text-muted-foreground mb-4">{error || 'Failed to load user details'}</p>
            <Button onClick={() => navigate('/dashboard/users')} variant="outline">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Users
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate('/dashboard/users')}
          className="shrink-0"
        >
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">User Details</h1>
          <p className="text-muted-foreground mt-1">View detailed information about the user</p>
        </div>
      </div>

      {/* User Information Card */}
      <div className="card-trinity p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <User className="w-5 h-5" />
          User Information
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium text-muted-foreground">Name</label>
            <p className="text-foreground font-medium">{userData.name || 'N/A'}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Email</label>
            <p className="text-foreground font-medium flex items-center gap-2">
              <Mail className="w-4 h-4" />
              {userData.email}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Role</label>
            <p className="text-foreground font-medium">{userData.role}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Status</label>
            <div className="mt-1">
              <span className={cn(
                'status-badge',
                userData.is_active ? 'status-success' : 'bg-muted text-muted-foreground'
              )}>
                {userData.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Email Verified</label>
            <div className="mt-1">
              {userData.email_verified ? (
                <span className="status-badge status-success flex items-center gap-1 w-fit">
                  <CheckCircle className="w-3 h-3" />
                  Verified
                </span>
              ) : (
                <span className="status-badge bg-yellow-100 text-yellow-800 flex items-center gap-1 w-fit">
                  <XCircle className="w-3 h-3" />
                  Unverified
                </span>
              )}
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Created At</label>
            <p className="text-foreground">{formatDate(userData.created_at)}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Last Login</label>
            <p className="text-foreground">{userData.last_login ? formatDate(userData.last_login) : 'Never'}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-muted-foreground">Engagements</label>
            <p className="text-foreground font-medium flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              {userData.engagements_count}
            </p>
          </div>
        </div>
      </div>

      {/* Files Section */}
      <div className="card-trinity p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <FileIcon className="w-5 h-5" />
          Files Uploaded ({userData.files.length})
        </h2>
        {userData.files.length === 0 ? (
          <p className="text-muted-foreground text-center py-8">No files uploaded by this user</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-trinity">
              <thead>
                <tr>
                  <th>File Name</th>
                  <th>Type</th>
                  <th>Size</th>
                  <th>Uploaded At</th>
                  <th>Description</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {userData.files.map((file) => (
                  <tr key={file.id}>
                    <td>
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-muted-foreground" />
                        <span className="font-medium">{file.file_name}</span>
                      </div>
                    </td>
                    <td>
                      <span className="text-muted-foreground">
                        {file.file_extension?.toUpperCase() || file.file_type || 'N/A'}
                      </span>
                    </td>
                    <td>
                      <span className="text-muted-foreground">{formatFileSize(file.file_size)}</span>
                    </td>
                    <td>
                      <span className="text-muted-foreground">{formatDate(file.created_at)}</span>
                    </td>
                    <td>
                      <span className="text-muted-foreground">{file.description || '-'}</span>
                    </td>
                    <td>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDownloadFile(file.id, file.file_name)}
                        className="flex items-center gap-2"
                      >
                        <Download className="w-4 h-4" />
                        Download
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Diagnostic Reports Section */}
      <div className="card-trinity p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          Diagnostic Reports ({userData.diagnostics.length})
        </h2>
        {userData.diagnostics.length === 0 ? (
          <p className="text-muted-foreground text-center py-8">No diagnostic reports generated for this user</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-trinity">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Score</th>
                  <th>Created At</th>
                  <th>Completed At</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {userData.diagnostics.map((diagnostic) => (
                  <tr key={diagnostic.id}>
                    <td>{getStatusBadge(diagnostic.status)}</td>
                    <td>
                      {diagnostic.overall_score !== null && diagnostic.overall_score !== undefined ? (
                        <span className="font-medium">{diagnostic.overall_score.toFixed(1)}/5.0</span>
                      ) : (
                        <span className="text-muted-foreground">N/A</span>
                      )}
                    </td>
                    <td>
                      <span className="text-muted-foreground">{formatDate(diagnostic.created_at)}</span>
                    </td>
                    <td>
                      <span className="text-muted-foreground">
                        {diagnostic.completed_at ? formatDate(diagnostic.completed_at) : '-'}
                      </span>
                    </td>
                    <td>
                      {diagnostic.status === 'completed' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDownloadDiagnostic(diagnostic.id)}
                          className="flex items-center gap-2"
                        >
                          <Download className="w-4 h-4" />
                          Download
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

