# Vercel deployment (apps/web)

## Required project settings

In **Vercel → Project → Settings → Build & Development Settings**:

| Setting | Value |
|---------|--------|
| Root Directory | `apps/web` |
| Framework Preset | **Next.js** (not "Other") |
| Output Directory | **leave completely empty** |
| Build Command | empty (uses `vercel.json`) |
| Install Command | empty (uses `vercel.json`) |

If **Output Directory** is set to `public`, the deploy will fail or serve only static files.
Next.js output lives in `.next` and is handled automatically by the Next.js preset.

After changing settings, redeploy from the latest `main` branch.

## Environment

- `NEXT_PUBLIC_API_URL` — URL of the deployed API (when available)
