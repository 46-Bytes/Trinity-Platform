import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronDown, ChevronRight, Download, Eye, File as FileIcon, FolderOpen, Lock } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useAuth } from '@/context/AuthContext';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  type BuyerDocument,
  downloadBuyerDocument,
  fetchBuyerDocumentForView,
  fetchBuyerEngagement,
  fetchBuyerFolderContents,
  fetchBuyerFolders,
} from '@/store/slices/buyerReducer';

/** A document open in the viewer: PDFs and images by object URL, text as text. */
interface Viewing {
  doc: BuyerDocument;
  kind: 'pdf' | 'image' | 'text';
  url: string | null;
  text: string | null;
}

const showError = (e: unknown) => toast.error(e instanceof Error ? e.message : String(e));

/**
 * What a buyer sees when they sign in: the business they are looking at, and
 * the folders the advisor has released to them. Nothing else about the sale -
 * no roadmap, no tasks, no due diligence statuses, no advisor notes.
 *
 * Folders are empty until the data room is connected. That is stated on screen
 * rather than left to look broken.
 */
export default function BuyerDocumentsPage() {
  const dispatch = useAppDispatch();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { engagement, folders, contents, isLoading, error } = useAppSelector((s) => s.buyer);
  const [open, setOpen] = useState<string | null>(null);
  const [viewing, setViewing] = useState<Viewing | null>(null);
  const [openingId, setOpeningId] = useState<string | null>(null);

  const isBuyer = user?.role === 'buyer';

  // Release the blob when the viewer closes or shows another document.
  const viewingUrl = viewing?.url ?? null;
  useEffect(() => () => {
    if (viewingUrl) URL.revokeObjectURL(viewingUrl);
  }, [viewingUrl]);

  const openViewer = async (doc: BuyerDocument) => {
    setOpeningId(doc.id);
    try {
      const blob = await fetchBuyerDocumentForView(doc.id);
      if (blob.type.startsWith('text/')) {
        setViewing({ doc, kind: 'text', url: null, text: await blob.text() });
      } else {
        const kind = blob.type.startsWith('image/') ? 'image' : 'pdf';
        setViewing({ doc, kind, url: URL.createObjectURL(blob), text: null });
      }
    } catch (e) {
      showError(e);
    } finally {
      setOpeningId(null);
    }
  };

  useEffect(() => {
    if (!isBuyer) {
      navigate('/dashboard', { replace: true });
      return;
    }
    dispatch(fetchBuyerEngagement());
    dispatch(fetchBuyerFolders());
  }, [dispatch, isBuyer, navigate]);

  if (!isBuyer) return null;

  if (error) {
    return (
      <section className="card-trinity p-6">
        <div className="flex items-start gap-3">
          <Lock className="mt-0.5 h-5 w-5 flex-shrink-0 text-muted-foreground" aria-hidden />
          <div>
            <h1 className="font-heading text-lg font-semibold">Documents unavailable</h1>
            <p className="mt-1 text-sm text-muted-foreground">{error}</p>
            <p className="mt-2 text-sm text-muted-foreground">
              If you believe this is a mistake, contact the advisor who invited you.
            </p>
          </div>
        </div>
      </section>
    );
  }

  const title = engagement?.business_name || engagement?.engagement_name || 'Documents';

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-semibold text-muted-foreground">Data room</p>
        <h1 className="mt-0.5 font-heading text-2xl font-bold">
          {isLoading && !engagement ? 'Loading…' : title}
        </h1>
        {engagement?.business_name && engagement.engagement_name && (
          <p className="mt-1 text-sm text-muted-foreground">{engagement.engagement_name}</p>
        )}
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          You have read-only access to the documents released for this business. Every document is
          served through Trinity and each time you open or download one it is recorded.
        </p>
      </div>

      <section className="card-trinity p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-heading text-base font-semibold">Released folders</h2>
          <span className="text-sm text-muted-foreground">
            {folders.length} folder{folders.length === 1 ? '' : 's'}
          </span>
        </div>

        {folders.length === 0 ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            No documents have been released to you yet. They will appear here once the advisor
            releases them.
          </p>
        ) : (
          <ul className="space-y-2">
            {folders.map((folder) => {
              const key = `${folder.category_code}|${folder.sub_item_code}`;
              const expanded = open === key;
              const documents = contents[key];
              return (
                <li key={key} className="rounded-lg border border-border text-sm">
                  <button
                    type="button"
                    aria-expanded={expanded}
                    onClick={() => {
                      const next = expanded ? null : key;
                      setOpen(next);
                      if (next && documents === undefined) {
                        dispatch(
                          fetchBuyerFolderContents({
                            categoryCode: folder.category_code,
                            subItemCode: folder.sub_item_code,
                          })
                        );
                      }
                    }}
                    className="flex w-full items-center gap-3 px-3.5 py-3 text-left hover:bg-muted/40"
                  >
                    {expanded ? (
                      <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-hidden />
                    ) : (
                      <ChevronRight className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-hidden />
                    )}
                    <FolderOpen className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-hidden />
                    <span className="font-mono text-xs text-muted-foreground">
                      {folder.sub_item_code}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">
                        {folder.sub_item ?? `Folder ${folder.sub_item_code}`}
                      </span>
                      {folder.category && (
                        <span className="block truncate text-xs text-muted-foreground">
                          {folder.category_code}. {folder.category}
                        </span>
                      )}
                    </span>
                    <span className="flex-shrink-0 text-xs text-muted-foreground">
                      {documents === undefined
                        ? 'Open'
                        : documents.length === 0
                          ? 'Empty'
                          : `${documents.length} file${documents.length === 1 ? '' : 's'}`}
                    </span>
                  </button>

                  {expanded && (
                    <div className="border-t border-border px-3.5 py-2">
                      {documents === undefined ? (
                        <p className="py-2 text-xs text-muted-foreground">Loading&#8230;</p>
                      ) : documents.length === 0 ? (
                        <p className="py-2 text-xs text-muted-foreground">
                          Nothing has been added to this folder yet.
                        </p>
                      ) : (
                        <ul className="space-y-1">
                          {documents.map((doc) => (
                            <li key={doc.id} className="flex items-center gap-2 py-1 text-sm">
                              <FileIcon
                                className="h-3.5 w-3.5 flex-shrink-0 text-muted-foreground"
                                aria-hidden
                              />
                              <span className="min-w-0 flex-1 truncate">{doc.file_name}</span>
                              {doc.viewable && (
                                <button
                                  type="button"
                                  disabled={openingId === doc.id}
                                  className="flex flex-shrink-0 items-center gap-1 text-xs font-medium text-primary hover:underline disabled:opacity-50"
                                  onClick={() => openViewer(doc)}
                                >
                                  <Eye className="h-3.5 w-3.5" />
                                  {openingId === doc.id ? 'Opening…' : 'View'}
                                </button>
                              )}
                              <button
                                type="button"
                                className="flex flex-shrink-0 items-center gap-1 text-xs font-medium text-primary hover:underline"
                                onClick={() => downloadBuyerDocument(doc.id, doc.file_name).catch(showError)}
                              >
                                <Download className="h-3.5 w-3.5" />
                                Download
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        {folders.length > 0 && (
          <p className="mt-4 text-xs text-muted-foreground">
            Open a folder to see what is in it. Documents are served by Trinity, and each time you
            open or download one it is recorded.
          </p>
        )}
      </section>

      <Dialog open={viewing !== null} onOpenChange={(isOpen) => !isOpen && setViewing(null)}>
        <DialogContent className="flex h-[90vh] w-[95vw] max-w-5xl flex-col gap-3 p-4 sm:p-6">
          <DialogHeader>
            <DialogTitle className="truncate pr-8">{viewing?.doc.file_name}</DialogTitle>
            <DialogDescription>Served by Trinity. Opening a document is recorded.</DialogDescription>
          </DialogHeader>
          <div className="min-h-0 flex-1 overflow-auto rounded-md border border-border bg-muted/30">
            {viewing?.kind === 'pdf' && viewing.url && (
              <iframe title={viewing.doc.file_name} src={viewing.url} className="h-full w-full" />
            )}
            {viewing?.kind === 'image' && viewing.url && (
              <img
                src={viewing.url}
                alt={viewing.doc.file_name}
                className="mx-auto h-full max-w-full object-contain"
              />
            )}
            {viewing?.kind === 'text' && (
              <pre className="whitespace-pre-wrap break-words p-4 text-sm">{viewing.text}</pre>
            )}
          </div>
          <DialogFooter>
            {viewing && (
              <Button
                variant="outline"
                onClick={() => downloadBuyerDocument(viewing.doc.id, viewing.doc.file_name).catch(showError)}
              >
                <Download className="mr-2 h-4 w-4" />
                Download
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
