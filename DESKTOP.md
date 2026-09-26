# MAINTAIN AI Desktop — Installable Cloud Client

The desktop application is an Electron client for the hosted MAINTAIN AI backend. The installer contains the React/Vite frontend and Electron shell. It does **not** start or bundle a local FastAPI server.

## Architecture

```text
Windows / macOS / Linux
          │
          ▼
   MAINTAIN AI Desktop
        Electron
          │
          │ HTTPS + WSS
          ▼
 https://maintain-ai-3.vercel.app
          │
          ▼
    FastAPI backend
          │
          ├── Authentication
          ├── Neon/Postgres
          ├── ML / pretrained models
          ├── WebSocket telemetry
          └── Reports / exports
```

The frontend receives `VITE_API_URL` at build time. The Electron main process also has the same hosted URL as its default and performs a `/api/auth/status` health check every 10 seconds. A packaged installation therefore does not depend on `127.0.0.1:8000`.

## Backend URL contract

Default production URL:

```text
https://maintain-ai-3.vercel.app
```

GitHub Actions resolves the URL in this order:

1. Manual `backend_url` workflow input, when supplied.
2. Repository variable `MAINTAIN_AI_API_URL`.
3. The production default above.

The workflow verifies `/api/auth/status` **before** building the installer. If the hosted backend is unavailable, the build fails instead of producing an installer that cannot connect.

## Desktop startup

`desktop/main.js`:

- Uses the hosted backend by default.
- Never assumes the installed machine has a local FastAPI server.
- Checks `/api/auth/status` on startup and every 10 seconds.
- Exposes backend URL and connection state to the renderer through the preload bridge.
- Loads the packaged frontend from the Electron resources directory.
- Uses context isolation and disables Node integration in the renderer.

`frontend/src/api/client.js` uses the Electron bridge when present, so desktop API calls use the same backend URL as the Electron health check. In a normal browser it falls back to the build-time `VITE_API_URL`.

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

Development Electron loads `http://localhost:5173`. This is intentionally different from a packaged installation.

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

- Windows: `.exe` NSIS installer
- macOS: `.dmg`
- Linux: `.AppImage` and `.deb`

## GitHub Actions

The authoritative workflow is:

```text
.github/workflows/desktop-build.yml
```

The obsolete duplicate `build-desktop.yml` workflow has been removed because it built the frontend against `http://127.0.0.1:8000` and could therefore produce a desktop package with the wrong backend contract.

The authoritative workflow:

1. Checks out the repository.
2. Installs Node.js 20 and Python 3.12.
3. Resolves the hosted backend URL.
4. Verifies `/api/auth/status`.
5. Builds the frontend with the resolved `VITE_API_URL`.
6. Installs Electron dependencies.
7. Runs `node --check main.js`.
8. Builds the installer with electron-builder.
9. Verifies that an installer file exists.
10. Uploads the installer as a GitHub Actions artifact.
11. For version tags, publishes the installers to a GitHub Release.

The workflow supports a manual backend URL input so a future backend hostname can be adopted without editing the source code.

## Release process

1. Make and validate the desired code changes.
2. Run **Build MAINTAIN AI Desktop** manually from GitHub Actions for a test artifact.
3. Download the Windows artifact and install it on Windows.
4. Confirm the application reports a connected backend and can sign in.
5. Push a version tag such as `v0.3.0` when the build is ready for release.
6. GitHub Actions builds Windows, macOS, and Linux and publishes the release assets.

## Security

The installer contains no database credentials, JWT signing secrets, Gemini API keys, Supabase secret keys, or other backend secrets. Only public configuration such as the hosted API URL may be embedded in the frontend build.

Authentication remains server-controlled. The desktop client sends the authenticated bearer token to the backend; it does not receive or store Neon database credentials.

## Troubleshooting

### Desktop says backend is offline

Check the connection status shown by the application and verify that:

```text
https://maintain-ai-3.vercel.app/api/auth/status
```

responds successfully. If it does not, fix the hosted backend/deployment first; rebuilding the desktop package will not repair an unavailable server.

### Desktop opens but API requests use localhost

This indicates an old installer or an installer built by the obsolete workflow. Rebuild using `.github/workflows/desktop-build.yml`. The current workflow explicitly embeds the hosted URL and the Electron shell defaults to the same URL.

### GitHub Actions builds an installer but it cannot connect

Do not distribute that artifact until the workflow's backend-health step has passed. The current workflow makes that check mandatory.
