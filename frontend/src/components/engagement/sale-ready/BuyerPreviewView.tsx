import { ArrowLeft, FolderOpen, Lock } from 'lucide-react';

import { Button } from '@/components/ui/button';
import type { ReleasedFolder } from '@/store/slices/buyerAdminReducer';
import type { DDItem } from './types';

interface BuyerPreviewViewProps {
  /** The released set, straight from the same state the release controls write to. */
  releasedFolders: ReleasedFolder[];
  /** The engagement's DD items, which name the folders. The buyer API names them the same way. */
  ddItems: DDItem[];
  /** Who the advisor is previewing as, when there is a buyer to name. */
  buyerName?: string | null;
  onBack: () => void;
}

const folderKey = (category: string, sub: string) => `${category}|${sub}`;

/**
 * The data room exactly as a buyer sees it, for an advisor to check before
 * releasing anything else.
 *
 * Fidelity is the whole point, so this reads the released set the advisor
 * already holds - the same rows `GET /api/buyer/me/folders` returns, because
 * both come from BuyerService.list_released_folders - and names folders from
 * the same DD items the buyer payload is named from. Nothing is fetched from
 * the buyer API, no buyer session is created and no permission is bypassed:
 * this is a rendering of state the advisor is already entitled to.
 *
 * Deliberately absent, because a buyer never receives them: the roadmap, tasks,
 * DD statuses, gap handling, notes, document registers and any storage path.
 */
export function BuyerPreviewView({
  releasedFolders,
  ddItems,
  buyerName,
  onBack,
}: BuyerPreviewViewProps) {
  const names = new Map<string, { category: string | null; subItem: string | null }>();
  for (const item of ddItems) {
    const key = folderKey(item.category_code, item.sub_item_code);
    if (!names.has(key)) names.set(key, { category: item.category, subItem: item.sub_item });
  }

  const folders = [...releasedFolders]
    .sort((a, b) =>
      a.category_code.localeCompare(b.category_code, undefined, { numeric: true }) ||
      a.sub_item_code.localeCompare(b.sub_item_code, undefined, { numeric: true })
    )
    .map((f) => ({ ...f, ...(names.get(folderKey(f.category_code, f.sub_item_code)) ?? {}) }));

  return (
    <div className="space-y-5">
      <div className="card-trinity flex flex-col gap-3 border-0 bg-foreground p-4 text-background sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide opacity-70">Buyer view</p>
          <h2 className="font-heading text-lg font-bold">Data room</h2>
          <p className="mt-1 max-w-2xl text-xs opacity-80">
            This is what a buyer sees{buyerName ? `, as ${buyerName}` : ''}. Read-only, released
            folders only. Files are served by Trinity, never linked from Drive, and every open is
            recorded.
          </p>
        </div>
        <Button variant="secondary" size="sm" className="flex-shrink-0" onClick={onBack}>
          <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
          Back to advisor view
        </Button>
      </div>

      <section className="card-trinity p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-heading text-base font-semibold">Released folders</h3>
          <span className="text-sm text-muted-foreground">
            {folders.length} folder{folders.length === 1 ? '' : 's'}
          </span>
        </div>

        {folders.length === 0 ? (
          <div className="py-10 text-center">
            <Lock className="mx-auto mb-2 h-5 w-5 text-muted-foreground" aria-hidden />
            <p className="text-sm text-muted-foreground">
              Nothing has been released yet, so a buyer would see an empty data room.
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Tick <span className="font-medium">Visible to buyers</span> on a folder to release it.
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {folders.map((folder) => (
              <li
                key={folderKey(folder.category_code, folder.sub_item_code)}
                className="flex items-center gap-3 rounded-lg border border-border px-3.5 py-3 text-sm"
              >
                <FolderOpen className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-hidden />
                <span className="font-mono text-xs text-muted-foreground">{folder.sub_item_code}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">
                    {folder.subItem ?? `Folder ${folder.sub_item_code}`}
                  </span>
                  {folder.category && (
                    <span className="block truncate text-xs text-muted-foreground">
                      {folder.category_code}. {folder.category}
                    </span>
                  )}
                </span>
                <span className="flex-shrink-0 text-xs text-muted-foreground">Empty</span>
              </li>
            ))}
          </ul>
        )}

        <p className="mt-4 text-xs text-muted-foreground">
          Folders are released, but the document store is not connected yet, so every folder is
          empty for a buyer too. Viewing and downloading arrive with the Google Drive integration.
        </p>
      </section>
    </div>
  );
}
