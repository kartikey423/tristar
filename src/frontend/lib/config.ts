/**
 * Shared frontend configuration constants.
 * SERVER_API_BASE: used in Server Components and Server Actions (Node.js env).
 */

export const SERVER_API_BASE = process.env.API_URL ?? 'http://localhost:8000';
