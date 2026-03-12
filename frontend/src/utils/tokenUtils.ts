/**
 * JWT token utilities for client-side expiration checking.
 * Decodes the payload without signature verification (only for reading exp claim).
 */

export function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = payload.exp;
    if (!exp) return true;
    // Expired if current time >= exp (with 30s buffer for clock skew)
    return Date.now() >= exp * 1000 - 30000;
  } catch {
    return true;
  }
}

export function getTokenExpiryMs(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}
