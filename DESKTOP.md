# MAINTAIN AI Desktop — Installable Cloud Client

The desktop application is an Electron client that connects to the hosted MAINTAIN AI backend. The installer contains the React/Vite frontend, but does not start or bundle a local FastAPI server.

## Architecture

```
Windows / macOS / Linux
          │
          ▼
   MAINTAIN AI Desktop
        Electron
          │
          │ HTTPS + WSS
          ▼
 maintain-ai-3.vercel.app
          │
          ▼
    FastAPI backend
          │
          ├── Database
          ├── ML / pretrained models
          ├── WebSocket telemetry
          ├── Reports / exports
          └── Authentication
```

The frontend uses `VITE_API_URL` at build time. GitHub Actions uses the repository variable `MAINTAIN_AI_API_URL` when present and otherwise uses:

```
https://maintain-ai-3.vercel.app
```

## Local development

Run the web frontend and backend normally, then run Electron:

```bash
cd backend
python3 -m uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Then:

```bash
cd desktop
npm install
npm run dev
```

## Build an installer locally

Build the frontend against the hosted backend:

```bash
cd frontend
npm install
VITE_API_URL=https://maintain-ai-3.vercel.app npm run build
```

On Windows PowerShell:

```powershell
$env:VITE_API_URL="https://maintain-ai-3.vercel.app"
npm run build
```

Then:

```bash
cd ../desktop
npm install
npm run dist
```

Installers are written to `desktop/dist/`.

Targets:
- Windows: `.exe`
- macOS: `.dmg`
- Linux: `.AppImage` and `.deb`

## GitHub Actions

The workflow at `.github/workflows/desktop-build.yml` builds Windows, macOS, and Linux installers.

It runs:
- Manually from GitHub Actions
- Automatically when a version tag such as `v0.2.0` is pushed

Every build uploads installable artifacts. Version tags additionally create a GitHub Release containing the installers.

A new desktop build does not require a Vercel deployment. The installed client talks to the hosted backend over HTTPS and WebSocket.

## Security

The installer contains no database credentials, JWT signing secrets, Gemini API keys, or backend secrets. Do not put secrets into the frontend build.

## Release process

1. Push the desired code to `Lab`.
2. Create a version tag such as `v0.2.0`.
3. GitHub Actions builds Windows, macOS, and Linux installers.
4. The workflow publishes the installers to the GitHub Release.
5. Users install the package for their operating system and connect to the online MAINTAIN AI backend.
