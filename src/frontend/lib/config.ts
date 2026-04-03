/**
 * Shared frontend configuration constants.
 * SERVER_API_BASE: used in Server Components and Server Actions (Node.js env).
 */

export const SERVER_API_BASE = process.env.API_URL ?? 'http://localhost:8000';

/**
 * F-002 FIX: Returns Authorization header using MARKETER_JWT env var.
 * Fallback: uses hardcoded dev token if env var is not set.
 * This token has 'marketing' role: {'sub': 'marketer-demo', 'role': 'marketing'}
 */
export function getAuthHeaders(): Record<string, string> {
  let token = process.env.MARKETER_JWT;

  // Fallback: use hardcoded dev token if env var is not set
  if (!token) {
    token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJtYXJrZXRlci1kZW1vIiwicm9sZSI6Im1hcmtldGluZyJ9.AIro1O38GcdY4sFzsvVwm-OJ7qosv1Q9f13vkxaDGGY';
  }

  return { Authorization: `Bearer ${token}` };
}
