import { GeneratedFile, GeneratedFileProps } from './GeneratedFile';
import { FileText } from 'lucide-react';

interface GeneratedFilesListProps {
  files: GeneratedFileProps[];
  onDownload?: (id: string) => void;
}

export function GeneratedFilesList({ files, onDownload }: GeneratedFilesListProps) {
  if (files.length === 0) {
    return (
      <div className="text-center py-12 border border-dashed rounded-lg">
        <FileText className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
        <p className="text-muted-foreground">No generated files yet</p>
        <p className="text-sm text-muted-foreground mt-1">
          Files will appear here after using AI tools
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
        />
      ))}
    </div>
  );
}

