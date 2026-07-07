import { useEffect, useState, useCallback } from 'react';
import { ShieldCheck, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';

import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';
import {
  getFieldConfigs,
  updateFieldConfigs,
  AIFieldPrivacyItem,
  QuestionnaireType,
} from '@/lib/aiPrivacyService';

import saleReadyQuestions from '@/questions/questions_sale_ready.json';
import valuBuilderQuestions from '@/questions/questions_ValueBuilder.json';

interface QuestionDef {
  name: string;
  title?: string;
  type: string;
}

interface PageDef {
  name: string;
  title: string;
  elements: QuestionDef[];
}

function extractPages(json: { pages: { name: string; title: string; elements: QuestionDef[] }[] }): PageDef[] {
  return json.pages.map((page) => ({
    name: page.name,
    title: page.title || page.name,
    elements: page.elements ?? [],
  }));
}

const ALL_PAGES: Record<QuestionnaireType, PageDef[]> = {
  sale_ready: extractPages(saleReadyQuestions as any),
  value_builder: extractPages(valuBuilderQuestions as any),
};

const TYPE_LABELS: Record<QuestionnaireType, string> = {
  sale_ready: 'Sale Ready',
  value_builder: 'Value Builder',
};

const TYPE_BADGE_COLOUR: Record<string, string> = {
  text: 'bg-blue-100 text-blue-800',
  dropdown: 'bg-purple-100 text-purple-800',
  radiogroup: 'bg-orange-100 text-orange-800',
  checkbox: 'bg-yellow-100 text-yellow-800',
  comment: 'bg-gray-100 text-gray-700',
  matrixdynamic: 'bg-pink-100 text-pink-800',
  multipletext: 'bg-teal-100 text-teal-800',
  boolean: 'bg-indigo-100 text-indigo-800',
  file: 'bg-red-100 text-red-800',
};

function typeBadge(type: string) {
  return TYPE_BADGE_COLOUR[type] ?? 'bg-gray-100 text-gray-700';
}

interface TabPanelProps {
  questionnaireType: QuestionnaireType;
}

function PrivacyTabPanel({ questionnaireType }: TabPanelProps) {
  const pages = ALL_PAGES[questionnaireType];
  const allQuestions = pages.flatMap((p) => p.elements);

  const [configs, setConfigs] = useState<Map<string, boolean>>(new Map());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setLoading(true);
    getFieldConfigs(questionnaireType)
      .then((items: AIFieldPrivacyItem[]) => {
        const map = new Map<string, boolean>();
        items.forEach((item) => map.set(item.field_name, item.include_in_ai));
        setConfigs(map);
      })
      .catch(() => toast.error('Failed to load privacy settings'))
      .finally(() => setLoading(false));
  }, [questionnaireType]);

  const getIncluded = useCallback(
    (fieldName: string) => configs.get(fieldName) ?? true,
    [configs],
  );

  const toggle = async (fieldName: string, value: boolean) => {
    // Optimistic update
    const newConfigs = new Map(configs).set(fieldName, value);
    setConfigs(newConfigs);
    setSaving(true);
    try {
      const fields: AIFieldPrivacyItem[] = allQuestions.map((q) => ({
        field_name: q.name,
        include_in_ai: newConfigs.get(q.name) ?? true,
      }));
      await updateFieldConfigs(questionnaireType, fields);
    } catch {
      // Revert on failure
      setConfigs((prev) => new Map(prev).set(fieldName, !value));
      toast.error('Failed to save privacy settings');
    } finally {
      setSaving(false);
    }
  };

  const totalExcluded = allQuestions.filter((q) => !getIncluded(q.name)).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex items-center justify-between rounded-lg border border-border bg-muted/40 px-4 py-3">
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{allQuestions.length}</span> fields total
          {totalExcluded > 0 && (
            <>
              {' · '}
              <span className="font-medium text-destructive">{totalExcluded}</span> excluded from AI
            </>
          )}
        </p>
        {saving && (
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Saving…
          </span>
        )}
      </div>

      {/* Modules accordion */}
      <Accordion type="multiple" className="space-y-2">
        {pages.map((page, index) => {
          const excludedInPage = page.elements.filter((q) => !getIncluded(q.name)).length;
          return (
            <AccordionItem
              key={page.name}
              value={page.name}
              className="rounded-xl border border-border overflow-hidden shadow-sm"
            >
              <AccordionTrigger className="px-5 py-4 hover:no-underline hover:bg-muted/40 data-[state=open]:bg-primary/5 data-[state=open]:border-b data-[state=open]:border-border transition-colors">
                <div className="flex items-center gap-3 flex-1 min-w-0 mr-3">
                  <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-muted text-xs font-semibold text-muted-foreground shrink-0">
                    {index + 1}
                  </span>
                  <span className="font-semibold text-sm text-foreground">{page.title}</span>
                  <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground shrink-0">
                    {page.elements.length} fields
                  </span>
                  {excludedInPage > 0 && (
                    <Badge variant="destructive" className="text-xs shrink-0">
                      {excludedInPage} excluded
                    </Badge>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent className="pb-0">
                <div className="divide-y divide-border">
                  {page.elements.map((q) => {
                    const included = getIncluded(q.name);
                    return (
                      <div
                        key={q.name}
                        className={`flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-muted/20 ${
                          !included ? 'bg-destructive/5' : ''
                        }`}
                      >
                        <Switch
                          checked={included}
                          onCheckedChange={(val) => toggle(q.name, val)}
                          id={`switch-${questionnaireType}-${q.name}`}
                        />
                        <label
                          htmlFor={`switch-${questionnaireType}-${q.name}`}
                          className="flex-1 cursor-pointer min-w-0"
                        >
                          <p
                            className={`text-sm font-medium leading-snug ${
                              included ? 'text-foreground' : 'text-muted-foreground line-through'
                            }`}
                          >
                            {q.title || q.name}
                          </p>
                        </label>
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${typeBadge(q.type)}`}
                        >
                          {q.type}
                        </span>
                        {!included && (
                          <Badge variant="destructive" className="text-xs shrink-0">
                            Not sent to AI
                          </Badge>
                        )}
                      </div>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>
          );
        })}
      </Accordion>
    </div>
  );
}

export default function AIPrivacyPage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="p-2 rounded-lg bg-primary/10 shrink-0">
          <ShieldCheck className="w-5 h-5 text-primary" />
        </div>
        <div>
          <h1 className="text-xl font-semibold text-foreground">AI Data Privacy Controls</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Toggle which questionnaire fields are included in AI processing. Disabled fields are
            still saved and shown to users but are stripped from the Claude payload.
          </p>
        </div>
      </div>

      {/* Questionnaire tabs */}
      <Tabs defaultValue="sale_ready">
        <TabsList>
          {(Object.keys(TYPE_LABELS) as QuestionnaireType[]).map((t) => (
            <TabsTrigger key={t} value={t}>
              {TYPE_LABELS[t]}
            </TabsTrigger>
          ))}
        </TabsList>

        {(Object.keys(TYPE_LABELS) as QuestionnaireType[]).map((t) => (
          <TabsContent key={t} value={t} className="mt-4">
            <PrivacyTabPanel questionnaireType={t} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
