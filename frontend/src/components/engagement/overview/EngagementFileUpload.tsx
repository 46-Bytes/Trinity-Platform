import { useRef, useState } from 'react';
import { Loader2, Upload } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Mirrors FileService.ALLOWED_EXTENSIONS so the picker offers what the server
// accepts. The server still validates; this only saves a wasted round trip.
const ACCEPTED =
  '.pdf,.doc,.docx,.txt,.rtf,.xls,.xlsx,.csv,.jpg,.jpeg,.png,.gif,.webp,.zip';

interface EngagementFileUploadProps {
  engagementId: string;
  onUploaded: () => void;
}

/**
 * Upload button for the Overview page's Uploaded Files card.
 *
 * A hidden input behind a Button, matching FileQuestion in the diagnostic -
 * the same pattern an advisor already meets when attaching files there.
 */
export function EngagementFileUpload({ engagementId, onUploaded }: EngagementFileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);

  const upload = async (fileList: FileList) => {
    const files = Array.from(fileList);
    if (files.length === 0) return;

    setIsUploading(true);
    try {
      const token = localStorage.getItem('auth_token');
      if (!token) throw new Error('No authentication token found');

      const formData = new FormData();
      files.forEach((file) => formData.append('files', file));

      const response = await fetch(`${API_BASE_URL}/api/engagements/${engagementId}/files`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(error.detail || `HTTP ${response.status}: Upload failed`);
      }

      const created = await response.json();
      toast.success(
        created.length === 1 ? 'File uploaded' : `${created.length} files uploaded`
      );
      onUploaded();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to upload the file');
    } finally {
      setIsUploading(false);
      // Reset so picking the same file again still fires onChange.
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPTED}
        className="hidden"
        onChange={(event) => event.target.files && upload(event.target.files)}
      />
      <Button
        variant="outline"
        size="sm"
        disabled={isUploading}
        onClick={() => inputRef.current?.click()}
      >
        {isUploading ? (
          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
        ) : (
          <Upload className="w-4 h-4 mr-2" />
        )}
        {isUploading ? 'Uploading...' : 'Upload Files'}
      </Button>
    </>
  );
}
