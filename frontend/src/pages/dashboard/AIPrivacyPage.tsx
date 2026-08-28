import { useEffect, useState, useCallback } from 'react';
import { ShieldCheck, Loader2, Eye, EyeOff, Search, Database } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { Switch } from '@/components/ui/switch';
import { Input } from '@/components/ui/input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from '@/components/ui/accordion';
import { StatCard } from '@/components/ui/stat-card';
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

// Human-friendly field-type labels (raw SurveyJS type names are developer-y).
const TYPE_LABEL: Record<string, string> = {
  text: 'Text',
  dropdown: 'Choice',
  radiogroup: 'Choice',
  checkbox: 'Multi-select',
  comment: 'Long text',
  matrixdynamic: 'Table',
  multipletext: 'Fields',
  boolean: 'Yes / No',
  file: 'File',
};

function typeLabel(type: string) {
  return TYPE_LABEL[type] ?? type;
}

type FilterMode = 'all' | 'shared' | 'private';

const FILTERS: { value: FilterMode; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'shared', label: 'Shared' },
  { value: 'private', label: 'Private' },
];

interface TabPanelProps {
  questionnaireType: QuestionnaireType;
}

function PrivacyTabPanel({ questionnaireType }: TabPanelProps) {
  const pages = ALL_PAGES[questionnaireType];
  const allQuestions = pages.flatMap((p) => p.elements);

  const [configs, setConfigs] = useState<Map<string, boolean>>(new Map());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<FilterMode>('all');
  const [openItems, setOpenItems] = useState<string[]>([]);

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

  const isIncluded = useCallback(
    (fieldName: string) => configs.get(fieldName) ?? true,
    [configs],
  );

  const persist = async (nextConfigs: Map<string, boolean>, errorMessage: string) => {
    const previous = configs;
    setConfigs(nextConfigs);
    setSaving(true);
    try {
      const fields: AIFieldPrivacyItem[] = allQuestions.map((q) => ({
        field_name: q.name,
        include_in_ai: nextConfigs.get(q.name) ?? true,
      }));
      await updateFieldConfigs(questionnaireType, fields);
    } catch {
      setConfigs(previous); // Revert on failure
      toast.error(errorMessage);
    } finally {
      setSaving(false);
    }
  };

  const toggle = (fieldName: string, value: boolean) =>
    persist(new Map(configs).set(fieldName, value), 'Failed to save privacy settings');

  const toggleCategory = (page: PageDef, value: boolean) => {
    const next = new Map(configs);
    page.elements.forEach((el) => next.set(el.name, value));
    return persist(next, `Failed to update ${page.title}`);
  };

  const total = allQuestions.length;
  const totalExcluded = allQuestions.filter((q) => !isIncluded(q.name)).length;
  const sharedCount = total - totalExcluded;
  const sharedPct = total ? Math.round((sharedCount / total) * 100) : 0;

  // Filter pages/fields by the search query and the shared/private filter.
  const q = query.trim().toLowerCase();
  const visiblePages = pages
    .map((page, index) => {
      const elements = page.elements.filter((el) => {
        const matchesQuery = !q || (el.title || el.name).toLowerCase().includes(q);
        const included = isIncluded(el.name);
        const matchesFilter =
          filter === 'all' || (filter === 'shared' ? included : !included);
        return matchesQuery && matchesFilter;
      });
      return { page, index, elements };
    })
    .filter((p) => p.elements.length > 0);

  // While searching/filtering, force-open every matching category.
  const filtering = q !== '' || filter !== 'all';
  const openValues = filtering ? visiblePages.map((v) => v.page.name) : openItems;

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-28 rounded-xl bg-muted" />
          ))}
        </div>
        <div className="h-16 rounded-xl bg-muted" />
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-14 rounded-xl bg-muted" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard title="Total Fields" value={total} icon={Database} iconColor="text-primary" />
        <StatCard
          title="Shared with AI"
          value={sharedCount}
          icon={Eye}
          iconColor="text-accent"
          change={`${sharedPct}% of all fields`}
        />
        <StatCard
          title="Kept Private"
          value={totalExcluded}
          icon={EyeOff}
          iconColor="text-warning"
          change={totalExcluded > 0 ? `${100 - sharedPct}% held back` : 'Nothing hidden'}
        />
      </div>

      {/* Progress meter */}
      <div className="rounded-xl border border-border bg-card p-4 space-y-2 shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-foreground">Data shared with AI</span>
          <div className="flex items-center gap-3">
            {saving && (
              <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Saving…
              </span>
            )}
            <span className="text-sm font-semibold text-accent">{sharedPct}%</span>
          </div>
        </div>
        <div className="progress-trinity">
          <div className="progress-trinity-bar" style={{ width: `${sharedPct}%` }} />
        </div>
      </div>

      {/* Search + filter */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search fields…"
            className="pl-9"
          />
        </div>
        <div className="inline-flex rounded-lg border border-border bg-muted/40 p-1 shrink-0">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              onClick={() => setFilter(f.value)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-md transition-colors',
                filter === f.value
                  ? 'bg-background text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Modules accordion */}
      {visiblePages.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border py-16 text-center text-sm text-muted-foreground">
          No fields match your search.
        </div>
      ) : (
        <Accordion
          type="multiple"
          value={openValues}
          onValueChange={setOpenItems}
          className="space-y-2"
        >
          {visiblePages.map(({ page, index, elements }) => {
            const privateInPage = page.elements.filter((el) => !isIncluded(el.name)).length;
            const allShared = privateInPage === 0;
            return (
              <AccordionItem
                key={page.name}
                value={page.name}
                className="group rounded-xl border border-border overflow-hidden shadow-sm bg-card"
              >
                <div className="flex items-center pr-4 transition-colors group-data-[state=open]:bg-primary/5 group-data-[state=open]:border-b group-data-[state=open]:border-border">
                  <div className="flex-1 min-w-0">
                    <AccordionTrigger className="w-full px-5 py-4 hover:no-underline">
                      <div className="flex items-center gap-3 min-w-0 mr-3">
                        <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-muted text-xs font-semibold text-muted-foreground shrink-0">
                          {index + 1}
                        </span>
                        <span className="font-semibold text-sm text-foreground text-left truncate">
                          {page.title}
                        </span>
                        <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-muted-foreground shrink-0">
                          {page.elements.length} fields
                        </span>
                        {privateInPage > 0 && (
                          <span className="inline-flex items-center gap-1 rounded-full bg-warning/10 px-2.5 py-0.5 text-xs font-medium text-warning shrink-0">
                            <EyeOff className="w-3 h-3" />
                            {privateInPage} private
                          </span>
                        )}
                      </div>
                    </AccordionTrigger>
                  </div>
                  <div
                    className="flex items-center gap-2 pl-3 ml-1 shrink-0 border-l border-border/60"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <span className="hidden sm:inline text-xs text-muted-foreground">
                      {allShared ? 'All shared' : 'Share all'}
                    </span>
                    <Switch
                      checked={allShared}
                      onCheckedChange={(val) => toggleCategory(page, val)}
                      aria-label={`Share all fields in ${page.title} with AI`}
                    />
                  </div>
                </div>
                <AccordionContent className="pb-0">
                  <div className="divide-y divide-border">
                    {elements.map((el) => {
                      const included = isIncluded(el.name);
                      return (
                        <div
                          key={el.name}
                          className={cn(
                            'flex items-center gap-4 px-5 py-3.5 transition-colors',
                            included ? 'hover:bg-muted/30' : 'bg-warning/5 hover:bg-warning/10',
                          )}
                        >
                          <Switch
                            checked={included}
                            onCheckedChange={(val) => toggle(el.name, val)}
                            id={`switch-${questionnaireType}-${el.name}`}
                          />
                          <label
                            htmlFor={`switch-${questionnaireType}-${el.name}`}
                            className="flex-1 cursor-pointer min-w-0"
                          >
                            <p
                              className={cn(
                                'text-sm font-medium leading-snug',
                                included ? 'text-foreground' : 'text-muted-foreground',
                              )}
                            >
                              {el.title || el.name}
                            </p>
                          </label>
                          <span className="hidden md:inline-flex items-center rounded-md bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground shrink-0">
                            {typeLabel(el.type)}
                          </span>
                          <span
                            className={cn(
                              'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium shrink-0',
                              included ? 'bg-accent/10 text-accent' : 'bg-warning/10 text-warning',
                            )}
                          >
                            {included ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                            <span className="hidden md:inline">{included ? 'Shared' : 'Private'}</span>
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>
      )}
    </div>
  );
}

export default function AIPrivacyPage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-start gap-4 rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="p-2.5 rounded-xl bg-accent/10 shrink-0">
          <ShieldCheck className="w-6 h-6 text-accent" />
        </div>
        <div>
          <h1 className="text-xl font-heading font-bold text-foreground">AI Data Privacy Controls</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Toggle which questionnaire fields are included in AI processing. Fields kept private are
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
