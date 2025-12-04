import { useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { ArrowRight, Sparkles } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

export default function Login() {
  const { login } = useAuth();
  const [searchParams] = useSearchParams();
  const error = searchParams.get('error');

  const handleSignIn = () => {
    // Clear any existing tokens/session data before redirecting to Auth0
    // This ensures a fresh login with no previous user data
    localStorage.removeItem('auth_token');
    
    // ALWAYS redirect to Auth0 Universal Login
    // This ensures we get fresh credentials and proper email verification
    window.location.href = '/api/auth/login';
  };

  useEffect(() => {
    // Clear any existing authentication data when landing on login page
    // This ensures a fresh start with no previous user data
    localStorage.removeItem('auth_token');
    
    // Show error message if authentication failed
    if (error === 'authentication_failed') {
      console.error('Authentication failed. Please try again.');
    }
  }, [error]);

  return (
    <div className="min-h-screen flex">
      {/* Left Panel - Hero */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden" style={{ background: 'var(--gradient-hero)' }}>
        <div className="absolute inset-0 opacity-20">
          <div className="absolute top-20 left-20 w-72 h-72 bg-accent/20 rounded-full blur-3xl" />
          <div className="absolute bottom-40 right-10 w-96 h-96 bg-accent/10 rounded-full blur-3xl" />
        </div>
        
        <div className="relative z-10 flex flex-col justify-center px-16 text-primary-foreground">
          <div className="flex items-center gap-3 mb-8">
            <div className="w-12 h-12 rounded-xl bg-accent flex items-center justify-center">
              <span className="font-heading font-bold text-xl text-accent-foreground">T</span>
            </div>
            <span className="font-heading font-bold text-2xl">Trinity</span>
          </div>
          
          <h1 className="font-heading text-5xl font-bold mb-6 leading-tight animate-slide-up">
            Transform Your<br />
            <span className="text-accent">Business Advisory</span>
          </h1>
          
          <p className="text-lg text-primary-foreground/80 mb-8 max-w-md animate-slide-up stagger-1">
            A secure, cloud-based engagement platform that enables advisors to manage clients, 
            produce diagnostics, and generate AI-assisted business artefacts.
          </p>

          <div className="space-y-4 animate-slide-up stagger-2">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-accent" />
              </div>
              <span className="text-primary-foreground/90">AI-Powered Business Tools</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-accent" />
              </div>
              <span className="text-primary-foreground/90">Secure Client Engagement</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-accent" />
              </div>
              <span className="text-primary-foreground/90">Comprehensive Task Management</span>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <div className="w-full max-w-md animate-scale-in">
          {/* Mobile Logo */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center">
              <span className="font-heading font-bold text-lg text-primary-foreground">T</span>
            </div>
            <span className="font-heading font-bold text-xl">Trinity</span>
          </div>

          <div className="mb-8">
            <h2 className="font-heading text-3xl font-bold text-foreground mb-2">Welcome back</h2>
            <p className="text-muted-foreground">Sign in to your account to continue</p>
          </div>

          {error && (
            <div className="mb-6 p-4 bg-destructive/10 border border-destructive/20 rounded-lg">
              <p className="text-sm text-destructive">
                Authentication failed. Please try again.
              </p>
            </div>
          )}

          <div className="space-y-4">
            <Button 
              onClick={handleSignIn}
              className="w-full btn-primary h-11"
              size="lg"
            >
              <span className="flex items-center gap-2">
                Sign in
                <ArrowRight className="w-4 h-4" />
              </span>
            </Button>

            <p className="text-center text-sm text-muted-foreground">
              You'll be redirected to Auth0 to sign in securely
            </p>
          </div>

          <p className="mt-8 text-center text-sm text-muted-foreground">
            Don't have an account?{' '}
            <a href="#" className="text-accent font-medium hover:underline">Contact your administrator</a>
          </p>
        </div>
      </div>
    </div>
  );
}
