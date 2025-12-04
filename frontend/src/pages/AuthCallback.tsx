import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

export default function AuthCallback() {
  const navigate = useNavigate();

  useEffect(() => {
    // Get token from URL
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');

    if (token) {
      // Store token in localStorage
      localStorage.setItem('auth_token', token);
      console.log('✅ Token stored in localStorage');
      
      // Redirect to dashboard
      navigate('/dashboard', { replace: true });
    } else {
      // No token, redirect to login
      console.error('❌ No token in callback URL');
      navigate('/login', { replace: true });
    }
  }, [navigate]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
        <p className="mt-4 text-gray-600">Completing authentication...</p>
      </div>
    </div>
  );
}

