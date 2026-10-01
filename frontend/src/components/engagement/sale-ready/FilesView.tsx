import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronDown, ChevronRight, Download, ExternalLink, Eye, File as FileIcon, Folder, Trash2,
  Upload, Users,
} from 'lucide-react';
import { toast } from 'sonner';

import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  fetchEngagementBuyers, fetchReleasedFolders, setReleasedFolders,
} from '@/store/slices/buyerAdminReducer';
import {
  type DataRoomFile,
  deleteDataRoomFile,
  downloadDataRoomFile,
  fetchDataRoom,
  uploadDDItemFile,
} from '@/store/slices/dataRoomReducer';
import { fetchDDChecklist } from '@/store/slices/saleReadyReducer';
import { BuyerAccessPanel } from './BuyerAccessPanel';
import { BuyerPreviewView } from './BuyerPreviewView';
import { formatShortDate } from './saleReadyDisplay';
import type { DDItem } from './types';

interface FilesViewProps {
  items: DDItem[];
  engagementId: string;
  /** Owner mode: folders and files are visible, but nothing can be changed and
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

// The shortest gap between two focus-driven refreshes. The Drive sync runs on
// a five-minute cycle, so anything tighter than this re-fetches data that
// cannot have changed.
const FOCUS_REFRESH_THROTTLE_MS = 30_000;

function formatSize(bytes: number | null): string {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * The data room: one folder per DD category and sub-item, backed by Benchmark's
 * Google Drive. Trinity indexes and serves the files; it stores none of them.
 *
 * Everything to do with buyers lives on this tab, as in the mockup: the release
 * checkbox sits beside the folder it releases, and buyer management is a panel
 * behind the "Buyer access" button, collapsed until asked for. Owners can see
 * this tab, so both are gated on readOnly.
 *
 * Drive links ("Open folder in Drive" and an arrow per file) are for advisors
 * only. Owners upload and download through Trinity and never see Drive; the
 * server sends them no links. No buyer ever receives a Drive link: their
 * schemas have no field for one and their router cannot reach these endpoints.
 */
export function FilesView({ items, engagementId, readOnly = false }: FilesViewProps) {
  const dispatch = useAppDispatch();
  const { buyers, releasedFolders, isSaving } = useAppSelector((s) => s.buyerAdmin);
  const { status, files, folders: driveFolders, dataRoomWebLink, isUploading } =
    useAppSelector((s) => s.dataRoom);
  const [showBuyers, setShowBuyers] = useState(false);
  const [preview, setPreview] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<DataRoomFile | null>(null);
  // The DD item a Files-tab upload is attached to. Falls back to the folder's first item.
  const [uploadItemId, setUploadItemId] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  // Seeded with the mount fetch below, so returning to the tab straight away
  // does not immediately re-fetch what was just loaded.
  const lastRefresh = useRef<number>(Date.now());

  useEffect(() => {
    // The release list endpoint is advisor-only; the owner reads the same
    // flags from the data room response instead (see `released` below).
    if (!readOnly) dispatch(fetchReleasedFolders(engagementId));
    dispatch(fetchDataRoom(engagementId));
  }, [dispatch, engagementId, readOnly]);

  // Owned here rather than in the panel: the header shows the count before
  // the panel has ever been opened.
  useEffect(() => {
    if (!readOnly) dispatch(fetchEngagementBuyers(engagementId));
  }, [dispatch, engagementId, readOnly]);

  /**
   * Refresh when the advisor comes back to the tab.
   *
   * Files can arrive without Trinity being touched: someone drops one into
   * the Drive folder and the background sync indexes it minutes later. This
   * view otherwise only fetches on mount, so the obvious workflow - switch
   * to Drive, add a file, switch back - would show a stale list until a
   * reload.
   *
   * Throttled, because alt-tabbing is not a request for fresh data and a
   * visible window can fire both events at once.
   */
  useEffect(() => {
    const refresh = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastRefresh.current < FOCUS_REFRESH_THROTTLE_MS) return;
      lastRefresh.current = now;
      dispatch(fetchDataRoom(engagementId));
    };

    // Both, because they cover different moves: visibilitychange for
    // switching tabs, focus for switching applications.
    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', refresh);
    return () => {
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', refresh);
    };
  }, [dispatch, engagementId]);

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
    () => new Set(
      readOnly
        ? driveFolders
            .filter((f) => f.released_to_buyers)
            .map((f) => folderKey(f.category_code, f.sub_item_code))
        : releasedFolders.map((f) => folderKey(f.category_code, f.sub_item_code))
    ),
    [readOnly, driveFolders, releasedFolders]
  );

  const countsByFolder = useMemo(() => {
    const counts = new Map<string, number>();
    for (const f of files) {
      if (!f.category_code || !f.sub_item_code) continue;
      const key = folderKey(f.category_code, f.sub_item_code);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return counts;
  }, [files]);

  const [openCategory, setOpenCategory] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const activeCategory = openCategory ?? categories[0]?.code ?? null;
  const category = categories.find((c) => c.code === activeCategory);
  const folder = category?.subs.find((s) => s.code === selected) ?? category?.subs[0];
  const uploadItem = folder?.items.find((i) => i.id === uploadItemId) ?? folder?.items[0] ?? null;

  const folderFiles = useMemo(
    () => (folder
      ? files.filter((f) => f.category_code === folder.categoryCode && f.sub_item_code === folder.code)
      : []),
    [files, folder]
  );

  const fail = (e: unknown) => toast.error(e instanceof Error ? e.message : String(e));

  const toggleRelease = (target: SubFolder, on: boolean) => {
    const key = folderKey(target.categoryCode, target.code);
    const next = on
      ? [...releasedFolders, { category_code: target.categoryCode, sub_item_code: target.code }]
      : releasedFolders.filter((f) => folderKey(f.category_code, f.sub_item_code) !== key);
    dispatch(setReleasedFolders({ engagementId, folders: next }))
      .unwrap()
      .then(() => toast.success(on ? 'Folder released to buyers' : 'Folder hidden from buyers'))
      .catch(fail);
  };

  // Every chosen file is attached to the selected DD item; only that item moves to In progress.
  const upload = (chosen: FileList | null) => {
    if (!chosen?.length || !uploadItem) return;
    Promise.all(
      [...chosen].map((file) =>
        dispatch(uploadDDItemFile({ engagementId, itemId: uploadItem.id, file })).unwrap()
      )
    )
      .then(() => {
        toast.success(chosen.length === 1 ? 'File uploaded' : `${chosen.length} files uploaded`);
        dispatch(fetchDDChecklist(engagementId));
      })
      .catch(fail);
    if (fileInput.current) fileInput.current.value = '';
  };

  const liveBuyers = buyers.filter((b) => b.status !== 'revoked');
  const driveReady = status?.connected ?? false;

  // The selected folder if Trinity has created it in Drive, otherwise the data
  // room itself. A folder with no files yet does not exist in Drive.
  const openInDriveHref =
    (folder
      ? driveFolders.find(
          (f) => f.category_code === folder.categoryCode && f.sub_item_code === folder.code
        )?.drive_web_link
      : null) ?? dataRoomWebLink;

  if (preview && !readOnly) {
    return (
      <BuyerPreviewView
        releasedFolders={releasedFolders}
        ddItems={items}
        files={files}
        buyerName={
          liveBuyers[0]
            ? [liveBuyers[0].name ?? liveBuyers[0].email, liveBuyers[0].company].filter(Boolean).join(', ')
            : null
        }
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
              {driveReady
                ? 'Drive holds the files; Trinity indexes them and serves them. Nothing is stored on Trinity’s servers.'
                : status?.message ??
                  'Drive holds the files; Trinity indexes them. The Drive connection is not set up yet, so uploads are unavailable.'}
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {!readOnly && (
            <Button variant="outline" size="sm" asChild={!!openInDriveHref} disabled={!openInDriveHref}>
              {openInDriveHref ? (
                <a href={openInDriveHref} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="mr-1.5 h-3.5 w-3.5" /> Open folder in Drive
                </a>
              ) : (
                <span>
                  <ExternalLink className="mr-1.5 h-3.5 w-3.5" /> Open folder in Drive
                </span>
              )}
            </Button>
          )}
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
          {/* Advisors and owners (sellers) both upload, each file to one DD item. */}
          <>
              <input
                ref={fileInput}
                type="file"
                multiple
                className="hidden"
                onChange={(e) => upload(e.target.files)}
              />
              <Select
                value={uploadItem?.id ?? ''}
                onValueChange={setUploadItemId}
                disabled={!folder || isUploading}
              >
                <SelectTrigger aria-label="Upload to DD item" className="h-9 w-full text-xs sm:w-56">
                  <SelectValue placeholder="Choose a DD item" />
                </SelectTrigger>
                <SelectContent>
                  {(folder?.items ?? []).map((i) => (
                    <SelectItem key={i.id} value={i.id}>
                      {i.document_required ?? i.item_key}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                size="sm"
                disabled={!driveReady || isUploading || !uploadItem}
                onClick={() => fileInput.current?.click()}
              >
                <Upload className="mr-1.5 h-3.5 w-3.5" />
                {isUploading ? 'Uploading…' : 'Upload'}
              </Button>
          </>
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
                  c.subs.map((s) => {
                    const count = countsByFolder.get(folderKey(s.categoryCode, s.code)) ?? 0;
                    return (
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
                          <Eye className="h-3.5 w-3.5 flex-shrink-0 text-success" aria-label="Released to buyers" />
                        )}
                        {count > 0 && (
                          <span className="flex-shrink-0 rounded-full bg-muted px-1.5 text-[10px] font-semibold text-muted-foreground">
                            {count}
                          </span>
                        )}
                      </button>
                    );
                  })}
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

            {folderFiles.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                {driveReady
                  ? 'No files in this folder yet. Upload one above, or drop it into the folder in Drive.'
                  : 'No files in this folder yet. Uploads become available once Google Drive is connected.'}
              </div>
            ) : (
              <ul className="space-y-1.5">
                {folderFiles.map((file) => (
                  <li
                    key={file.id}
                    className="flex items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm"
                  >
                    <FileIcon className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-hidden />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{file.file_name}</span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {[
                          formatSize(file.file_size),
                          file.uploaded_by_name,
                          file.source === 'drive' ? 'Added in Drive' : null,
                        ]
                          .filter(Boolean)
                          .join(' · ')}
                      </span>
                      <span className="block truncate text-xs text-muted-foreground">
                        Added {formatShortDate(file.created_at) ?? '—'} · Linked DD item:{' '}
                        {file.dd_item_document ?? 'folder only'}
                      </span>
                    </span>
                    {!readOnly && file.drive_web_link && (
                      <a
                        href={file.drive_web_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        title="Open the file in Drive"
                        aria-label={`Open ${file.file_name} in Drive`}
                        className="inline-grid h-8 w-8 flex-shrink-0 place-items-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                      >
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden />
                      </a>
                    )}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="flex-shrink-0"
                      aria-label={`Download ${file.file_name}`}
                      onClick={() =>
                        downloadDataRoomFile(engagementId, file.id, file.file_name).catch(fail)
                      }
                    >
                      <Download className="h-3.5 w-3.5" />
                    </Button>
                    {!readOnly && (
                      <Button
                        variant="ghost"
                        size="sm"
                        className="flex-shrink-0"
                        aria-label={`Remove ${file.file_name}`}
                        onClick={() => setConfirmDelete(file)}
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>

      <AlertDialog open={confirmDelete !== null} onOpenChange={(open) => !open && setConfirmDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove this document?</AlertDialogTitle>
            <AlertDialogDescription>
              {confirmDelete?.file_name}
              <span className="mt-2 block">
                It is moved to the bin in Drive and disappears from Trinity, including for any buyer
                who could see this folder. The record of who opened it is kept.
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!confirmDelete) return;
                dispatch(deleteDataRoomFile({ engagementId, mediaId: confirmDelete.id }))
                  .unwrap()
                  .then(() => toast.success('Document removed'))
                  .catch(fail);
                setConfirmDelete(null);
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
