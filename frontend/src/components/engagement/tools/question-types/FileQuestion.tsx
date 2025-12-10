import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Upload, X, File } from "lucide-react";
import { useState } from "react";

interface FileQuestionProps {
  question: {
    name: string;
    title: string;
    description?: string;
    allowMultiple?: boolean;
    waitForUpload?: boolean;
  };
  value: File[] | File | null;
  onChange: (files: File[] | File | null) => void;
}

export function FileQuestion({ question, value, onChange }: FileQuestionProps) {
  const [uploading, setUploading] = useState(false);
  
  // Normalize value to always be an array for easier handling
  const files = value 
    ? (Array.isArray(value) ? value : [value])
    : [];

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    
    if (selectedFiles.length === 0) return;

    if (question.allowMultiple) {
      // Add to existing files
      const newFiles = [...files, ...selectedFiles];
      onChange(newFiles);
    } else {
      // Replace with single file
      onChange(selectedFiles[0]);
    }

    // If waitForUpload is true, upload immediately
    if (question.waitForUpload) {
      setUploading(true);
      try {
        // TODO: Implement actual file upload to backend
        await uploadFiles(selectedFiles);
        setUploading(false);
      } catch (error) {
        console.error('File upload failed:', error);
        setUploading(false);
      }
    }

    // Reset input
    e.target.value = '';
  };

  const uploadFiles = async (filesToUpload: File[]) => {
    // TODO: Replace with actual API call
    const formData = new FormData();
    filesToUpload.forEach((file) => {
      formData.append('files', file);
    });

    const token = localStorage.getItem('auth_token');
    const response = await fetch('/api/tools/upload', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Upload failed');
    }

    return response.json();
  };

  const removeFile = (index: number) => {
    if (question.allowMultiple) {
      const newFiles = files.filter((_, i) => i !== index);
      onChange(newFiles.length > 0 ? newFiles : null);
    } else {
      onChange(null);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="space-y-4">
      <div>
        <Label>{question.title}</Label>
        {question.description && (
          <p className="text-sm text-muted-foreground mt-1">{question.description}</p>
        )}
      </div>

      {/* File Input */}
      <div className="border-2 border-dashed rounded-lg p-6 text-center">
        <input
          type="file"
          id={`file-input-${question.name}`}
          className="hidden"
          multiple={question.allowMultiple}
          onChange={handleFileChange}
          disabled={uploading}
        />
        <label
          htmlFor={`file-input-${question.name}`}
          className="cursor-pointer flex flex-col items-center gap-2"
        >
          <Upload className="w-8 h-8 text-muted-foreground" />
          <div>
            <span className="text-sm font-medium text-foreground">
              Click to upload
            </span>
            {question.allowMultiple && (
              <span className="text-sm text-muted-foreground"> or drag and drop</span>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            {question.allowMultiple ? 'Multiple files allowed' : 'Single file only'}
          </p>
        </label>
      </div>

      {/* Uploaded Files List */}
      {files.length > 0 && (
        <div className="space-y-2">
          <Label className="text-sm">Uploaded Files ({files.length})</Label>
          <div className="space-y-2">
            {files.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 border rounded-lg bg-muted/30"
              >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <File className="w-5 h-5 text-muted-foreground flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{file.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatFileSize(file.size)}
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => removeFile(index)}
                  className="flex-shrink-0 text-destructive hover:text-destructive"
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}

      {uploading && (
        <p className="text-sm text-muted-foreground">Uploading files...</p>
      )}
    </div>
  );
}

