/** @type {import('next').NextConfig} */
const nextConfig = {
  // Server-side runtime configuration - available in server actions and API routes
  serverRuntimeConfig: {
    MARKETER_JWT: process.env.MARKETER_JWT,
    API_URL: process.env.API_URL || 'http://localhost:8000',
  },
  // Public runtime configuration - available on both client and server
  publicRuntimeConfig: {
    API_URL: process.env.API_URL || 'http://localhost:8000',
  },
};

module.exports = nextConfig;
