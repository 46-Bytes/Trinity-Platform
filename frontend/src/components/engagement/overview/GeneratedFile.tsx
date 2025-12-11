import { FileText, Download, Calendar, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

export interface GeneratedFileProps {
  id: string;
  name: string;
  type: 'pdf' | 'docx' | 'xlsx' | 'pptx' | 'txt';
  generatedAt: Date;
  generatedBy?: string;
  size?: string;
  toolType?: string; // e.g., 'business-plan', 'diagnostic', 'position-description'
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
  name,
  type,
  generatedAt,
  generatedBy,
  size,
  toolType,
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
                {toolType}
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

      {/* Download Button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onDownload?.('')}
        className="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <Download className="w-4 h-4 mr-2" />
        Download
      </Button>
    </div>
  );
}

