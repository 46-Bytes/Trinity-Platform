import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

// Decodes a JWT payload and returns true if the token is expired or unparseable.
// Uses native atob() — no external library needed.
function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return true;
    // base64url → base64: restore URL-safe chars and missing padding
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64.padEnd(
      base64.length + (4 - (base64.length % 4)) % 4,
      '='
    );
    const payload = JSON.parse(atob(padded));
    if (typeof payload.exp !== 'number') return true;
    return payload.exp < Math.floor(Date.now() / 1000);
  } catch {
    return true;
  }
}

// Layer 1 — Pre-request check: if the stored token is already expired, skip the
// network call entirely and return a synthetic 401 so callers behave consistently.
// The existing reactive 401 handler below remains as a backstop for server-side
// revocations that the client cannot detect from the exp claim alone.
const _originalFetch = window.fetch.bind(window);
window.fetch = async (...args: Parameters<typeof fetch>): Promise<Response> => {
  const token = localStorage.getItem('auth_token');
  if (token && isTokenExpired(token)) {
    localStorage.removeItem('auth_token');
    window.dispatchEvent(new CustomEvent('auth:token-expired'));
    return new Response(JSON.stringify({ detail: 'Token expired' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' },
    });
  }

  // Existing reactive layer: catches server-side 401s (revoked tokens, etc.)
  const response = await _originalFetch(...args);
  if (response.status === 401 && localStorage.getItem('auth_token')) {
    localStorage.removeItem('auth_token');
    window.dispatchEvent(new CustomEvent('auth:token-expired'));
  }
  return response;
};

// Layer 2 — Global click listener: catches UI-only interactions (modal openers,
// toggles, etc.) that don't trigger a fetch call and would bypass Layer 1.
// capture:true fires this before React's synthetic event system processes the click.
document.addEventListener('click', () => {
  const token = localStorage.getItem('auth_token');
  if (token && isTokenExpired(token)) {
    localStorage.removeItem('auth_token');
    window.dispatchEvent(new CustomEvent('auth:token-expired'));
  }
}, { capture: true });

createRoot(document.getElementById("root")!).render(<App />);
