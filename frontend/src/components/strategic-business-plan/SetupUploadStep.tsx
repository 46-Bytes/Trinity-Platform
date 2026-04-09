import { useState, useRef, useCallback } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { uploadFiles, saveSetup, createPlan, resetPlanData } from '@/store/slices/strategicBusinessPlanReducer';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Upload, FileText, X, Loader2, Info } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

interface SetupUploadStepProps {
  planId: string | null;
  engagementId?: string;
  onComplete: () => void;
  isLoading: boolean;
}

export function SetupUploadStep({ planId, engagementId, onComplete, isLoading }: SetupUploadStepProps) {
  const dispatch = useAppDispatch();
  const currentPlan = useAppSelector((s) => s.strategicBusinessPlan.currentPlan);

  // Form state — pre-populated from saved plan data when navigating back
  const [clientName, setClientName] = useState(currentPlan?.client_name || '');
  const [industry, setIndustry] = useState(currentPlan?.industry || '');
  const [planningHorizon, setPlanningHorizon] = useState(currentPlan?.planning_horizon || '');
  const [targetAudience, setTargetAudience] = useState(currentPlan?.target_audience || '');
  const [additionalContext, setAdditionalContext] = useState(currentPlan?.additional_context || '');

  // File state
  const [files, setFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (selectedFiles: FileList | null) => {
    if (!selectedFiles) return;
    const fileArray = Array.from(selectedFiles);
    const validFiles = fileArray.filter((file) => {
      if (file.size > 100 * 1024 * 1024) {
        toast.error(`File ${file.name} exceeds 100MB limit`);
        return false;
      }
      return true;
    });
    setFiles((prev) => [...prev, ...validFiles]);
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

  const formValid = clientName.trim() && industry.trim() && planningHorizon && targetAudience.trim() && files.length > 0;

  const handleSubmit = async () => {
    if (!formValid) return;

    try {
      let activePlanId = planId;

      if (activePlanId) {
        // Plan already exists — reset all generated data before re-uploading
        await dispatch(resetPlanData(activePlanId)).unwrap();
      } else {
        // Create plan for the first time
        const result = await dispatch(createPlan({ engagementId })).unwrap();
        activePlanId = result.plan_id;
      }

      // Upload files
      if (files.length > 0 && activePlanId) {
        await dispatch(uploadFiles({
          planId: activePlanId,
          files,
        })).unwrap();
      }

      // Save setup
      if (activePlanId) {
        await dispatch(saveSetup({
          planId: activePlanId,
          data: {
            clientName,
            industry,
            planningHorizon,
            targetAudience,
            additionalContext: additionalContext || undefined,
          },
        })).unwrap();
      }

      toast.success('Setup complete! Moving to cross-analysis.');
      onComplete();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to save setup');
    }
  };

  return (
    <div className="space-y-6">
      {/* Background Information */}
      <Card>
        <CardHeader>
          <CardTitle>Background Information</CardTitle>
          <CardDescription>
            Provide the context needed to build the Strategic Business Plan
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="clientName">Client Name *</Label>
              <Input
                id="clientName"
                value={clientName}
                onChange={(e) => setClientName(e.target.value)}
                placeholder="e.g. ABC Corporation"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="industry">Industry *</Label>
              <Input
                id="industry"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                placeholder="e.g. Manufacturing, Professional Services"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="planningHorizon">Planning Horizon *</Label>
              <Select value={planningHorizon} onValueChange={setPlanningHorizon}>
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
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="additionalContext">Additional Context (optional)</Label>
            <Textarea
              id="additionalContext"
              value={additionalContext}
              onChange={(e) => setAdditionalContext(e.target.value)}
              placeholder="Any additional context, priorities, or notes for the plan..."
              rows={3}
            />
          </div>
        </CardContent>
      </Card>

      {/* File Upload */}
      <Card>
        <CardHeader>
          <CardTitle>Upload Source Materials</CardTitle>
          <CardDescription>
            Upload documents that will form the basis of the Strategic Business Plan.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 text-blue-800 text-sm">
            <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
            <p>
              For best results, upload a completed Strategy Workshop Workbook alongside any diagnostic
              reports and supporting materials.
            </p>
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
            <Upload className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
            {isDragOver ? (
              <p className="text-primary font-medium">Drop files here...</p>
            ) : (
              <div>
                <p className="text-sm font-medium mb-2">Drag and drop files here, or click to select</p>
                <p className="text-xs text-muted-foreground">
                  Supports PDF, DOCX, XLSX, PPTX, TXT, CSV, and images (max 100MB per file)
                </p>
              </div>
            )}
          </div>

          {files.length > 0 && (
            <div className="space-y-2">
              <h3 className="text-sm font-medium">Selected Files ({files.length})</h3>
              <div className="space-y-2 max-h-72 overflow-y-auto">
                {files.map((file, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-muted rounded-lg gap-3">
                    <div className="flex items-center space-x-3 flex-1 min-w-0">
                      <FileText className="w-5 h-5 text-muted-foreground flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{file.name}</p>
                        <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                      </div>
                    </div>
                    <Button variant="ghost" size="icon" onClick={() => removeFile(index)} className="flex-shrink-0">
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <Button onClick={handleSubmit} disabled={!formValid || isLoading} className="w-full" size="lg">
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Uploading & saving...
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
