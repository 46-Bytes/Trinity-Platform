import { FileText, Download, Calendar, User, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn, capitalizeFirstLetter } from '@/lib/utils';

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
  isProcessing?: boolean; // Whether the file is currently being processed
  onDownload?: (id: string) => void;
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
  onDownload,
}: GeneratedFileProps) {
  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
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
          <div className="flex items-center gap-2 mb-1">
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
          </div>
          
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5" />
              Generated {formatDate(generatedAt)}
            </span>
            {generatedBy && (
              <span className="flex items-center gap-1.5">
                <User className="w-3.5 h-3.5" />
                {generatedBy}
              </span>
            )}
            {size && (
              <span>{size}</span>
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

