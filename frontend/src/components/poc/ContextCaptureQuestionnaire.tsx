/**
 * POC: Context Capture Questionnaire Component
 * Step 2 of the file upload POC - collects client context and preferences
 */
import React from 'react';
import { ArrowLeft, ArrowRight, CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

export interface QuestionnaireData {
  clientName: string;
  industry: string;
  companySize: string;
  locations: string;
  exclusions: string;
  constraints: string;
  preferredRanking: string;
  strategicPriorities: string;
  excludeSaleReadiness: boolean;
}

interface UploadedFile {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'success' | 'error';
  progress: number;
  fileId?: string;
  error?: string;
  openaiInfo?: {
    bytes?: number;
    purpose?: string;
    created_at?: number;
  };
}

interface ContextCaptureQuestionnaireProps {
  questionnaireData: QuestionnaireData;
  onQuestionnaireChange: (field: keyof QuestionnaireData, value: string | boolean) => void;
  onSubmit: () => void;
  onBack: () => void;
  files: UploadedFile[];
  successCount: number;
  isSubmitting: boolean;
}

export function ContextCaptureQuestionnaire({
  questionnaireData,
  onQuestionnaireChange,
  onSubmit,
  onBack,
  files,
  successCount,
  isSubmitting,
}: ContextCaptureQuestionnaireProps) {
  const isFormValid =
    questionnaireData.clientName &&
    questionnaireData.industry &&
    questionnaireData.companySize &&
    questionnaireData.locations &&
    questionnaireData.strategicPriorities;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">Context Capture</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Client Name */}
        <div className="space-y-2">
          <Label htmlFor="clientName">Client Name *</Label>
          <Input
            id="clientName"
            value={questionnaireData.clientName}
            onChange={(e) => onQuestionnaireChange('clientName', e.target.value)}
            placeholder="Enter client name"
            required
          />
        </div>

        {/* Industry */}
        <div className="space-y-2">
          <Label htmlFor="industry">Industry *</Label>
          <Input
            id="industry"
            value={questionnaireData.industry}
            onChange={(e) => onQuestionnaireChange('industry', e.target.value)}
            placeholder="e.g., Technology, Healthcare, Finance"
            required
          />
        </div>

        {/* Company Size */}
        <div className="space-y-2">
          <Label htmlFor="companySize">Company Size *</Label>
          <Select
            value={questionnaireData.companySize}
            onValueChange={(value) => onQuestionnaireChange('companySize', value)}
          >
            <SelectTrigger id="companySize">
              <SelectValue placeholder="Select company size" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="startup">1-10</SelectItem>
              <SelectItem value="medium">11-15</SelectItem>
              <SelectItem value="large">51+</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Locations */}
        <div className="space-y-2">
          <Label htmlFor="locations">Locations *</Label>
          <Input
            id="locations"
            value={questionnaireData.locations}
            onChange={(e) => onQuestionnaireChange('locations', e.target.value)}
            placeholder="e.g., Sydney, Melbourne, Brisbane"
            required
          />
        </div>
      </div>

      {/* Exclusions */}
      <div className="space-y-2">
        <Label htmlFor="exclusions">Exclusions</Label>
        <Textarea
          id="exclusions"
          value={questionnaireData.exclusions}
          onChange={(e) => onQuestionnaireChange('exclusions', e.target.value)}
          placeholder="List any areas or topics that should be excluded from the analysis..."
          rows={3}
        />
      </div>

      {/* Constraints */}
      <div className="space-y-2">
        <Label htmlFor="constraints">Constraints</Label>
        <Textarea
          id="constraints"
          value={questionnaireData.constraints}
          onChange={(e) => onQuestionnaireChange('constraints', e.target.value)}
          placeholder="List any constraints or limitations that should be considered..."
          rows={3}
        />
      </div>

      {/* Preferred Ranking of Top Findings */}
      <div className="space-y-2">
        <Label htmlFor="preferredRanking">Preferred Ranking of Top Findings</Label>
        <Textarea
          id="preferredRanking"
          value={questionnaireData.preferredRanking}
          onChange={(e) => onQuestionnaireChange('preferredRanking', e.target.value)}
          placeholder="How should findings be ranked? (e.g., by priority, impact, ease of implementation, etc.)"
          rows={3}
        />
      </div>

      {/* Strategic Priorities */}
      <div className="space-y-2">
        <Label htmlFor="strategicPriorities">Strategic Priorities for Next 12 Months *</Label>
        <Textarea
          id="strategicPriorities"
          value={questionnaireData.strategicPriorities}
          onChange={(e) => onQuestionnaireChange('strategicPriorities', e.target.value)}
          placeholder="Describe the key strategic priorities and goals for the next 12 months..."
          rows={4}
          required
        />
      </div>

      {/* Exclude Sale-Readiness */}
      <div className="flex items-center space-x-2">
        <Checkbox
          id="excludeSaleReadiness"
          checked={questionnaireData.excludeSaleReadiness}
          onCheckedChange={(checked) => onQuestionnaireChange('excludeSaleReadiness', checked === true)}
        />
        <Label
          htmlFor="excludeSaleReadiness"
          className="text-sm font-normal cursor-pointer"
        >
          Exclude sale-readiness from analysis
        </Label>
      </div>

      {/* Summary of Uploaded Files */}
      {successCount > 0 && (
        <div className="p-4 bg-muted rounded-lg">
          <p className="text-sm font-medium mb-2">Uploaded Files ({successCount}):</p>
          <div className="space-y-1">
            {files
              .filter((f) => f.status === 'success' && f.fileId)
              .map((f) => (
                <div key={f.id} className="text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-3 h-3 text-green-600" />
                  <span className="text-muted-foreground">{f.file.name}</span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Submit Button */}
      <div className="flex justify-end gap-3 pt-4 border-t">
        <Button
          variant="outline"
          onClick={onBack}
          disabled={isSubmitting}
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back
        </Button>
        <Button
          onClick={onSubmit}
          disabled={!isFormValid || isSubmitting}
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Submitting...
            </>
          ) : (
            <>
              Confirm & Continue
              <ArrowRight className="w-4 h-4 ml-2" />
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

