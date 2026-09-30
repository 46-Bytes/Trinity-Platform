import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Link2, RefreshCw, Unlink } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
const BASE = `${API_BASE_URL}/api/drive`;

interface DriveStatus {
  enabled: boolean;
  connected: boolean;
  account_email: string | null;
  root_folder_id: string | null;
  root_folder_configured: boolean;
  last_synced_at: string | null;
  last_error: string | null;
  configuration_missing: string[];
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('auth_token');
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
    credentials: 'include',
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || 'The Drive connection could not be reached');
  }
  return (await response.json()) as T;
}

/**
 * Connecting Trinity to Benchmark's Google Drive.
 *
 * A one-time setup step, done once by an admin and then left alone. The token
 * itself is never shown here or returned by the API - this reports whether the
 * connection works, which account authorised it, and what is still missing.
 *
 * Nobody but Trinity uses these credentials: advisors, clients and buyers have
 * no Drive access at all, and every document reaches them through Trinity.
 */
export function DriveConnectionCard() {
  const [status, setStatus] = useState<DriveStatus | null>(null);
  const [rootFolder, setRootFolder] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const next = await call<DriveStatus>('/status');
      setStatus(next);
      setRootFolder(next.root_folder_id ?? '');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (fn: () => Promise<DriveStatus>, success: string) => {
    setBusy(true);
    try {
      const next = await fn();
      setStatus(next);
      setRootFolder(next.root_folder_id ?? '');
      toast.success(success);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const connect = async () => {
    setBusy(true);
    try {
      const { authorization_url } = await call<{ authorization_url: string }>('/connect');
      window.location.href = authorization_url;
    } catch (e) {
      toast.error(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  if (!status) return null;

  const blocked = status.configuration_missing.length > 0;

  return (
    <section className="card-trinity p-4 sm:p-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-heading text-base font-semibold">Google Drive data room</h2>
          <p className="mt-1 max-w-3xl text-xs text-muted-foreground">
            Sale Ready documents live in Benchmark&apos;s Drive; Trinity indexes them and serves
            them. The account is used by Trinity alone — advisors, clients and buyers never get
            Drive access, and no Drive link is ever shown to them.
          </p>
        </div>
        <div className="flex flex-shrink-0 gap-2">
          <Button variant="outline" size="sm" disabled={busy} onClick={() => run(() => call<DriveStatus>('/check', { method: 'POST' }), 'Connection checked')}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Check
          </Button>
          {status.connected ? (
            <Button variant="outline" size="sm" disabled={busy} onClick={() => run(() => call<DriveStatus>('/disconnect', { method: 'POST' }), 'Disconnected')}>
              <Unlink className="mr-1.5 h-3.5 w-3.5" />
              Disconnect
            </Button>
          ) : (
            <Button size="sm" disabled={busy || blocked} onClick={connect}>
              <Link2 className="mr-1.5 h-3.5 w-3.5" />
              Connect
            </Button>
          )}
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 text-sm">
        {status.connected ? (
          <>
            <CheckCircle2 className="h-4 w-4 flex-shrink-0 text-success" aria-hidden />
            <span>
              Connected{status.account_email ? ` as ${status.account_email}` : ''}.
              {status.last_synced_at
                ? ` Last synced ${new Date(status.last_synced_at).toLocaleString('en-AU')}.`
                : ' Not synced yet.'}
            </span>
          </>
        ) : (
          <>
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-muted-foreground" aria-hidden />
            <span className="text-muted-foreground">
              Not connected. Uploads and buyer downloads are unavailable until an admin connects the
              account.
            </span>
          </>
        )}
      </div>

      {blocked && (
        <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
          Server configuration is incomplete: {status.configuration_missing.join(', ')}. These are
          environment settings, not something that can be fixed from this screen.
        </p>
      )}

      {status.last_error && (
        <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
          Last error: {status.last_error}
        </p>
      )}

      <div className="mt-4 max-w-xl">
        <Label className="mb-1.5 block text-sm font-semibold" htmlFor="drive-root">
          Root folder id
        </Label>
        <p className="mb-2 text-xs text-muted-foreground">
          The Drive id of <code>Trinity / Clients</code>. Every client folder is created beneath it.
        </p>
        <div className="flex gap-2">
          <Input
            id="drive-root"
            value={rootFolder}
            placeholder="1AbC…"
            className="text-sm"
            onChange={(e) => setRootFolder(e.target.value)}
          />
          <Button
            variant="outline"
            size="sm"
            className="flex-shrink-0"
            disabled={busy || !rootFolder.trim() || rootFolder.trim() === (status.root_folder_id ?? '')}
            onClick={() =>
              run(
                () => call<DriveStatus>('/root-folder', {
                  method: 'PUT',
                  body: JSON.stringify({ root_folder_id: rootFolder.trim() }),
                }),
                'Root folder saved'
              )
            }
          >
            Save
          </Button>
        </div>
      </div>
    </section>
  );
}
