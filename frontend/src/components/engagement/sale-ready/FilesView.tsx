import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, ExternalLink, Eye, Folder, Upload, Users } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  fetchEngagementBuyers,
  fetchReleasedFolders,
  setReleasedFolders,
} from '@/store/slices/buyerAdminReducer';
import { BuyerAccessPanel } from './BuyerAccessPanel';
import { BuyerPreviewView } from './BuyerPreviewView';
import type { DDItem } from './types';

interface FilesViewProps {
  items: DDItem[];
  engagementId: string;
  /** Owner mode: the eye markers still show, but nothing can be released and
   *  buyer management is not offered at all. */
  readOnly?: boolean;
}

interface SubFolder {
  code: string;
  categoryCode: string;
  label: string;
  stageTitle: string;
  items: DDItem[];
}

const folderKey = (category: string, sub: string) => `${category}|${sub}`;

/**
 * The data room: one folder per DD category and sub-item. Files will live in
 * Benchmark's Google Drive; until that integration is confirmed the folders are
 * shown empty and upload is unavailable. Trinity storage is deliberately not used.
 *
 * Everything to do with buyers lives on this tab, as in the mockup: the folder
 * release checkbox sits beside the folder itself, and buyer management is a
 * panel behind the "Buyer access" button, collapsed until asked for. Owners can
 * see this tab, so both are gated on readOnly.
 */
export function FilesView({ items, engagementId, readOnly = false }: FilesViewProps) {
  const dispatch = useAppDispatch();
  const { buyers, releasedFolders, isSaving } = useAppSelector((s) => s.buyerAdmin);
  // The mockup keeps buyer access on this tab, collapsed until asked for.
  const [showBuyers, setShowBuyers] = useState(false);
  const [preview, setPreview] = useState(false);

  useEffect(() => {
    dispatch(fetchReleasedFolders(engagementId));
  }, [dispatch, engagementId]);

  // Owned here rather than in the panel: the header shows the count before
  // the panel has ever been opened.
  useEffect(() => {
    if (!readOnly) dispatch(fetchEngagementBuyers(engagementId));
  }, [dispatch, engagementId, readOnly]);

  const categories = useMemo(() => {
    const map = new Map<string, { label: string; subs: Map<string, SubFolder> }>();
    for (const item of items) {
      const cat = map.get(item.category_code) ?? { label: `${item.category_code}. ${item.category}`, subs: new Map() };
      const sub = cat.subs.get(item.sub_item_code) ?? {
        code: item.sub_item_code,
        categoryCode: item.category_code,
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

  const released = useMemo(
    () => new Set(releasedFolders.map((f) => folderKey(f.category_code, f.sub_item_code))),
    [releasedFolders]
  );

  const [openCategory, setOpenCategory] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const activeCategory = openCategory ?? categories[0]?.code ?? null;
  const category = categories.find((c) => c.code === activeCategory);
  const folder = category?.subs.find((s) => s.code === selected) ?? category?.subs[0];

  const toggleRelease = (target: SubFolder, on: boolean) => {
    const key = folderKey(target.categoryCode, target.code);
    const next = on
      ? [...releasedFolders, { category_code: target.categoryCode, sub_item_code: target.code }]
      : releasedFolders.filter((f) => folderKey(f.category_code, f.sub_item_code) !== key);
    dispatch(setReleasedFolders({ engagementId, folders: next }))
      .unwrap()
      .then(() => toast.success(on ? 'Folder released to buyers' : 'Folder hidden from buyers'))
      .catch((e) => toast.error(String(e)));
  };

  const liveBuyers = buyers.filter((b) => b.status !== 'revoked');

  if (preview && !readOnly) {
    return (
      <BuyerPreviewView
        releasedFolders={releasedFolders}
        ddItems={items}
        buyerName={liveBuyers[0]?.name ?? liveBuyers[0]?.email ?? null}
        onBack={() => setPreview(false)}
      />
    );
  }

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
          {!readOnly && (
            <Button
              variant="outline"
              size="sm"
              aria-expanded={showBuyers}
              onClick={() => setShowBuyers((open) => !open)}
            >
              <Users className="mr-1.5 h-3.5 w-3.5" />
              Buyer access{liveBuyers.length ? ` (${liveBuyers.length})` : ''}
            </Button>
          )}
          <Button size="sm" disabled>
            <Upload className="mr-1.5 h-3.5 w-3.5" /> Upload
          </Button>
        </div>
      </div>

      {showBuyers && !readOnly && (
        <BuyerAccessPanel
          engagementId={engagementId}
          onClose={() => setShowBuyers(false)}
          onPreview={() => setPreview(true)}
        />
      )}

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[22rem_1fr]">
        <nav className="card-trinity p-3 sm:p-4" aria-label="Data room folders">
          <p className="mb-2 px-1.5 text-xs text-muted-foreground">
            One folder per DD category and sub-item. An eye means released to buyers.
          </p>
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
                        'flex w-full items-center gap-1.5 rounded-lg py-1.5 pl-9 pr-2 text-left text-xs hover:bg-muted/50',
                        folder?.code === s.code && 'bg-success/10 font-semibold text-success'
                      )}
                    >
                      <span className="min-w-0 flex-1 truncate">{s.label}</span>
                      {released.has(folderKey(s.categoryCode, s.code)) && (
                        <Eye
                          className="h-3.5 w-3.5 flex-shrink-0 text-success"
                          aria-label="Released to buyers"
                        />
                      )}
                    </button>
                  ))}
              </div>
            );
          })}
        </nav>

        {folder && (
          <section className="card-trinity p-4 sm:p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <h2 className="font-heading text-base font-semibold">{folder.label}</h2>
                <p className="text-xs text-muted-foreground">
                  {category?.label} · {folder.stageTitle}
                </p>
              </div>
              {!readOnly && (
                <Label className="flex flex-shrink-0 cursor-pointer items-center gap-2 text-xs font-medium">
                  <Checkbox
                    checked={released.has(folderKey(folder.categoryCode, folder.code))}
                    disabled={isSaving}
                    onCheckedChange={(v) => toggleRelease(folder, v === true)}
                  />
                  Visible to buyers
                </Label>
              )}
            </div>
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
