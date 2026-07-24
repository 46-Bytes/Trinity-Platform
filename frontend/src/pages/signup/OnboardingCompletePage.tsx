import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight, CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getAccount, type Account } from '@/lib/selfServiceApi';

/** How long to keep polling before telling the owner to check back later. */
const POLL_TIMEOUT_MS = 60_000;
const POLL_INTERVAL_MS = 2_000;

/**
 * Post-payment screen.
 *
 * Provisioning (engagement + M0 diagnostic) may complete inline (manual
 * billing) or asynchronously via a webhook (Stripe), so this polls
 * /api/self-service/account until the workspace exists, then deep-links the
 * owner into their diagnostic.
 */
export default function OnboardingCompletePage() {
  const navigate = useNavigate();
  const [account, setAccount] = useState<Account | null>(null);
  const [timedOut, setTimedOut] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startedAt = useRef(Date.now());

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      try {
        const data = await getAccount();
        if (cancelled) return;

        setAccount(data);

        if (data.engagement_id) return; // done - the redirect effect takes over

        if (Date.now() - startedAt.current > POLL_TIMEOUT_MS) {
          setTimedOut(true);
          return;
        }
        timer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Could not check your account status.');
      }
    };

    poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  // Send the owner straight to their diagnostic once provisioning lands.
  useEffect(() => {
    if (!account?.engagement_id) return;
    const timer = setTimeout(() => {
      navigate(`/dashboard/engagements/${account.engagement_id}`, { replace: true });
    }, 1200);
    return () => clearTimeout(timer);
  }, [account?.engagement_id, navigate]);

  const ready = !!account?.engagement_id;

  return (
    <div className="min-h-screen flex items-center justify-center p-8 bg-background">
      <div className="w-full max-w-md text-center animate-scale-in">
        <img src="/logo.png" alt="Trinity Logo" className="w-24 h-24 object-contain mx-auto mb-6" />

        {error ? (
          <>
            <AlertCircle className="w-12 h-12 text-destructive mx-auto mb-4" />
            <h1 className="font-heading text-2xl font-bold mb-2">Something went wrong</h1>
            <p className="text-muted-foreground mb-6">{error}</p>
            <Button onClick={() => navigate('/dashboard')} variant="outline">
              Go to dashboard
            </Button>
          </>
        ) : ready ? (
          <>
            <CheckCircle2 className="w-12 h-12 text-accent mx-auto mb-4" />
            <h1 className="font-heading text-2xl font-bold mb-2">You're all set</h1>
            <p className="text-muted-foreground mb-6">
              Your {account?.program_label ?? 'program'} workspace is ready. Taking you to your
              diagnostic...
            </p>
            <Button
              onClick={() => navigate(`/dashboard/engagements/${account?.engagement_id}`)}
              className="btn-primary"
            >
              <span className="flex items-center gap-2">
                Start my diagnostic
                <ArrowRight className="w-4 h-4" />
              </span>
            </Button>
          </>
        ) : timedOut ? (
          <>
            <AlertCircle className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h1 className="font-heading text-2xl font-bold mb-2">Still setting up</h1>
            <p className="text-muted-foreground mb-6">
              Your payment went through and we're finishing your workspace. This can take a moment -
              your dashboard will show it as soon as it's ready.
            </p>
            <Button onClick={() => navigate('/dashboard')} className="btn-primary">
              Go to dashboard
            </Button>
          </>
        ) : (
          <>
            <Loader2 className="w-12 h-12 text-accent mx-auto mb-4 animate-spin" />
            <h1 className="font-heading text-2xl font-bold mb-2">Setting up your workspace</h1>
            <p className="text-muted-foreground">
              We're preparing your program and diagnostic. This only takes a few seconds.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
