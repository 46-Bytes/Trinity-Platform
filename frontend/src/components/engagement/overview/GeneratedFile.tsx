import { useState, useEffect } from 'react';
import { FileText, Download, Calendar, User, Loader2, Tag, X, Edit2, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn, capitalizeFirstLetter } from '@/lib/utils';
import { useAuth } from '@/context/AuthContext';

export interface GeneratedFileProps {
  id: string;
  name: string;
  type: 'pdf' | 'docx' | 'xlsx' | 'pptx' | 'txt';
  generatedAt: Date;
  generatedBy?: string;
  size?: string;
  toolType?: string; // e.g., 'business-plan', 'diagnostic', 'position-description'
  relativePath?: string; // Path for downloading the file
  diagnosticId?: string; // Diagnostic ID for report downloads
  mediaId?: string; // Media ID for uploaded files
  isProcessing?: boolean; // Whether the file is currently being processed
  tag?: string; // Document tag
  uploadedByAdmin?: boolean;
  onDownload?: (id: string) => void;
  onTagUpdate?: (fileId: string, tag: string | null, mediaId?: string) => Promise<void>;
}

const fileTypeIcons = {
  pdf: '📄',
  docx: '📝',
  xlsx: '📊',
  pptx: '📽️',
  txt: '📋',
};

const fileTypeColors = {
  pdf: 'text-red-500',
  docx: 'text-blue-500',
  xlsx: 'text-green-500',
  pptx: 'text-orange-500',
  txt: 'text-gray-500',
};

export function GeneratedFile({
  id,
  name,
  type,
  generatedAt,
  generatedBy,
  size,
  toolType,
  isProcessing,
  tag,
  mediaId,
  uploadedByAdmin,
  onDownload,
  onTagUpdate,
}: GeneratedFileProps) {
  const { user } = useAuth();
  const isAdvisor = user?.role === 'advisor' || user?.role === 'firm_advisor';
  const [isEditingTag, setIsEditingTag] = useState(false);
  const [tagValue, setTagValue] = useState(tag || '');
  const [isSavingTag, setIsSavingTag] = useState(false);

  // Update tagValue when tag prop changes (after refresh)
  useEffect(() => {
    setTagValue(tag || '');
  }, [tag]);

  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  };

  const handleTagSave = async () => {
    if (!onTagUpdate) return;
    
    setIsSavingTag(true);
    try {
      const tagToSave = tagValue.trim() || null;
      await onTagUpdate(id, tagToSave, mediaId);
      setIsEditingTag(false);
    } catch (error) {
      console.error('Failed to save tag:', error);
    } finally {
      setIsSavingTag(false);
    }
  };

  const handleTagCancel = () => {
    setTagValue(tag || '');
    setIsEditingTag(false);
  };

  const handleTagDelete = async () => {
    if (!onTagUpdate) return;
    
    setIsSavingTag(true);
    try {
      await onTagUpdate(id, null, mediaId);
      setTagValue('');
    } catch (error) {
      console.error('Failed to delete tag:', error);
    } finally {
      setIsSavingTag(false);
    }
  };

  return (
    <div className="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50 transition-colors group">
      <div className="flex items-center gap-4 flex-1 min-w-0">
        {/* File Icon */}
        <div className={cn(
          "flex-shrink-0 w-12 h-12 rounded-lg flex items-center justify-center text-2xl bg-muted",
          fileTypeColors[type]
        )}>
          {fileTypeIcons[type]}
        </div>

        {/* File Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <h3 className="font-semibold text-foreground truncate">{name}</h3>
            <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground uppercase">
              {type}
            </span>
            {toolType && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-accent/20 text-accent">
                {capitalizeFirstLetter(toolType)}
              </span>
            )}
            {isProcessing && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-info/20 text-info flex items-center gap-1">
                <Loader2 className="w-3 h-3 animate-spin" />
                Processing
              </span>
            )}
            {/* Tag Display/Edit for Advisors */}
            {isAdvisor && !isProcessing && (
              <div className="flex items-center gap-1">
                {isEditingTag ? (
                  <div className="flex items-center gap-1">
                    <Input
                      value={tagValue}
                      onChange={(e) => setTagValue(e.target.value)}
                      placeholder="Enter tag..."
                      className="h-6 text-xs px-2 py-0 w-24"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          handleTagSave();
                        } else if (e.key === 'Escape') {
                          handleTagCancel();
                        }
                      }}
                      autoFocus
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={handleTagSave}
                      disabled={isSavingTag}
                    >
                      <Check className="w-3 h-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={handleTagCancel}
                      disabled={isSavingTag}
                    >
                      <X className="w-3 h-3" />
                    </Button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1">
                    {tag ? (
                      <>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-primary/10 text-primary flex items-center gap-1">
                          <Tag className="w-3 h-3" />
                          {tag}
                        </span>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={() => setIsEditingTag(true)}
                        >
                          <Edit2 className="w-3 h-3" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={handleTagDelete}
                          disabled={isSavingTag}
                        >
                          <X className="w-3 h-3" />
                        </Button>
                      </>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 px-2 text-xs opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1"
                        onClick={() => setIsEditingTag(true)}
                      >
                        <Tag className="w-3 h-3" />
                        Add tag
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-4 text-sm text-muted-foreground flex-wrap">
            {generatedBy && (
              <span className="flex items-center gap-1.5">
                <User className="w-3.5 h-3.5" />
                {generatedBy}
              </span>
            )}
            {size && (
              <span>{size}</span>
            )}
            {uploadedByAdmin && (
              <span className="flex items-center gap-1.5 text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                <User className="w-3.5 h-3.5" />
                Uploaded by Admin
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Download Button - Hide if processing */}
      {!isProcessing && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onDownload?.(id)}
          className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <Download className="w-4 h-4 mr-2" />
          Download
        </Button>
      )}
      {isProcessing && (
        <div className="flex-shrink-0 flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>Generating...</span>
        </div>
      )}
    </div>
  );
}

