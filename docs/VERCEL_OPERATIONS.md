# Vercel Operations

## Repository contract

`vercel.json` defines two deployable services:

- `frontend/` using Vite
- `backend/` using `app.main:app`

Routing is:

```text
/api/*  -> backend
/*      -> frontend
```

This means the browser can use the same hosted origin for the UI and API rather than hard-coding a separate backend hostname.

## What the repository proves

The routing/deployment contract is committed in `vercel.json`. The repository also contains GitHub Actions validation/build workflows.

## What must be checked in Vercel

Provider-side configuration is not represented by `vercel.json` alone. Before calling a deployment production-ready, verify in the Vercel project:

1. The correct GitHub repository is connected.
2. The intended production branch is selected.
3. Frontend/backend roots match the repository layout.
4. Required environment variables exist in the correct environment (Development/Preview/Production).
5. Frontend variables use the `VITE_` prefix where Vite requires browser exposure.
6. Backend secrets are not prefixed `VITE_` and are not exposed to the browser bundle.
7. The deployed `/api/health` endpoint responds successfully.
8. The frontend can call `/api/*` through the same deployment.
9. Supabase redirect/site URLs include the actual production frontend URL.
10. Database and external-service connectivity is verified from the deployed backend.

## Environment boundary

Frontend/browser configuration may include only values intended for public use, such as:

- `VITE_API_URL` when a separate API origin is intentionally used
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY`

Backend-only values include:

- `DATABASE_URL`
- `SUPABASE_SECRET_KEY`
- `SUPABASE_JWT_SECRET` where legacy JWT compatibility is enabled
- `FIREBASE_SERVICE_ACCOUNT_JSON`
- `GEMINI_API_KEY`

Do not put these backend secrets into frontend environment variables.

## Deployment flow

```text
Git push
  -> GitHub
  -> Vercel build/deploy
  -> frontend service + backend service
  -> /api/* routed to FastAPI
  -> frontend routes served by Vite build
```

## Troubleshooting

### UI loads but API fails

Check the Vercel backend deployment/runtime logs, then test `/api/health`. Confirm backend environment variables and database connectivity.

### API works but authentication redirects fail

Check the Supabase Auth Site URL and redirect allow-list against the actual Vercel production/preview URL.

### Local development works but Vercel fails

Compare local `.env` names with Vercel environment-variable names. Do not copy local secret files into Git; configure the values in the provider dashboard.

### Database connection failures

Verify `DATABASE_URL`, SSL requirements, and serverless connection/pooling behavior. The application should not expose the database URL to clients.

## Verification record

The exact Vercel project/domain/environment-variable values are external state. Record them here only after they are actually inspected; do not infer them from source code.
