import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

// Global fetch interceptor: on 401, clear the stored token and signal that the
// session has expired. AuthContext listens for this event and sets the user as
// unauthenticated, which causes ProtectedRoute to redirect to /login.
const _originalFetch = window.fetch.bind(window);
window.fetch = async (...args: Parameters<typeof fetch>): Promise<Response> => {
  const response = await _originalFetch(...args);
  if (response.status === 401 && localStorage.getItem('auth_token')) {
    localStorage.removeItem('auth_token');
    window.dispatchEvent(new CustomEvent('auth:token-expired'));
  }
  return response;
};

createRoot(document.getElementById("root")!).render(<App />);
