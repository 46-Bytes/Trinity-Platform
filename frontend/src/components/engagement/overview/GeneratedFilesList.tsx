import { GeneratedFile, GeneratedFileProps } from './GeneratedFile';
import { FileText } from 'lucide-react';

interface GeneratedFilesListProps {
  files: GeneratedFileProps[];
  onDownload?: (id: string) => void;
  onTagUpdate?: (fileId: string, tag: string | null, mediaId?: string) => Promise<void>;
  emptyMessage?: {
    title?: string;
    description?: string;
  };
}

export function GeneratedFilesList({ files, onDownload, onTagUpdate, emptyMessage }: GeneratedFilesListProps) {
  if (files.length === 0) {
    const defaultTitle = emptyMessage?.title || 'No files yet';
    const defaultDescription = emptyMessage?.description || 'Files will appear here';
    
    return (
      <div className="text-center py-12 border border-dashed rounded-lg">
        <FileText className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
        <p className="text-muted-foreground">{defaultTitle}</p>
        <p className="text-sm text-muted-foreground mt-1">
          {defaultDescription}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {files.map((file) => (
        <GeneratedFile
          key={file.id}
          {...file}
          onDownload={onDownload}
          onTagUpdate={onTagUpdate}
        />
      ))}
    </div>
  );
}

