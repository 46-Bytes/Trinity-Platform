import { useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, ExternalLink, Folder, Upload } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { DDItem } from './types';

interface FilesViewProps {
  items: DDItem[];
}

interface SubFolder {
  code: string;
  label: string;
  stageTitle: string;
  items: DDItem[];
}

/**
 * The data room: one folder per DD category and sub-item. Files will live in
 * Benchmark's Google Drive; until that integration is confirmed the folders are
 * shown empty and upload is unavailable. Trinity storage is deliberately not used.
 */
export function FilesView({ items }: FilesViewProps) {
  const categories = useMemo(() => {
    const map = new Map<string, { label: string; subs: Map<string, SubFolder> }>();
    for (const item of items) {
      const cat = map.get(item.category_code) ?? { label: `${item.category_code}. ${item.category}`, subs: new Map() };
      const sub = cat.subs.get(item.sub_item_code) ?? {
        code: item.sub_item_code,
        label: `${item.sub_item_code} ${item.sub_item ?? ''}`.trim(),
        stageTitle: item.stage_title,
        items: [],
      };
      sub.items.push(item);
      cat.subs.set(item.sub_item_code, sub);
      map.set(item.category_code, cat);
    }
    return [...map.entries()].map(([code, c]) => ({ code, label: c.label, subs: [...c.subs.values()] }));
  }, [items]);

  const [openCategory, setOpenCategory] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const activeCategory = openCategory ?? categories[0]?.code ?? null;
  const category = categories.find((c) => c.code === activeCategory);
  const folder = category?.subs.find((s) => s.code === selected) ?? category?.subs[0];

  return (
    <div className="space-y-5">
      <div className="card-trinity flex flex-col gap-3 bg-muted/30 p-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div className="flex items-center gap-3">
          <span className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg bg-success/10 text-[11px] font-bold text-success">
            GD
          </span>
          <div>
            <p className="text-sm font-semibold">Files are stored in Benchmark Google Drive</p>
            <p className="text-xs text-muted-foreground">
              Drive holds the files; Trinity indexes them. The Drive connection is not set up yet, so folders are empty
              and uploads are unavailable.
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled>
            <ExternalLink className="mr-1.5 h-3.5 w-3.5" /> Open in Drive
          </Button>
          <Button size="sm" disabled>
            <Upload className="mr-1.5 h-3.5 w-3.5" /> Upload
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[22rem_1fr]">
        <nav className="card-trinity p-3 sm:p-4" aria-label="Data room folders">
          <p className="mb-2 px-1.5 text-xs text-muted-foreground">One folder per DD category and sub-item.</p>
          {categories.map((c) => {
            const open = c.code === activeCategory;
            return (
              <div key={c.code}>
                <button
                  type="button"
                  onClick={() => {
                    setOpenCategory(c.code);
                    setSelected(null);
                  }}
                  aria-expanded={open}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm font-medium hover:bg-muted/50',
                    open && 'bg-muted font-semibold'
                  )}
                >
                  {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                  <Folder className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                  <span className="min-w-0 truncate">{c.label}</span>
                </button>
                {open &&
                  c.subs.map((s) => (
                    <button
                      key={s.code}
                      type="button"
                      onClick={() => setSelected(s.code)}
                      className={cn(
                        'block w-full rounded-lg py-1.5 pl-9 pr-2 text-left text-xs hover:bg-muted/50',
                        folder?.code === s.code && 'bg-success/10 font-semibold text-success'
                      )}
                    >
                      {s.label}
                    </button>
                  ))}
              </div>
            );
          })}
        </nav>

        {folder && (
          <section className="card-trinity p-4 sm:p-6">
            <h2 className="font-heading text-base font-semibold">{folder.label}</h2>
            <p className="text-xs text-muted-foreground">
              {category?.label} · {folder.stageTitle}
            </p>
            <p className="mb-4 mt-3 text-xs text-muted-foreground">
              DD items in this folder: {folder.items.map((i) => i.document_required).join(' · ')}
            </p>
            <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              No files in this folder yet. Uploads here and from each DD item become available once Google Drive is
              connected.
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
