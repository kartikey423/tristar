/** @type {import('next').NextConfig} */
const nextConfig = {
  serverRuntimeConfig: {
    MARKETER_JWT: process.env.MARKETER_JWT,
    API_URL: process.env.API_URL || 'http://localhost:8000',
  },
  publicRuntimeConfig: {
    API_URL: process.env.API_URL || 'http://localhost:8000',
  },
};
module.exports = nextConfig;
