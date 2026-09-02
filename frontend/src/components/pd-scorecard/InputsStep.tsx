import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAppDispatch } from '@/store/hooks';
import {
  saveInputs,
  uploadDocuments,
  type PDScorecard,
  type UploadedFileResult,
} from '@/store/slices/pdScorecardReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Upload, FileText, X, Loader2, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

interface InputsStepProps {
  build: PDScorecard | null;
  isUploading: boolean;
  isSaving: boolean;
  onComplete: () => void;
}

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${Math.round((bytes / Math.pow(k, i)) * 100) / 100} ${sizes[i]}`;
};

export function InputsStep({ build, isUploading, isSaving, onComplete }: InputsStepProps) {
  const dispatch = useAppDispatch();
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [clientName, setClientName] = useState('');
  const [fyRange, setFyRange] = useState('');
  const [referenceFiles, setReferenceFiles] = useState<string[]>([]);
  const [pastedNotes, setPastedNotes] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const buildId = build?.id;
  const savedClientName = build?.client_name;
  const savedFyRange = build?.fy_range;
  const savedReferences = build?.reference_pd_files;
  const savedNotes = build?.pasted_notes;

  // Rehydrate the form when returning to an existing build
  useEffect(() => {
    if (savedClientName) setClientName(savedClientName);
    if (savedFyRange) setFyRange(savedFyRange);
    if (savedReferences?.length) setReferenceFiles(savedReferences);
    if (savedNotes) setPastedNotes(savedNotes);
    // Only rehydrate when switching to a different build, not on every save
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buildId]);

  const uploadedFilenames = useMemo(
    () => Object.keys(build?.file_mappings || {}),
    [build?.file_mappings]
  );

  const hasSource = Boolean(
    uploadedFilenames.length > 0 || pendingFiles.length > 0 || pastedNotes.trim()
  );

  const handleFileSelect = (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;
    const valid = Array.from(selectedFiles).filter((file) => {
      if (file.size > MAX_FILE_SIZE) {
        toast.error(`File ${file.name} exceeds the 10MB limit`);
        return false;
      }
      return true;
    });
    setPendingFiles((prev) => [...prev, ...valid]);
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFileSelect(e.dataTransfer.files);
  }, []);

  const toggleReference = (filename: string) => {
    setReferenceFiles((prev) =>
      prev.includes(filename) ? prev.filter((f) => f !== filename) : [...prev, filename]
    );
  };

  /** Upload anything still sitting in the staging list. */
  const uploadPendingFiles = async (): Promise<boolean> => {
    if (!build || pendingFiles.length === 0) return true;
    try {
      const result = await dispatch(
        uploadDocuments({ buildId: build.id, files: pendingFiles })
      ).unwrap();
      setPendingFiles([]);

      // The endpoint reports per-file outcomes, so a partial failure is not a success
      const failed: UploadedFileResult[] = (result.files || []).filter(
        (file: UploadedFileResult) => file.status === 'error'
      );
      if (failed.length > 0) {
        toast.error(`${failed.length} file(s) failed to upload`);
        return false;
      }
      return true;
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Upload failed');
      return false;
    }
  };

  const handleContinue = async () => {
    if (!build) return;

    if (!hasSource) {
      toast.error('Upload the roles matrix, or paste its contents');
      return;
    }

    const uploaded = await uploadPendingFiles();
    if (!uploaded) return;

    try {
      await dispatch(
        saveInputs({
          buildId: build.id,
          clientName: clientName.trim() || null,
          fyRange: fyRange.trim() || null,
          referencePdFiles: referenceFiles,
          pastedNotes: pastedNotes.trim() || null,
        })
      ).unwrap();
      onComplete();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save inputs');
    }
  };

  const busy = isUploading || isSaving;

  return (
    <div className="space-y-6">
      {/* Client details */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Client details</CardTitle>
          <CardDescription>
            The business name appears in the position description header. The financial year range
            is used for transition sections.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="client-name">Business name</Label>
            <Input
              id="client-name"
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              placeholder="e.g. Sample Client"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="fy-range">Financial year range</Label>
            <Input
              id="fy-range"
              value={fyRange}
              onChange={(e) => setFyRange(e.target.value)}
              placeholder="e.g. FY25-27"
            />
          </div>
        </CardContent>
      </Card>

      {/* Upload */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Roles matrix and reference PDs</CardTitle>
          <CardDescription>
            Upload the completed Roles &amp; Responsibilities matrix. Existing position descriptions
            are optional — tick them below and they will inform tone and wording only, never
            responsibilities.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            className={cn(
              'rounded-lg border-2 border-dashed p-6 text-center transition-colors',
              isDragOver ? 'border-primary bg-primary/5' : 'border-muted-foreground/25'
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <Upload className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground mb-3">
              Drag files here, or browse. Up to 10MB each.
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              accept=".xlsx,.xls,.csv,.pdf,.doc,.docx,.txt"
              onChange={(e) => handleFileSelect(e.target.files)}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => fileInputRef.current?.click()}
            >
              Browse files
            </Button>
          </div>

          {pendingFiles.length > 0 && (
            <div className="space-y-2">
              <Label>Ready to upload</Label>
              {pendingFiles.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  className="flex items-center justify-between gap-3 rounded-md border p-2"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                    <span className="text-sm truncate">{file.name}</span>
                    <span className="text-xs text-muted-foreground flex-shrink-0">
                      {formatFileSize(file.size)}
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={busy}
                    onClick={() => setPendingFiles((prev) => prev.filter((_, i) => i !== index))}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          {uploadedFilenames.length > 0 && (
            <div className="space-y-2">
              <Label>Uploaded — tick any that are reference PDs</Label>
              {uploadedFilenames.map((filename) => (
                <div key={filename} className="flex items-center gap-3 rounded-md border p-2">
                  <Checkbox
                    id={`ref-${filename}`}
                    checked={referenceFiles.includes(filename)}
                    onCheckedChange={() => toggleReference(filename)}
                  />
                  <Label
                    htmlFor={`ref-${filename}`}
                    className="flex items-center gap-2 min-w-0 text-sm font-normal cursor-pointer"
                  >
                    <FileText className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                    <span className="truncate">{filename}</span>
                  </Label>
                  {referenceFiles.includes(filename) && (
                    <Badge variant="secondary" className="ml-auto flex-shrink-0">
                      Tone only
                    </Badge>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Notes */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Paste the matrix, or add notes</CardTitle>
          <CardDescription>
            Optional. Use this instead of a file upload, or to add anything the matrix does not say.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea
            value={pastedNotes}
            onChange={(e) => setPastedNotes(e.target.value)}
            placeholder="Paste the roles and responsibilities matrix here..."
            rows={6}
          />
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={handleContinue} disabled={busy || !hasSource}>
          {busy ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              Saving...
            </>
          ) : (
            <>
              Continue
              <ArrowRight className="h-4 w-4 ml-2" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
