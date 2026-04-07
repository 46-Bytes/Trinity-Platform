import { useState } from 'react';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  draftSection,
  reviseSection,
  editSection,
  approveSection,
} from '@/store/slices/strategicBusinessPlanReducer';
import type { SBPSection } from '@/store/slices/strategicBusinessPlanReducer';
import { PLAN_SECTIONS } from './sectionConfig';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { BlockEditor } from './BlockEditor';
import {
  Loader2,
  CheckCircle2,
  RefreshCw,
  PenLine,
  ArrowRight,
  SkipForward,
  Save,
} from 'lucide-react';
import { toast } from 'sonner';

interface SectionEditorProps {
  planId: string;
  section: SBPSection;
  sectionIndex: number;
  totalSections: number;
  onNext: () => void;
  onSkip: () => void;
}

export function SectionEditor({
  planId,
  section,
  sectionIndex,
  totalSections,
  onNext,
  onSkip,
}: SectionEditorProps) {
  const dispatch = useAppDispatch();
  const { isDraftingSection } = useAppSelector((s) => s.strategicBusinessPlan);
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(section.content || '');
  const [editedImplications, setEditedImplications] = useState(section.strategic_implications || '');
  const [revisionNotes, setRevisionNotes] = useState('');
  const [showRevisionInput, setShowRevisionInput] = useState(false);

  const config = PLAN_SECTIONS.find((c) => c.key === section.key);

  const handleDraft = async () => {
    await dispatch(draftSection({ planId, sectionKey: section.key }));
  };

  const handleRevise = async () => {
    if (!revisionNotes.trim()) {
      toast.error('Please provide revision notes');
      return;
    }
    await dispatch(reviseSection({ planId, sectionKey: section.key, revisionNotes }));
    setRevisionNotes('');
    setShowRevisionInput(false);
  };

  const handleSaveEdit = async () => {
    await dispatch(
      editSection({
        planId,
        sectionKey: section.key,
        content: editedContent,
        strategicImplications: config?.hasDiagnosticImplications ? editedImplications : undefined,
      }),
    );
    setIsEditing(false);
    toast.success('Section updated');
  };

  const handleApprove = async () => {
    await dispatch(approveSection({ planId, sectionKey: section.key }));
    toast.success(`${section.title} approved`);
    onNext();
  };

  // Not yet drafted
  if (section.status === 'pending') {
    return (
      <Card className="flex-1">
        <CardHeader>
          <CardTitle>{sectionIndex + 1}. {section.title}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center py-12 space-y-4">
          {isDraftingSection ? (
            <>
              <Loader2 className="w-10 h-10 animate-spin text-primary" />
              <p className="text-muted-foreground">Drafting section...</p>
            </>
          ) : (
            <>
              <p className="text-muted-foreground text-center max-w-md">
                This section has not been drafted yet. Click below to generate it using the uploaded materials and cross-analysis.
              </p>
              <Button onClick={handleDraft} size="lg">
                <PenLine className="w-4 h-4 mr-2" />
                Draft This Section
              </Button>
              {!config?.required && (
                <Button variant="ghost" size="sm" onClick={onSkip}>
                  <SkipForward className="w-4 h-4 mr-2" />
                  Skip (Optional)
                </Button>
              )}
            </>
          )}
        </CardContent>
      </Card>
    );
  }

  // Drafting in progress
  if (section.status === 'drafting' || isDraftingSection) {
    return (
      <Card className="flex-1">
        <CardHeader>
          <CardTitle>{sectionIndex + 1}. {section.title}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Loader2 className="w-10 h-10 animate-spin text-primary mb-4" />
          <p className="text-muted-foreground">Drafting section content...</p>
        </CardContent>
      </Card>
    );
  }

  // Approved
  if (section.status === 'approved') {
    return (
      <Card className="flex-1">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-600" />
              {sectionIndex + 1}. {section.title}
            </CardTitle>
            <Badge variant="outline" className="bg-green-100 text-green-800">Approved</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: section.content || '' }} />
          {section.strategic_implications && (
            <div className="border-t pt-4 mt-4">
              <h4 className="font-semibold text-sm mb-2">Strategic Implications</h4>
              <div className="prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: section.strategic_implications }} />
            </div>
          )}
          {sectionIndex < totalSections - 1 && (
            <Button variant="outline" onClick={onNext}>
              <ArrowRight className="w-4 h-4 mr-2" />
              Next Section
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  // Drafted / Revision requested — main review state
  return (
    <Card className="flex-1">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{sectionIndex + 1}. {section.title}</CardTitle>
          <Badge variant="outline">
            {section.status === 'revision_requested' ? 'Revision requested' : 'Draft ready'}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Content */}
        {isEditing ? (
          <div className="space-y-4">
            <BlockEditor
              html={editedContent}
              onChange={setEditedContent}
              label="Section Content"
            />
            {config?.hasDiagnosticImplications && (
              <div className="border-t pt-4">
                <BlockEditor
                  html={editedImplications}
                  onChange={setEditedImplications}
                  label="Strategic Implications"
                />
              </div>
            )}
            <div className="flex gap-2 pt-2">
              <Button onClick={handleSaveEdit} size="sm">
                <Save className="w-4 h-4 mr-1" />
                Save Changes
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setEditedContent(section.content || '');
                  setEditedImplications(section.strategic_implications || '');
                  setIsEditing(false);
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div>
            <div className="prose prose-sm max-w-none border rounded-lg p-4 bg-muted/30" dangerouslySetInnerHTML={{ __html: section.content || '' }} />
            {section.strategic_implications && (
              <div className="border rounded-lg p-4 bg-muted/30 mt-3">
                <h4 className="font-semibold text-sm mb-2">Strategic Implications</h4>
                <div className="prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: section.strategic_implications }} />
              </div>
            )}
          </div>
        )}

        {/* Revision request */}
        {showRevisionInput && (
          <div className="border rounded-lg p-4 space-y-3">
            <h4 className="font-medium text-sm">Revision Notes</h4>
            <Textarea
              value={revisionNotes}
              onChange={(e) => setRevisionNotes(e.target.value)}
              placeholder="Describe what you'd like changed..."
              rows={3}
            />
            <div className="flex gap-2">
              <Button onClick={handleRevise} size="sm" disabled={isDraftingSection}>
                {isDraftingSection ? <Loader2 className="w-4 h-4 mr-1 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-1" />}
                Request Revision
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setShowRevisionInput(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Action buttons */}
        {!isEditing && !showRevisionInput && (
          <div className="flex gap-3 pt-2">
            <Button onClick={handleApprove} className="flex-1">
              <CheckCircle2 className="w-4 h-4 mr-2" />
              Approve
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setEditedContent(section.content || '');
                setEditedImplications(section.strategic_implications || '');
                setIsEditing(true);
              }}
            >
              <PenLine className="w-4 h-4 mr-2" />
              Edit
            </Button>
            <Button variant="outline" onClick={() => setShowRevisionInput(true)}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Request Revision
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
