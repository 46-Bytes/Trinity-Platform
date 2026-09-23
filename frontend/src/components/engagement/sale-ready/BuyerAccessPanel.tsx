import { useEffect, useMemo, useState } from 'react';
import { Eye, EyeOff, Plus, RotateCcw, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { useAppDispatch, useAppSelector } from '@/store/hooks';
import {
  type EngagementBuyer,
  fetchEngagementBuyers,
  fetchReleasedFolders,
  inviteBuyer,
  restoreBuyer,
  revokeBuyer,
  setReleasedFolders,
  updateBuyerNda,
} from '@/store/slices/buyerAdminReducer';
import type { DDItem } from './types';

interface BuyerAccessPanelProps {
  engagementId: string;
  /** The engagement's DD items, which name the folders that can be released. */
  ddItems: DDItem[];
  readOnly?: boolean;
}

const folderKey = (category: string, sub: string) => `${category}|${sub}`;

/**
 * The advisor's controls over buyer access.
 *
 * Buyers are invited per engagement, see only the folders released here, and
 * are revoked by ending their access rather than deleting the account. Nothing
 * on this panel touches document storage: releasing a folder says a buyer may
 * see it, not that anything is in it yet.
 */
export function BuyerAccessPanel({ engagementId, ddItems, readOnly = false }: BuyerAccessPanelProps) {
  const dispatch = useAppDispatch();
  const { buyers, releasedFolders, isSaving, error } = useAppSelector((s) => s.buyerAdmin);
  const [email, setEmail] = useState('');
  const [confirmRevoke, setConfirmRevoke] = useState<EngagementBuyer | null>(null);

  useEffect(() => {
    dispatch(fetchEngagementBuyers(engagementId));
    dispatch(fetchReleasedFolders(engagementId));
  }, [dispatch, engagementId]);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  /** Every folder that exists on this engagement, from its DD checklist. */
  const folders = useMemo(() => {
    const map = new Map<string, { category_code: string; sub_item_code: string; label: string }>();
    for (const item of ddItems) {
      const key = folderKey(item.category_code, item.sub_item_code);
      if (!map.has(key)) {
        map.set(key, {
          category_code: item.category_code,
          sub_item_code: item.sub_item_code,
          label: `${item.sub_item_code} ${item.sub_item ?? ''}`.trim(),
        });
      }
    }
    return [...map.values()];
  }, [ddItems]);

  const released = useMemo(
    () => new Set(releasedFolders.map((f) => folderKey(f.category_code, f.sub_item_code))),
    [releasedFolders]
  );

  const fail = (e: unknown) => toast.error(String(e));

  const invite = () => {
    if (!email.trim()) return;
    dispatch(inviteBuyer({ engagementId, email: email.trim() }))
      .unwrap()
      .then(() => {
        setEmail('');
        toast.success('Invitation sent. The buyer sets their password by email.');
      })
      .catch(fail);
  };

  const toggleFolder = (category: string, sub: string, on: boolean) => {
    const key = folderKey(category, sub);
    const next = on
      ? [...releasedFolders, { category_code: category, sub_item_code: sub }]
      : releasedFolders.filter((f) => folderKey(f.category_code, f.sub_item_code) !== key);
    dispatch(setReleasedFolders({ engagementId, folders: next })).unwrap().catch(fail);
  };

  return (
    <div className="space-y-5">
      <section className="card-trinity p-4 sm:p-6">
        <h2 className="font-heading text-base font-semibold">Buyer access</h2>
        <p className="mb-4 mt-1 max-w-3xl text-xs text-muted-foreground">
          Buyers sign in to Trinity and see only the folders released below, read-only. Every open and
          download is recorded. Revoking ends their access without deleting the account, so it can be
          restored later. The NDA is handled outside Trinity; the date here is a record only and does
          not control access.
        </p>

        {buyers.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No buyers have been invited to this engagement.
          </p>
        ) : (
          <div className="space-y-2">
            {buyers.map((buyer) => {
              const revoked = buyer.status !== 'active';
              return (
                <div
                  key={buyer.id}
                  className={cn(
                    'flex flex-col gap-2 rounded-lg border border-border p-3 sm:flex-row sm:items-center sm:gap-3',
                    revoked && 'opacity-60'
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{buyer.name || buyer.email}</p>
                    {buyer.name && buyer.email && (
                      <p className="truncate text-xs text-muted-foreground">{buyer.email}</p>
                    )}
                  </div>
                  <span
                    className={cn(
                      'w-fit flex-shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold',
                      revoked ? 'bg-destructive/10 text-destructive' : 'bg-success/10 text-success'
                    )}
                  >
                    {revoked ? 'Revoked' : 'Active'}
                  </span>
                  <div className="flex-shrink-0 sm:w-44">
                    <Label className="sr-only" htmlFor={`nda-${buyer.id}`}>
                      NDA signed
                    </Label>
                    <Input
                      id={`nda-${buyer.id}`}
                      type="date"
                      aria-label="NDA signed date"
                      className="h-8 text-xs"
                      disabled={readOnly || isSaving}
                      defaultValue={buyer.nda_signed_date ?? ''}
                      onBlur={(e) => {
                        if (e.target.value !== (buyer.nda_signed_date ?? '')) {
                          dispatch(updateBuyerNda({
                            engagementId, id: buyer.id, nda_signed_date: e.target.value || null,
                          })).unwrap().catch(fail);
                        }
                      }}
                    />
                  </div>
                  {revoked ? (
                    <Button
                      variant="outline" size="sm" className="flex-shrink-0"
                      disabled={readOnly || isSaving}
                      onClick={() =>
                        dispatch(restoreBuyer({ engagementId, id: buyer.id }))
                          .unwrap()
                          .then(() => toast.success('Access restored'))
                          .catch(fail)
                      }
                    >
                      <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                      Restore
                    </Button>
                  ) : (
                    <Button
                      variant="outline" size="sm" className="flex-shrink-0"
                      disabled={readOnly || isSaving}
                      onClick={() => setConfirmRevoke(buyer)}
                    >
                      <Trash2 className="mr-1.5 h-3.5 w-3.5 text-destructive" />
                      Revoke
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {!readOnly && (
          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <Input
              type="email"
              value={email}
              disabled={isSaving}
              placeholder="Invite a buyer by email"
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && invite()}
              className="text-sm"
            />
            <Button onClick={invite} disabled={isSaving || !email.trim()} className="flex-shrink-0">
              <Plus className="mr-1.5 h-4 w-4" />
              Invite
            </Button>
          </div>
        )}
      </section>

      <section className="card-trinity p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="font-heading text-base font-semibold">Visible to buyers</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              One folder per due diligence sub-item. Nothing is visible until you release it here.
            </p>
          </div>
          <span className="text-sm text-muted-foreground">{released.size} released</span>
        </div>

        {folders.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            This engagement has no due diligence items yet.
          </p>
        ) : (
          <div className="max-h-[420px] space-y-1 overflow-y-auto pr-1">
            {folders.map((folder) => {
              const key = folderKey(folder.category_code, folder.sub_item_code);
              const on = released.has(key);
              return (
                <label
                  key={key}
                  className="flex cursor-pointer items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm"
                >
                  <Checkbox
                    checked={on}
                    disabled={readOnly || isSaving}
                    onCheckedChange={(v) =>
                      toggleFolder(folder.category_code, folder.sub_item_code, v === true)
                    }
                  />
                  <span className="flex-1 truncate">{folder.label}</span>
                  {on ? (
                    <Eye className="h-4 w-4 flex-shrink-0 text-success" aria-label="Released" />
                  ) : (
                    <EyeOff className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-label="Not released" />
                  )}
                </label>
              );
            })}
          </div>
        )}

        <p className="mt-4 text-xs text-muted-foreground">
          Releasing a folder says a buyer may see it. Documents appear once the data room is connected.
        </p>
      </section>

      <AlertDialog open={confirmRevoke !== null} onOpenChange={(open) => !open && setConfirmRevoke(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Revoke this buyer's access?</AlertDialogTitle>
            <AlertDialogDescription>
              {confirmRevoke?.email}
              <span className="mt-2 block">
                They lose access immediately. The account is not deleted and the record of what they
                opened is kept, so access can be restored later.
              </span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (!confirmRevoke) return;
                dispatch(revokeBuyer({ engagementId, id: confirmRevoke.id }))
                  .unwrap()
                  .then(() => toast.success('Access revoked'))
                  .catch(fail);
                setConfirmRevoke(null);
              }}
            >
              Revoke
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
