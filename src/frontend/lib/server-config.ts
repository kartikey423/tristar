/**
 * Server-side configuration for TriStar
 * This module safely exposes environment variables to server components and actions
 */

import getConfig from 'next/config';

// Get server runtime configuration
const { serverRuntimeConfig = {} } = getConfig() || {};

export const serverConfig = {
  // TriStar API configuration
  API_BASE_URL: serverRuntimeConfig.API_URL || process.env.API_URL || 'http://localhost:8000',

  // JWT Token for authentication - read from runtime config
  MARKETER_JWT: serverRuntimeConfig.MARKETER_JWT || process.env.MARKETER_JWT || '',

  // Environment
  ENVIRONMENT: process.env.ENVIRONMENT || 'development',

  // Check if token is properly configured
  isAuthConfigured: () => {
    const token = serverRuntimeConfig.MARKETER_JWT || process.env.MARKETER_JWT;
    if (!token) {
      console.warn('⚠️ MARKETER_JWT is not configured in environment variables');
      return false;
    }
    return true;
  },

  // Get auth headers for API calls
  getAuthHeaders: () => {
    let token = serverRuntimeConfig.MARKETER_JWT || process.env.MARKETER_JWT;

    // Fallback: use hardcoded dev token if env var is not set
    if (!token) {
      token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJtYXJrZXRlci1kZW1vIiwicm9sZSI6Im1hcmtldGluZyJ9.AIro1O38GcdY4sFzsvVwm-OJ7qosv1Q9f13vkxaDGGY';
    }
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    };
  },
};

