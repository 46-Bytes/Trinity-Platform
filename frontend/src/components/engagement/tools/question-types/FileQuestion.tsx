import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Upload, X, File } from "lucide-react";
import { useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

interface FileMetadata {
  file_name: string;
  file_type: string;
  file_size?: number;
  relative_path?: string;
  media_id?: string;  // Backend media ID for file matching
  openai_file_id?: string;  // OpenAI file ID
}

interface FileQuestionProps {
  question: {
    name: string;
    title: string;
    description?: string;
    allowMultiple?: boolean;
    waitForUpload?: boolean;
  };
  /**
   * Value stored in user_responses.
   * This should be an array of file metadata objects, NOT raw File objects.
   */
  value: FileMetadata[] | FileMetadata | null;
  onChange: (value: FileMetadata[] | FileMetadata | null) => void;
  diagnosticId?: string;
}

export function FileQuestion({ question, value, onChange, diagnosticId }: FileQuestionProps) {
  const [uploading, setUploading] = useState(false);
  
  // Normalize value from user_responses to an array of metadata
  const files: FileMetadata[] = value
    ? (Array.isArray(value) ? value : [value])
    : [];

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    
    if (selectedFiles.length === 0) return;

    // We always upload immediately when waitForUpload is true
    if (question.waitForUpload && diagnosticId) {
      setUploading(true);
      try {
        const uploadedMetadata = await uploadFiles(diagnosticId, selectedFiles);

        // Build new metadata array to store in user_responses
        const existingMetadata: FileMetadata[] = files || [];
        const newMetadata = question.allowMultiple
          ? [...existingMetadata, ...uploadedMetadata]
          : uploadedMetadata.slice(-1); // last uploaded file only

        // Update local/Redux state via onChange with metadata only
        onChange(question.allowMultiple ? newMetadata : newMetadata[0] || null);

        // Immediately PATCH diagnostic responses with file metadata
        await saveFileResponse(diagnosticId, question.name, newMetadata);
      } catch (error) {
        console.error("File upload failed:", error);
      } finally {
        setUploading(false);
      }
    }

    // Reset input
    e.target.value = "";
  };

  const uploadFiles = async (diagnosticId: string, filesToUpload: File[]): Promise<FileMetadata[]> => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      throw new Error("No authentication token found");
    }

    const results: FileMetadata[] = [];

    for (const file of filesToUpload) {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        `${API_BASE_URL}/api/diagnostics/${diagnosticId}/upload-file`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Upload failed" }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Upload failed`);
      }

      const data = await response.json();
      results.push({
        file_name: data.file_name,
        file_type: data.file_type,
        file_size: data.file_size,
        relative_path: data.relative_path,
        media_id: data.media_id,  // Store media_id for backend file matching
        openai_file_id: data.openai_file_id,  // Store OpenAI file ID
      });
    }

    return results;
  };

  const saveFileResponse = async (
    diagnosticId: string,
    fieldName: string,
    metadataArray: FileMetadata[]
  ) => {
    const token = localStorage.getItem("auth_token");
    if (!token) {
      throw new Error("No authentication token found");
    }

    const payload = {
      user_responses: {
        [fieldName]: metadataArray,
      },
      status: "in_progress" as const,
    };

    const response = await fetch(
      `${API_BASE_URL}/api/diagnostics/${diagnosticId}/responses`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: "Failed to save file response" }));
      throw new Error(errorData.detail || `HTTP ${response.status}: Failed to save file response`);
    }
  };

  const removeFile = async (index: number) => {
    if (!diagnosticId) {
      console.error("Cannot remove file: diagnosticId is required");
      return;
    }

    const fileToRemove = files[index];
    if (!fileToRemove || !fileToRemove.file_name) {
      console.error("Cannot remove file: file metadata is missing");
      return;
    }

    try {
      const token = localStorage.getItem("auth_token");
      if (!token) {
        throw new Error("No authentication token found");
      }

      // Call DELETE endpoint to remove file from disk and update user_responses
      const response = await fetch(
        `${API_BASE_URL}/api/diagnostics/${diagnosticId}/delete-file?field_name=${encodeURIComponent(question.name)}&file_name=${encodeURIComponent(fileToRemove.file_name)}`,
        {
          method: "DELETE",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Failed to delete file" }));
        throw new Error(errorData.detail || `HTTP ${response.status}: Failed to delete file`);
      }

      // Get updated diagnostic from response
      const updatedDiagnostic = await response.json();
      
      // Extract updated file list from user_responses
      const updatedFieldValue = updatedDiagnostic.user_responses?.[question.name];
      
      // Update local state with the new value from backend
      if (question.allowMultiple) {
        const newFiles = updatedFieldValue 
          ? (Array.isArray(updatedFieldValue) ? updatedFieldValue : [updatedFieldValue])
          : [];
        onChange(newFiles.length > 0 ? newFiles : null);
      } else {
        onChange(updatedFieldValue || null);
      }
    } catch (error) {
      console.error("File deletion failed:", error);
      // Optionally show error toast to user
      // toast.error("Failed to delete file. Please try again.");
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
                    <p className="text-sm font-medium truncate">
                      {"file_name" in file ? file.file_name : (file as any).name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {"file_size" in file && typeof file.file_size === "number"
                        ? formatFileSize(file.file_size)
                        : ""}
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

