import { useState, useRef, useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { uploadFiles, saveSetup, createPlan, resetPlanData } from '@/store/slices/strategicBusinessPlanReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Upload, FileText, X, Loader2, Sparkles, Info, Check } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface SetupUploadStepProps {
  planId: string | null;
  engagementId?: string;
  onComplete: () => void;
  isLoading: boolean;
}

export function SetupUploadStep({ planId, engagementId, onComplete, isLoading }: SetupUploadStepProps) {
  const dispatch = useAppDispatch();
  const currentPlan = useAppSelector((s) => s.strategicBusinessPlan.currentPlan);
  const uploadedFiles = useAppSelector((s) => s.strategicBusinessPlan.uploadedFiles);

  const [files, setFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [extractionDone, setExtractionDone] = useState(false);
  const [uploadComplete, setUploadComplete] = useState(false);
  const [createdPlanId, setCreatedPlanId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Form fields — pre-populated from saved plan when navigating back
  const [clientName, setClientName] = useState(currentPlan?.client_name || '');
  const [industry, setIndustry] = useState(currentPlan?.industry || '');
  const [planningHorizon, setPlanningHorizon] = useState(currentPlan?.planning_horizon || '');
  const [targetAudience, setTargetAudience] = useState(currentPlan?.target_audience || '');
  const [additionalContext, setAdditionalContext] = useState(currentPlan?.additional_context || '');

  const handleFileSelect = (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;
    const valid = Array.from(selectedFiles).filter((f) => {
      if (f.size > 100 * 1024 * 1024) {
        toast.error(`${f.name} exceeds the 100 MB limit`);
        return false;
      }
      return true;
    });
    setFiles((prev) => [...prev, ...valid]);
  };

  const handleDragOver = useCallback((e: React.DragEvent) => { e.preventDefault(); setIsDragOver(true); }, []);
  const handleDragLeave = useCallback((e: React.DragEvent) => { e.preventDefault(); setIsDragOver(false); }, []);
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFileSelect(e.dataTransfer.files);
  }, []);

  const removeFile = (index: number) => setFiles((prev) => prev.filter((_, i) => i !== index));

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  };

  const handleUploadAndExtract = async () => {
    if (files.length === 0) return;
    setIsExtracting(true);
    try {
      let activePlanId = planId;

      if (activePlanId) {
        await dispatch(resetPlanData(activePlanId)).unwrap();
      } else {
        const result = await dispatch(createPlan({ engagementId })).unwrap();
        activePlanId = result.plan_id;
        setCreatedPlanId(activePlanId);
      }

      await dispatch(uploadFiles({ planId: activePlanId!, files })).unwrap();
      setUploadComplete(true);

      const token = localStorage.getItem('auth_token');
      const res = await fetch(
        `${API_BASE_URL}/api/strategic-business-plan/${activePlanId}/extract-setup`,
        { headers: { Authorization: `Bearer ${token}` }, credentials: 'include' },
      );

      if (res.ok) {
        const data = await res.json();
        const ex = data?.extracted || {};
        if (ex.clientName) setClientName(ex.clientName);
        if (ex.industry) setIndustry(ex.industry);
        if (ex.planningHorizon) setPlanningHorizon(ex.planningHorizon);
        if (ex.targetAudience) setTargetAudience(ex.targetAudience);
        if (ex.additionalContext) setAdditionalContext(ex.additionalContext);
        toast.success('Information extracted — review and confirm below');
        setExtractionDone(true);
      } else {
        toast.warning('Upload complete. Please fill in the background information manually.');
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setIsExtracting(false);
    }
  };

  const hasServerFiles = (currentPlan?.file_ids?.length ?? 0) > 0;
  const fieldsEnabled = hasServerFiles || uploadComplete;
  const formValid =
    clientName.trim() &&
    industry.trim() &&
    planningHorizon &&
    targetAudience.trim() &&
    (files.length > 0 || hasServerFiles);

  const handleSubmit = async () => {
    if (!formValid) return;
    setIsSaving(true);
    try {
      const activePlanId = planId || createdPlanId || currentPlan?.id;

      if (!activePlanId) {
        toast.error('Please upload your documents first.');
        return;
      }

      await dispatch(saveSetup({
        planId: activePlanId,
        data: { clientName, industry, planningHorizon, targetAudience, additionalContext: additionalContext || undefined },
      })).unwrap();

      toast.success('Setup complete! Moving to cross-analysis.');
      onComplete();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save setup');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* File Upload */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Source Materials</CardTitle>
          <CardDescription>
            Upload your strategy workbook and any supporting documents. Background information will be extracted automatically.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 text-blue-800 text-sm">
            <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <p>For best results, upload a completed Strategy Workshop Workbook alongside diagnostic reports and supporting materials.</p>
          </div>

          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={cn(
              'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors',
              isDragOver ? 'border-primary bg-primary/5' : 'border-muted-foreground/25 hover:border-primary/50',
            )}
          >
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx,.xlsx,.xls,.pptx,.txt,.csv,.png,.jpg,.jpeg"
              onChange={(e) => handleFileSelect(e.target.files)}
              className="hidden"
            />
            <Upload className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
            {isDragOver ? (
              <p className="text-primary font-medium">Drop files here…</p>
            ) : (
              <div>
                <p className="text-sm font-medium mb-1">Drag and drop files here, or click to select</p>
                <p className="text-xs text-muted-foreground">PDF, DOCX, XLSX, PPTX, TXT, CSV, images · max 100 MB per file</p>
              </div>
            )}
          </div>

          {files.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Selected files ({files.length})</p>
              <div className="space-y-1.5 max-h-52 overflow-y-auto">
                {files.map((file, index) => (
                  <div key={index} className="flex items-center gap-3 p-2.5 bg-muted rounded-lg">
                    <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{file.name}</p>
                      <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                    </div>
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => removeFile(index)}>
                      <X className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {hasServerFiles && files.length === 0 && uploadedFiles.length > 0 && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Uploaded files ({uploadedFiles.length})</p>
              <div className="space-y-1.5 max-h-52 overflow-y-auto">
                {uploadedFiles.map((f) => (
                  <div key={f.file_id} className="flex items-center gap-3 p-2.5 bg-muted rounded-lg">
                    <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{f.filename}</p>
                      <p className="text-xs text-muted-foreground">Uploaded</p>
                    </div>
                    <Check className="w-4 h-4 text-green-500 flex-shrink-0" />
                  </div>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">Select new files above to replace them.</p>
            </div>
          )}
          {hasServerFiles && files.length === 0 && uploadedFiles.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {currentPlan!.file_ids!.length} file{currentPlan!.file_ids!.length !== 1 ? 's' : ''} already uploaded.
              Select new files above to replace them.
            </p>
          )}

          {files.length > 0 && (
            <Button
              onClick={handleUploadAndExtract}
              disabled={isExtracting || extractionDone}
              className="w-full"
              size="lg"
            >
              {isExtracting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Uploading & extracting information…
                </>
              ) : extractionDone ? (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  Extraction Complete
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 mr-2" />
                  Upload & Extract Information
                </>
              )}
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Background Information */}
      <Card>
        <CardHeader>
          <CardTitle>Background Information</CardTitle>
          <CardDescription>
            Review and confirm the details below. Fields are pre-filled from your documents where possible.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {!fieldsEnabled && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 text-amber-800 text-sm border border-amber-200">
              <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <p>Upload your source materials above first — fields will be enabled after extraction.</p>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="clientName">Client Name *</Label>
              <Input
                id="clientName"
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                placeholder="e.g. ABC Corporation"
                disabled={isExtracting || !fieldsEnabled}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="industry">Industry *</Label>
              <Input
                id="industry"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                placeholder="e.g. Manufacturing, Professional Services"
                disabled={isExtracting || !fieldsEnabled}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="planningHorizon">Planning Horizon *</Label>
              <Select value={planningHorizon} onValueChange={setPlanningHorizon} disabled={isExtracting || !fieldsEnabled}>
                <SelectTrigger id="planningHorizon">
                  <SelectValue placeholder="Select planning horizon" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1-year">1 Year</SelectItem>
                  <SelectItem value="3-year">3 Years</SelectItem>
                  <SelectItem value="5-year">5 Years</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="targetAudience">Primary Audience *</Label>
              <Input
                id="targetAudience"
                value={targetAudience}
                onChange={(e) => setTargetAudience(e.target.value)}
                placeholder="e.g. Owners, Management Team, Bank"
                disabled={isExtracting || !fieldsEnabled}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="additionalContext">Additional Context <span className="text-muted-foreground font-normal">(optional)</span></Label>
            <Textarea
              id="additionalContext"
              value={additionalContext}
              onChange={(e) => setAdditionalContext(e.target.value)}
              placeholder="Any additional context, priorities, or notes for the plan…"
              rows={7}
              disabled={isExtracting || !fieldsEnabled}
            />
          </div>

          <Button
            onClick={handleSubmit}
            disabled={!formValid || isExtracting || isSaving}
            className="w-full"
            size="lg"
          >
            {isSaving ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Saving…
              </>
            ) : (
              'Continue to Cross-Analysis'
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
