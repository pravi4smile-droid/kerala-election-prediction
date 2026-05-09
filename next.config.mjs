import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = dirname(fileURLToPath(import.meta.url));
const localBackend = process.env.BACKEND_ORIGIN ||
  (process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:5000' : '');

/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    root: repoRoot,
  },
  async rewrites() {
    if (!localBackend) return [];
    return [
      {
        source: '/api/:path*',
        destination: `${localBackend}/api/:path*`,
      },
      {
        source: '/static/:path*',
        destination: `${localBackend}/static/:path*`,
      },
    ];
  },
};

export default nextConfig;
