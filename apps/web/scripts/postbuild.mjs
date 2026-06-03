import { cpSync, existsSync, mkdirSync, rmSync } from 'fs';

/** Copy Next static export (out/) to public/ for Vercel Output Directory = public */
if (!existsSync('out')) {
  console.error('postbuild: out/ not found — run next build first');
  process.exit(1);
}

rmSync('public', { recursive: true, force: true });
cpSync('out', 'public', { recursive: true });

// Ensure robots.txt exists
mkdirSync('public', { recursive: true });
cpSync('static-assets/robots.txt', 'public/robots.txt');

console.log('postbuild: copied out/ → public/');
