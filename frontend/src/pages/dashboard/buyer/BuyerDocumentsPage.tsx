import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderOpen, Lock } from 'lucide-react';

import { useAuth } from '@/context/AuthContext';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import { fetchBuyerEngagement, fetchBuyerFolders } from '@/store/slices/buyerReducer';

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
  const { engagement, folders, isLoading, error } = useAppSelector((s) => s.buyer);

  const isBuyer = user?.role === 'buyer';

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
            {folders.map((folder) => (
              <li
                key={`${folder.category_code}.${folder.sub_item_code}`}
                className={cn(
                  'flex items-center gap-3 rounded-lg border border-border px-3.5 py-3',
                  'text-sm'
                )}
              >
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
                <span className="flex-shrink-0 text-xs text-muted-foreground">Empty</span>
              </li>
            ))}
          </ul>
        )}

        {folders.length > 0 && (
          <p className="mt-4 text-xs text-muted-foreground">
            Folders are released but the document store is not connected yet, so they are currently
            empty.
          </p>
        )}
      </section>
    </div>
  );
}
