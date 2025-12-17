import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Mail, ArrowRight } from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const email = searchParams.get('email') || '';
  const [isResending, setIsResending] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(false);

  const handleResendVerification = async () => {
    if (!email) return;
    
    setIsResending(true);
    try {
      // Call backend to resend verification email
      const response = await fetch(`${API_BASE_URL}/api/auth/resend-verification?email=${encodeURIComponent(email)}`, {
        method: 'POST',
      });
      
      if (response.ok) {
        setResendSuccess(true);
        setTimeout(() => setResendSuccess(false), 5000);
      }
    } catch (error) {
      console.error('Failed to resend verification email:', error);
    } finally {
      setIsResending(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-lg shadow-lg">
        <div className="text-center">
          <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-blue-100 mb-4">
            <Mail className="h-8 w-8 text-blue-600" />
          </div>
          <h2 className="text-3xl font-bold text-gray-900">Verify Your Email</h2>
          <p className="mt-2 text-sm text-gray-600">
            We've sent a verification email to
          </p>
          <p className="mt-1 text-sm font-medium text-gray-900">{email}</p>
        </div>

        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <p className="text-sm text-blue-800">
            <strong>Please check your inbox</strong> and click the verification link to activate your account.
          </p>
          <p className="text-sm text-blue-700 mt-2">
            After verifying your email, click "Back to Login" and sign in again to access your dashboard.
          </p>
        </div>

        <div className="space-y-4">
          <Button
            onClick={handleResendVerification}
            disabled={isResending || resendSuccess}
            className="w-full"
            variant="outline"
          >
            {isResending ? (
              'Sending...'
            ) : resendSuccess ? (
              '✓ Email Sent!'
            ) : (
              <>
                Resend Verification Email
                <ArrowRight className="ml-2 h-4 w-4" />
              </>
            )}
          </Button>

          <Button
            onClick={() => navigate('/login')}
            className="w-full"
            variant="ghost"
          >
            Back to Login
          </Button>
        </div>

        <p className="text-xs text-center text-gray-500">
          Didn't receive the email? Check your spam folder or try resending.
        </p>
      </div>
    </div>
  );
}

