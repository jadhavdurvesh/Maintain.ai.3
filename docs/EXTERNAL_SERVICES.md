# External Services & Cloud Boundaries

This document records how MAINTAIN AI uses services outside the Git repository. It is intentionally explicit about what is implemented in code versus what must be configured in a provider dashboard.

## 1. Service map

| Service | Purpose | Code touches it directly? | Secrets involved |
|---|---|---:|---|
| Supabase Auth | user identity, sign-in, verification, password flows | Yes | publishable key client-side; secret/service key backend-only |
| Supabase Realtime | private telemetry broadcast transport | Yes | backend secret key; short-lived realtime token |
| Neon/PostgreSQL | hosted application database | Yes, through SQLAlchemy | `DATABASE_URL` backend-only |
| Vercel | hosted frontend/backend deployment target | Through repository deployment configuration | provider-managed project env vars |
| Resend | email delivery only when configured as Supabase SMTP/provider | No direct client found | SMTP credentials live outside this repository |
| Firebase Cloud Messaging | Android push notifications | Yes, backend through Firebase Admin | service-account JSON backend-only |
| Gemini | optional AI assistant enhancement | Yes, backend when enabled | `GEMINI_API_KEY` backend-only |
| GitHub Actions | CI validation/builds | Yes, workflow files | GitHub-managed environment/secrets where required |

## 2. Important boundary

The browser, Android app, Workforce app and IoT Gateway must not receive database credentials, Supabase secret keys, Firebase service-account credentials, or other backend secrets.

The intended trust boundary is:

```text
Clients / Gateway
       |
       | HTTPS / authorized realtime
       v
FastAPI backend
       |
       +--> Neon/PostgreSQL
       +--> Supabase Auth / Realtime
       +--> Firebase Admin
       +--> optional Gemini
       +--> notification / ML services
```

## 3. Supabase

Supabase is used for identity and realtime transport. The backend reads `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` and backend-only `SUPABASE_SECRET_KEY`. The frontend uses `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`.

Telemetry is persisted to the application database first and then published to private organization/machine-scoped Supabase Realtime topics. The repository also contains the Realtime policy SQL used to restrict topic reads.

## 4. Neon/PostgreSQL

The hosted system uses the same SQLAlchemy model layer as local SQLite. `DATABASE_URL` belongs only in the backend environment. The frontend and desktop application never connect directly to Neon.

## 5. Vercel

The repository contains `vercel.json` describing separate frontend and backend services and routing `/api/*` to the backend while other paths go to the frontend. Provider-side project configuration is not stored in Git.

See `VERCEL_OPERATIONS.md` for the deployment contract and verification checklist.

## 6. Resend / email

No direct Resend API client or `RESEND_API_KEY` is present in the repository. Email actions are requested through Supabase Auth. If the Supabase project is configured to use Resend as its SMTP/email provider, Resend is an external delivery service behind Supabase.

Do not document a direct Resend integration unless a direct SDK/API client is actually added to the codebase.

## 7. Firebase / FCM

The backend uses Firebase Admin for push notification delivery. The service-account credential is backend-only. Android receives FCM notifications and registers its device token with the backend.

## 8. Gemini

Gemini is optional. The backend can use `GEMINI_API_KEY` for the Gemini-backed assistant path. The application is designed to retain an offline/local path when Gemini is unavailable.

## 9. What is not in Git

The following must be treated as external configuration and verified in the provider dashboard before production changes:

- Supabase project URL and project identity
- Supabase Auth email/SMTP settings
- Supabase redirect/site URLs
- Supabase Realtime authorization settings/policies
- Neon project/database credentials
- Vercel project, domains, environment variables and deployment settings
- Firebase project and service-account configuration
- Resend SMTP/domain configuration, if used
- Gemini API key
- mobile package/application credentials
- DNS/domain records

Never commit the values of those secrets to this repository.

## 10. Status vocabulary

- **Implemented**: confirmed by source code or committed configuration.
- **Externally configured**: required provider-side setting not represented by source code.
- **Historical/project-context**: remembered from prior engineering work but not independently verifiable from the current repository.
- **Planned**: intended future behavior.

When a provider dashboard cannot be inspected, keep the item in the externally configured category rather than guessing.
