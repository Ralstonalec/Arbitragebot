import type { NextConfig } from 'next';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const monorepoRoot = path.join(__dirname, '../..');
const sharedSrc = path.join(monorepoRoot, 'packages/shared/src/index.ts');

const nextConfig: NextConfig = {
  transpilePackages: ['@arb/shared'],
  outputFileTracingRoot: monorepoRoot,
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      '@arb/shared': sharedSrc,
    };
    return config;
  },
};

export default nextConfig;
