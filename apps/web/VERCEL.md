# Vercel deployment (apps/web)

## Project settings

| Setting | Value |
|---------|--------|
| Root Directory | `apps/web` |
| Framework Preset | **Other** or **Next.js** (build uses static export) |
| Output Directory | `public` (set in `vercel.json`) |
| Build Command | empty (uses `npm run build`) |
| Install Command | empty (uses `npm install`) |

The build exports Next.js to `out/`, then copies to `public/` for Vercel.

## Environment

- `NEXT_PUBLIC_API_URL` — your API base URL (required for live data)
