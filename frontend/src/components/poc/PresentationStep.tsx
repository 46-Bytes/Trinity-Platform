/**
 * Phase 3 – Presentation Generator Step
 *
 * After the Excel task planner (Phase 2), the advisor generates a branded
 * PowerPoint deck from the diagnostic report data. Slides are AI-generated,
 * reviewed / edited per-slide, then exported as .pptx.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Loader2,
  AlertCircle,
  Download,
  Presentation,
  CheckCircle2,
  Edit3,
  Eye,
  ChevronDown,
  ChevronUp,
  ArrowLeft,
  Sparkles,
  Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// ─── Types ──────────────────────────────────────────────────────────────

interface PresentationSlide {
  index: number;
  type: string;
  title: string;
  subtitle?: string;
  bullets?: string[];
  finding?: string[];
  recommendation_bullets?: string[];
  outcome?: string[];
  rows?: Array<{ rec: number; title: string; timing: string; outcome: string }>;
  approved: boolean;
}

interface PresentationStepProps {
  projectId: string;
  onBack: () => void;
  className?: string;
}

// ─── Slide-type display labels ──────────────────────────────────────────

const SLIDE_TYPE_LABELS: Record<string, string> = {
  title: 'Title Slide',
  executive_summary: 'Executive Summary',
  structure: 'How Recommendations Are Structured',
  recommendation: 'Recommendation',
  timeline: 'Implementation Timeline',
  next_steps: 'Next Steps',
};

const SLIDE_TYPE_COLOURS: Record<string, string> = {
  title: 'bg-blue-100 text-blue-800',
  executive_summary: 'bg-indigo-100 text-indigo-800',
  structure: 'bg-purple-100 text-purple-800',
  recommendation: 'bg-emerald-100 text-emerald-800',
  timeline: 'bg-amber-100 text-amber-800',
  next_steps: 'bg-rose-100 text-rose-800',
};

// ─── Component ──────────────────────────────────────────────────────────

export default function PresentationStep({
  projectId,
  onBack,
  className,
}: PresentationStepProps) {
  // State
  const [slides, setSlides] = useState<PresentationSlide[]>([]);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSlide, setExpandedSlide] = useState<number | null>(null);
  const [editingSlide, setEditingSlide] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<PresentationSlide>>({});
  const [savingSlide, setSavingSlide] = useState(false);
  const [loaded, setLoaded] = useState(false);

  // ── Auth ──
  const getAuthHeaders = (): Record<string, string> => {
    const token = localStorage.getItem('auth_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  // ── Load existing slides on mount ──
  const loadExistingSlides = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/poc/${projectId}`, {
        headers: { ...getAuthHeaders() },
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        const existing =
          data?.project?.presentation_slides?.slides || [];
        if (existing.length > 0) {
          setSlides(existing);
        }
      }
    } catch {
      // non-critical – we just won't pre-populate
    } finally {
      setLoaded(true);
    }
  }, [projectId]);

  useEffect(() => {
    loadExistingSlides();
  }, [loadExistingSlides]);

  // ── Generate ──
  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/poc/${projectId}/presentation/generate`,
        {
          method: 'POST',
          headers: { ...getAuthHeaders() },
          credentials: 'include',
        }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Failed to generate slides');
      }
      const data = await res.json();
      setSlides(data.slides || []);
      setExpandedSlide(null);
      setEditingSlide(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  // ── Toggle approve ──
  const toggleApprove = async (index: number) => {
    const slide = slides[index];
    if (!slide) return;

    const newApproved = !slide.approved;
    // Optimistic update
    setSlides((prev) =>
      prev.map((s, i) => (i === index ? { ...s, approved: newApproved } : s))
    );

    try {
      await fetch(
        `${API_BASE_URL}/api/poc/${projectId}/presentation/slides/${index}/edit`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders(),
          },
          credentials: 'include',
          body: JSON.stringify({ approved: newApproved }),
        }
      );
    } catch {
      // Revert on error
      setSlides((prev) =>
        prev.map((s, i) =>
          i === index ? { ...s, approved: !newApproved } : s
        )
      );
    }
  };

  // ── Edit ──
  const startEditing = (index: number) => {
    const slide = slides[index];
    setEditingSlide(index);
    setExpandedSlide(index);
    setEditDraft({ ...slide });
  };

  const cancelEditing = () => {
    setEditingSlide(null);
    setEditDraft({});
  };

  const saveEdit = async () => {
    if (editingSlide === null) return;
    setSavingSlide(true);
    setError(null);

    try {
      const res = await fetch(
        `${API_BASE_URL}/api/poc/${projectId}/presentation/slides/${editingSlide}/edit`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders(),
          },
          credentials: 'include',
          body: JSON.stringify(editDraft),
        }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Failed to save edit');
      }
      const data = await res.json();
      setSlides(data.slides || []);
      setEditingSlide(null);
      setEditDraft({});
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSavingSlide(false);
    }
  };

  // ── Export ──
  const handleExport = async () => {
    setExporting(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/poc/${projectId}/presentation/export/pptx`,
        {
          method: 'POST',
          headers: { ...getAuthHeaders() },
          credentials: 'include',
        }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Failed to export presentation');
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      a.download = match?.[1] || 'Presentation.pptx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setExporting(false);
    }
  };

  // ── Derived stats ──
  const approvedCount = slides.filter((s) => s.approved).length;
  const totalCount = slides.length;
  const progressPct = totalCount > 0 ? (approvedCount / totalCount) * 100 : 0;

  // ── Delete slide ──
  const deleteSlide = async (index: number) => {
    const slide = slides[index];
    if (!slide) return;

    // Simple confirmation to avoid accidental deletes
    const confirmed = window.confirm(
      `Remove slide ${index + 1}: "${slide.title}" from this presentation?`,
    );
    if (!confirmed) return;

    setError(null);
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/poc/${projectId}/presentation/slides/${index}`,
        {
          method: 'DELETE',
          headers: { ...getAuthHeaders() },
          credentials: 'include',
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || 'Failed to delete slide');
      }
      const data = await res.json();
      setSlides(data.slides || []);
      setExpandedSlide(null);
      setEditingSlide(null);
      setEditDraft({});
    } catch (err: any) {
      setError(err.message);
    }
  };

  // ── Render ──
  return (
    <div className={cn('space-y-6', className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Presentation className="h-6 w-6 text-[#1a365d]" />
            Phase 3 – Step 1: Presentation Generator
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Generate, review, and export a branded PowerPoint deck from your
            diagnostic report.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={onBack}>
          <ArrowLeft className="h-4 w-4 mr-1" /> Back to Phase 2
        </Button>
      </div>

      {/* Error banner */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="py-3 flex items-start gap-2">
            <AlertCircle className="h-5 w-5 text-red-500 mt-0.5 shrink-0" />
            <p className="text-sm text-red-700">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Generate / progress bar */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Slide Generation</CardTitle>
          <CardDescription>
            {slides.length === 0
              ? 'Click below to generate presentation slides using AI.'
              : `${totalCount} slides generated. ${approvedCount} approved.`}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {slides.length > 0 && (
            <div className="space-y-1">
              <div className="flex justify-between text-xs text-gray-500">
                <span>Approval progress</span>
                <span>
                  {approvedCount}/{totalCount}
                </span>
              </div>
              <Progress value={progressPct} className="h-2" />
            </div>
          )}

          <div className="flex gap-3">
            <Button
              onClick={handleGenerate}
              disabled={generating}
              className="bg-[#1a365d] hover:bg-[#1a365d]/90"
            >
              {generating ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generating…
                </>
              ) : slides.length > 0 ? (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Regenerate Slides
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Generate Slides
                </>
              )}
            </Button>

            {slides.length > 0 && (
              <Button
                onClick={handleExport}
                disabled={exporting}
                variant="outline"
              >
                {exporting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Exporting…
                  </>
                ) : (
                  <>
                    <Download className="h-4 w-4 mr-2" />
                    Export to PowerPoint
                  </>
                )}
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Slide list */}
      {slides.length > 0 && (
        <div className="space-y-3">
          {slides.map((slide, idx) => {
            const isExpanded = expandedSlide === idx;
            const isEditing = editingSlide === idx;

            return (
              <Card
                key={idx}
                className={cn(
                  'transition-shadow',
                  slide.approved && 'border-green-300 bg-green-50/30'
                )}
              >
                {/* Card header — always visible */}
                <CardHeader
                  className="py-3 cursor-pointer select-none"
                  onClick={() => {
                    if (!isEditing) {
                      setExpandedSlide(isExpanded ? null : idx);
                    }
                  }}
                >
                  <div className="flex items-center gap-3">
                    {/* Left: number + badge + title (allow truncation) */}
                    <span className="text-xs font-mono text-gray-400 w-6 text-right shrink-0">
                      {idx + 1}
                    </span>
                    <Badge
                      variant="secondary"
                      className={cn(
                        'text-xs shrink-0 whitespace-nowrap',
                        SLIDE_TYPE_COLOURS[slide.type] ||
                          'bg-gray-100 text-gray-700'
                      )}
                    >
                      {SLIDE_TYPE_LABELS[slide.type] || slide.type}
                    </Badge>
                    <span className="font-medium text-sm text-gray-900 truncate min-w-0">
                      {slide.title}
                    </span>

                    {/* Right: action buttons (never shrink) */}
                    <div className="flex items-center gap-1 shrink-0 ml-auto">
                      {slide.approved && (
                        <CheckCircle2 className="h-4 w-4 text-green-600" />
                      )}
                      <Button
                        size="sm"
                        variant={slide.approved ? 'default' : 'outline'}
                        className={cn(
                          'h-7 text-xs',
                          slide.approved &&
                            'bg-green-600 hover:bg-green-700 text-white'
                        )}
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleApprove(idx);
                        }}
                      >
                        {slide.approved ? 'Approved' : 'Approve'}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs text-red-600 hover:text-red-700"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteSlide(idx);
                        }}
                        title="Delete slide"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (isEditing) {
                            cancelEditing();
                          } else {
                            startEditing(idx);
                          }
                        }}
                        title={isEditing ? 'Cancel editing' : 'Edit slide'}
                      >
                        {isEditing ? (
                          <Eye className="h-3.5 w-3.5" />
                        ) : (
                          <Edit3 className="h-3.5 w-3.5" />
                        )}
                      </Button>
                      {isExpanded ? (
                        <ChevronUp className="h-4 w-4 text-gray-400" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-gray-400" />
                      )}
                    </div>
                  </div>
                </CardHeader>

                {/* Card body — expanded */}
                {isExpanded && (
                  <CardContent className="pt-0 pb-4 space-y-3">
                    {isEditing ? (
                      <SlideEditor
                        slide={editDraft as PresentationSlide}
                        onChange={setEditDraft}
                        onSave={saveEdit}
                        onCancel={cancelEditing}
                        saving={savingSlide}
                      />
                    ) : (
                      <SlidePreview slide={slide} />
                    )}
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {loaded && slides.length === 0 && !generating && (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center text-gray-500">
            <Presentation className="h-12 w-12 mx-auto mb-3 text-gray-300" />
            <p className="font-medium">No slides generated yet</p>
            <p className="text-sm mt-1">
              Click "Generate Slides" above to create your presentation.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ─── Sub-components ─────────────────────────────────────────────────────

function SlidePreview({ slide }: { slide: PresentationSlide }) {
  return (
    <div className="text-sm text-gray-700 space-y-3">
      {slide.subtitle && (
        <p className="italic text-gray-500">{slide.subtitle}</p>
      )}

      {slide.bullets && slide.bullets.length > 0 && (
        <ul className="list-disc list-inside space-y-1">
          {slide.bullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      )}

      {slide.finding && slide.finding.length > 0 && (
        <div>
          <p className="font-semibold text-[#1a365d] mb-1">Finding</p>
          <ul className="list-disc list-inside space-y-1">
            {slide.finding.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </div>
      )}

      {slide.recommendation_bullets &&
        slide.recommendation_bullets.length > 0 && (
          <div>
            <p className="font-semibold text-[#1a365d] mb-1">Recommendation</p>
            <ul className="list-disc list-inside space-y-1">
              {slide.recommendation_bullets.map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </div>
        )}

      {slide.outcome && slide.outcome.length > 0 && (
        <div>
          <p className="font-semibold text-[#1a365d] mb-1">Outcome</p>
          <ul className="list-disc list-inside space-y-1">
            {slide.outcome.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </div>
      )}

      {slide.rows && slide.rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs border">
            <thead className="bg-[#1a365d] text-white">
              <tr>
                <th className="px-3 py-2 text-left">#</th>
                <th className="px-3 py-2 text-left">Recommendation</th>
                <th className="px-3 py-2 text-left">Timing</th>
                <th className="px-3 py-2 text-left">Key Outcome</th>
              </tr>
            </thead>
            <tbody>
              {slide.rows.map((row, i) => (
                <tr
                  key={i}
                  className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}
                >
                  <td className="px-3 py-1.5 border-t">{row.rec}</td>
                  <td className="px-3 py-1.5 border-t">{row.title}</td>
                  <td className="px-3 py-1.5 border-t">{row.timing}</td>
                  <td className="px-3 py-1.5 border-t">{row.outcome}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

interface SlideEditorProps {
  slide: PresentationSlide;
  onChange: (draft: Partial<PresentationSlide>) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
}

function SlideEditor({
  slide,
  onChange,
  onSave,
  onCancel,
  saving,
}: SlideEditorProps) {
  const updateField = (key: string, value: any) => {
    onChange({ ...slide, [key]: value });
  };

  const updateBulletList = (key: string, bullets: string[]) => {
    onChange({ ...slide, [key]: bullets });
  };

  return (
    <div className="space-y-4">
      {/* Title */}
      <div>
        <label className="text-xs font-medium text-gray-500 mb-1 block">
          Title
        </label>
        <Input
          value={slide.title || ''}
          onChange={(e) => updateField('title', e.target.value)}
          className="text-sm"
        />
      </div>

      {/* Subtitle (title slide) */}
      {slide.type === 'title' && (
        <div>
          <label className="text-xs font-medium text-gray-500 mb-1 block">
            Subtitle
          </label>
          <Input
            value={slide.subtitle || ''}
            onChange={(e) => updateField('subtitle', e.target.value)}
            className="text-sm"
          />
        </div>
      )}

      {/* Bullets */}
      {(slide.bullets !== undefined || ['executive_summary', 'structure', 'next_steps'].includes(slide.type)) && (
        <BulletEditor
          label="Bullets"
          bullets={slide.bullets || []}
          onChange={(val) => updateBulletList('bullets', val)}
        />
      )}

      {/* Finding */}
      {slide.finding !== undefined && (
        <BulletEditor
          label="Finding"
          bullets={slide.finding || []}
          onChange={(val) => updateBulletList('finding', val)}
        />
      )}

      {/* Recommendation bullets */}
      {slide.recommendation_bullets !== undefined && (
        <BulletEditor
          label="Recommendation"
          bullets={slide.recommendation_bullets || []}
          onChange={(val) => updateBulletList('recommendation_bullets', val)}
        />
      )}

      {/* Outcome */}
      {slide.outcome !== undefined && (
        <BulletEditor
          label="Outcome"
          bullets={slide.outcome || []}
          onChange={(val) => updateBulletList('outcome', val)}
        />
      )}

      {/* Actions */}
      <div className="flex gap-2 pt-2">
        <Button
          size="sm"
          onClick={onSave}
          disabled={saving}
          className="bg-[#1a365d] hover:bg-[#1a365d]/90"
        >
          {saving ? (
            <>
              <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
              Saving…
            </>
          ) : (
            'Save Changes'
          )}
        </Button>
        <Button size="sm" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function BulletEditor({
  label,
  bullets,
  onChange,
}: {
  label: string;
  bullets: string[];
  onChange: (updated: string[]) => void;
}) {
  return (
    <div>
      <label className="text-xs font-medium text-gray-500 mb-1 block">
        {label} (one per line)
      </label>
      <Textarea
        rows={Math.max(3, bullets.length + 1)}
        value={bullets.join('\n')}
        onChange={(e) =>
          onChange(
            e.target.value
              .split('\n')
              .map((s) => s.trimStart())
          )
        }
        className="text-sm font-mono"
      />
    </div>
  );
}
