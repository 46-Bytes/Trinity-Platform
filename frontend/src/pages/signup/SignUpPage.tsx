import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, Check, Loader2, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  createSignupIntent,
  getPrograms,
  toBackendUrl,
  type Plan,
  type Program,
} from '@/lib/selfServiceApi';

/**
 * Business owner self-service signup (Feature 7).
 *
 * Collects the owner's details and program choice, parks them as a signup
 * intent, then hands off to Auth0 for the credential step. The intent is what
 * tells the backend to create this account as a self-service business owner
 * rather than falling through to a default role.
 */
export default function SignUpPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [plans, setPlans] = useState<Plan[]>([]);
  const [signupEnabled, setSignupEnabled] = useState(true);
  const [loadingPlans, setLoadingPlans] = useState(true);

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [businessName, setBusinessName] = useState('');
  const [program, setProgram] = useState<Program | null>(
    (searchParams.get('program') as Program) || null,
  );

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPrograms()
      .then((data) => {
        setPlans(data.plans);
        setSignupEnabled(data.signup_enabled);
        if (!program && data.plans.length > 0) {
          setProgram(data.plans[0].program);
        }
      })
      .catch(() => setError('Could not load our programs. Please try again shortly.'))
      .finally(() => setLoadingPlans(false));
    // Only on mount - `program` is seeded from the query string above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!program) {
      setError('Please choose a program to continue.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const result = await createSignupIntent({
        email: email.trim(),
        program,
        name: name.trim() || undefined,
        business_name: businessName.trim() || undefined,
      });

      if (result.already_registered) {
        // The API never confirms whether an address is registered; it just
        // routes existing accounts to sign-in instead.
        navigate('/login?existing=1');
        return;
      }

      window.location.href = toBackendUrl(result.redirect_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
      setSubmitting(false);
    }
  };

  if (!loadingPlans && !signupEnabled) {
    return (
      <div className="min-h-screen flex items-center justify-center p-8 bg-background">
        <div className="max-w-md text-center">
          <h1 className="font-heading text-2xl font-bold mb-2">Sign-up is not open yet</h1>
          <p className="text-muted-foreground mb-6">
            Trinity self-service accounts are not available at the moment. Please check back soon.
          </p>
          <Button onClick={() => navigate('/login')} variant="outline">Back to sign in</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Hero */}
      <div
        className="hidden lg:flex lg:w-1/2 items-center justify-center relative overflow-hidden"
        style={{ background: 'var(--gradient-hero)' }}
      >
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-20 left-20 w-72 h-72 bg-accent/20 rounded-full blur-3xl" />
          <div className="absolute bottom-40 right-10 w-96 h-96 bg-accent/10 rounded-full blur-3xl" />
        </div>

        <div className="relative z-10 flex flex-col justify-center px-16 text-primary-foreground">
          <img src="/logo.png" alt="Trinity Logo" className="w-80 object-contain mb-4" />

          <h1 className="font-heading text-5xl font-bold mb-6 leading-tight animate-slide-up">
            Build the value of<br />
            <span className="text-accent">your business</span>
          </h1>

          <p className="text-lg text-primary-foreground/80 mb-8 max-w-md animate-slide-up stagger-1">
            Complete your diagnostic, get an AI-generated report with a recommended path,
            and work the modules at your own pace.
          </p>

          <div className="space-y-4 animate-slide-up stagger-2">
            {[
              'AI-powered diagnostic and report',
              'A recommended starting module and path',
              'Tasks, documents and your value dashboard',
              'Invite your team to collaborate',
            ].map((feature) => (
              <div key={feature} className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
                  <Sparkles className="w-4 h-4 text-accent" />
                </div>
                <span className="text-primary-foreground/90">{feature}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Right Panel - Signup Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-background overflow-y-auto">
        <div className="w-full max-w-md animate-scale-in py-8">
          <div className="flex items-center gap-4 mb-8 lg:hidden justify-center">
            <img src="/logo.png" alt="Trinity Logo" className="w-24 h-24 object-contain" />
          </div>

          <div className="mb-8">
            <h2 className="font-heading text-3xl font-bold text-foreground mb-2">
              Create your account
            </h2>
            <p className="text-muted-foreground">
              Start with a diagnostic and see where your business stands.
            </p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="name">Your name</Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Jane Smith"
                autoComplete="name"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">Work email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="jane@yourbusiness.com.au"
                autoComplete="email"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="businessName">Business name</Label>
              <Input
                id="businessName"
                value={businessName}
                onChange={(e) => setBusinessName(e.target.value)}
                placeholder="Your Business Pty Ltd"
                autoComplete="organization"
                required
              />
            </div>

            <div className="space-y-3">
              <Label>Choose your program</Label>
              {loadingPlans ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Loading programs...
                </div>
              ) : (
                <div className="grid gap-3">
                  {plans.map((plan) => {
                    const selected = program === plan.program;
                    return (
                      <button
                        key={plan.program}
                        type="button"
                        onClick={() => setProgram(plan.program)}
                        aria-pressed={selected}
                        className={`text-left rounded-lg border p-4 transition-colors ${
                          selected
                            ? 'border-accent bg-accent/5 ring-1 ring-accent'
                            : 'border-border hover:border-accent/50'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium text-foreground">{plan.label}</p>
                            <p className="text-sm text-muted-foreground mt-1">{plan.description}</p>
                          </div>
                          {selected && <Check className="w-5 h-5 text-accent shrink-0 mt-0.5" />}
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <Button
              type="submit"
              className="w-full btn-primary h-11"
              size="lg"
              disabled={submitting || loadingPlans || !program}
            >
              {submitting ? (
                <span className="flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Setting things up...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  Continue
                  <ArrowRight className="w-4 h-4" />
                </span>
              )}
            </Button>

            <p className="text-center text-xs text-muted-foreground">
              You'll set your password on the next screen.
            </p>
          </form>

          <p className="mt-8 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <a href="/login" className="text-accent font-medium hover:underline">Sign in</a>
          </p>
        </div>
      </div>
    </div>
  );
}
