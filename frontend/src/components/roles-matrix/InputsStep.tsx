import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useAppDispatch } from '@/store/hooks';
import {
  saveInputs,
  uploadDocuments,
  type RolesMatrix,
  type StaffMember,
  type UploadedFileResult,
} from '@/store/slices/rolesMatrixReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { Upload, FileText, X, Loader2, Plus, ArrowRight } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface InputsStepProps {
  matrix: RolesMatrix | null;
  isUploading: boolean;
  isSaving: boolean;
  onComplete: () => void;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${Math.round((bytes / Math.pow(k, i)) * 100) / 100} ${sizes[i]}`;
};

export function InputsStep({ matrix, isUploading, isSaving, onComplete }: InputsStepProps) {
  const dispatch = useAppDispatch();
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [staff, setStaff] = useState<StaffMember[]>([{ name: '', role_title: '' }]);
  const [includedRoles, setIncludedRoles] = useState<string[]>([]);
  const [pastedNotes, setPastedNotes] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const matrixId = matrix?.id;
  const savedStaff = matrix?.staff;
  const savedRoles = matrix?.included_roles;
  const savedNotes = matrix?.pasted_notes;

  // Rehydrate the form when returning to an existing matrix
  useEffect(() => {
    if (savedStaff?.length) {
      setStaff(savedStaff.map((m) => ({ name: m.name, role_title: m.role_title ?? '' })));
    }
    if (savedRoles?.length) {
      setIncludedRoles(savedRoles);
    }
    if (savedNotes) {
      setPastedNotes(savedNotes);
    }
    // Only rehydrate when switching to a different matrix, not on every save
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matrixId]);

  const uploadedFilenames = useMemo(
    () => Object.keys(matrix?.file_mappings || {}),
    [matrix?.file_mappings]
  );

  // Candidate roles are the names/titles the advisor has entered
  const roleCandidates = useMemo(() => {
    const candidates: string[] = [];
    staff.forEach((member) => {
      const label = member.name?.trim();
      if (!label) return;
      const title = member.role_title?.trim();
      candidates.push(title ? `${label} — ${title}` : label);
    });
    return candidates;
  }, [staff]);

  // Drop confirmed roles that no longer match any staff entry
  const roleCandidatesKey = roleCandidates.join('|');
  useEffect(() => {
    setIncludedRoles((prev) => prev.filter((role) => roleCandidatesKey.split('|').includes(role)));
  }, [roleCandidatesKey]);

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

  const handleUpload = async () => {
    if (!matrix || pendingFiles.length === 0) return;
    try {
      const result = await dispatch(
        uploadDocuments({ matrixId: matrix.id, files: pendingFiles })
      ).unwrap();
      setPendingFiles([]);

      // The endpoint reports per-file outcomes, so a partial failure is not a success
      const failed: UploadedFileResult[] = (result.files || []).filter(
        (file: UploadedFileResult) => file.status === 'error'
      );
      if (failed.length > 0) {
        toast.error(
          `${failed.length} of ${result.files.length} file(s) failed: ${failed
            .map((file) => file.filename)
            .join(', ')}`
        );
      } else {
        toast.success('Documents uploaded');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to upload documents');
    }
  };

  const updateStaff = (index: number, field: keyof StaffMember, value: string) => {
    setStaff((prev) => prev.map((m, i) => (i === index ? { ...m, [field]: value } : m)));
  };

  const addStaffRow = () => setStaff((prev) => [...prev, { name: '', role_title: '' }]);

  const removeStaffRow = (index: number) =>
    setStaff((prev) => (prev.length === 1 ? prev : prev.filter((_, i) => i !== index)));

  const toggleRole = (role: string, checked: boolean) => {
    setIncludedRoles((prev) => (checked ? [...prev, role] : prev.filter((r) => r !== role)));
  };

  const handleContinue = async () => {
    if (!matrix) return;

    const cleanedStaff = staff
      .map((m) => ({ name: m.name.trim(), role_title: m.role_title?.trim() || null }))
      .filter((m) => m.name);

    if (cleanedStaff.length === 0) {
      toast.error('Add at least one staff member');
      return;
    }
    if (includedRoles.length === 0) {
      toast.error('Confirm which roles must be included in the matrix');
      return;
    }
    if (uploadedFilenames.length === 0 && !pastedNotes.trim()) {
      toast.error('Upload a document or paste some notes before continuing');
      return;
    }

    try {
      await dispatch(
        saveInputs({
          matrixId: matrix.id,
          staff: cleanedStaff,
          includedRoles,
          pastedNotes: pastedNotes.trim() || undefined,
        })
      ).unwrap();
      onComplete();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save inputs');
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Position descriptions */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">1. Position descriptions</CardTitle>
          <CardDescription>
            Upload any existing position descriptions (PDs) and supporting documents.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              'border-2 border-dashed rounded-lg p-6 sm:p-8 text-center cursor-pointer transition-colors',
              isDragOver ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50'
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.txt,.md"
              onChange={(e) => handleFileSelect(e.target.files)}
              className="hidden"
            />
            <Upload className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
            {isDragOver ? (
              <p className="text-primary font-medium">Drop the files here...</p>
            ) : (
              <div>
                <p className="text-sm font-medium mb-1">Drag and drop files here, or click to select</p>
                <p className="text-xs text-muted-foreground">
                  PDF, Word, Excel and text files (max 10MB per file)
                </p>
              </div>
            )}
          </div>

          {pendingFiles.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Ready to upload ({pendingFiles.length})</p>
              <div className="space-y-2 max-h-52 overflow-y-auto">
                {pendingFiles.map((file, index) => (
                  <div key={`${file.name}-${index}`} className="flex items-center justify-between gap-2 p-3 bg-muted rounded-lg">
                    <div className="flex items-center gap-3 min-w-0">
                      <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{file.name}</p>
                        <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="flex-shrink-0"
                      onClick={() => setPendingFiles((prev) => prev.filter((_, i) => i !== index))}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
              <Button onClick={handleUpload} disabled={isUploading} className="w-full">
                {isUploading ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4 mr-2" />
                    Upload ({pendingFiles.length})
                  </>
                )}
              </Button>
            </div>
          )}

          {uploadedFilenames.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Uploaded ({uploadedFilenames.length})</p>
              <ul className="space-y-1">
                {uploadedFilenames.map((filename) => (
                  <li key={filename} className="flex items-center gap-2 text-sm text-muted-foreground">
                    <FileText className="w-4 h-4 flex-shrink-0" />
                    <span className="truncate">{filename}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 2. Key staff */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">2. Key staff</CardTitle>
          <CardDescription>List the key staff names and their current roles or titles.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {staff.map((member, index) => (
            <div key={index} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_auto] gap-3 items-end">
              <div className="space-y-1">
                <Label htmlFor={`staff-name-${index}`} className="text-xs">
                  Name
                </Label>
                <Input
                  id={`staff-name-${index}`}
                  value={member.name}
                  placeholder="e.g. Scott"
                  onChange={(e) => updateStaff(index, 'name', e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor={`staff-role-${index}`} className="text-xs">
                  Role / title
                </Label>
                <Input
                  id={`staff-role-${index}`}
                  value={member.role_title ?? ''}
                  placeholder="e.g. Director"
                  onChange={(e) => updateStaff(index, 'role_title', e.target.value)}
                />
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => removeStaffRow(index)}
                disabled={staff.length === 1}
                aria-label="Remove staff member"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          ))}
          <Button variant="outline" size="sm" onClick={addStaffRow}>
            <Plus className="w-4 h-4 mr-2" />
            Add staff member
          </Button>
        </CardContent>
      </Card>

      {/* 3. Responsibilities and notes */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">3. Responsibilities, org charts and notes</CardTitle>
          <CardDescription>
            Paste any existing responsibilities lists, org charts or notes about what each person
            currently does.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea
            value={pastedNotes}
            onChange={(e) => setPastedNotes(e.target.value)}
            placeholder={'Scott — client delivery, invoicing (1hr per week), quoting...\nMary — calendar management, client liaison...'}
            className="min-h-[180px]"
          />
        </CardContent>
      </Card>

      {/* 4. Confirm roles */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">4. Roles to include</CardTitle>
          <CardDescription>
            Confirm which roles must be included in the Roles &amp; Responsibilities matrix.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {roleCandidates.length === 0 ? (
            <p className="text-sm text-muted-foreground">Add staff members above to choose roles.</p>
          ) : (
            roleCandidates.map((role) => (
              <div key={role} className="flex items-center gap-3">
                <Checkbox
                  id={`role-${role}`}
                  checked={includedRoles.includes(role)}
                  onCheckedChange={(checked) => toggleRole(role, checked === true)}
                />
                <Label htmlFor={`role-${role}`} className="font-normal cursor-pointer">
                  {role}
                </Label>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Button onClick={handleContinue} disabled={isSaving || isUploading} size="lg" className="w-full">
        {isSaving ? (
          <>
            <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            Saving...
          </>
        ) : (
          <>
            Continue to extraction
            <ArrowRight className="w-4 h-4 ml-2" />
          </>
        )}
      </Button>
    </div>
  );
}
