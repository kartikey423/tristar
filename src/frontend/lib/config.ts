/**
 * Shared frontend configuration constants.
 * SERVER_API_BASE: used in Server Components and Server Actions (Node.js env).
 */

export const SERVER_API_BASE = process.env.API_URL ?? 'http://localhost:8000';

/**
 * F-002 FIX: Returns Authorization header using MARKETER_JWT env var.
 * Returns empty object when MARKETER_JWT is not set (no crash — graceful degradation).
 */
export function getAuthHeaders(): Record<string, string> {
  const token = process.env.MARKETER_JWT;
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}
