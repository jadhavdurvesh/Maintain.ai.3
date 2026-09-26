# MAINTAIN AI 3 — Authentication & Identity

## 1. Purpose

This document explains exactly how identity moves through MAINTAIN AI 3 across the web, Android, and Workforce clients.

The platform uses a hybrid identity/application model:

```text
Supabase Auth
    |
    | access token
    v
Maintain.ai FastAPI
    |
    +--> Maintain user
    +--> organization
    +--> application access
    +--> role
    +--> machine assignments
    |
    v
Neon/Postgres authorization data
```

Supabase authenticates the person. Maintain.ai decides what that authenticated person is allowed to do.

## 2. Supabase Auth

The backend reads:

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SECRET_KEY`

The publishable key may be used by clients. The secret key is backend-only.

The backend verifies access tokens through `backend/app/supabase_auth.py`. Depending on the token algorithm, verification uses the Supabase JWKS endpoint or the Supabase `/auth/v1/user` endpoint. fileciteturn152file0

## 3. Maintain user mapping

Supabase identity is mapped to the Maintain user by:

1. `supabase_user_id`
2. email as a fallback during synchronization

The Maintain user owns the trusted organization and role context. The backend then checks `UserApplicationAccess` for the requested application. fileciteturn153file0

Application values currently recognized by the backend:

- `engineering`
- `android`
- `workforce`

## 4. Web login

The React client has a dedicated Supabase Auth implementation in `frontend/src/supabaseAuth.js`.

### Password login

```text
Login.jsx
   |
   v
supabaseAuth.signIn(email, password)
   |
   v
Supabase /auth/v1/token?grant_type=password
   |
   v
access + refresh token
   |
   v
AuthContext
   |
   +--> POST /api/auth/supabase/sync
   |
   +--> GET /api/auth/me
   |
   v
application session
```

The browser stores the session locally and schedules token refresh before expiry. fileciteturn159file0

### OAuth

Google/Apple OAuth uses PKCE:

1. generate verifier
2. generate SHA-256 challenge
3. store verifier/state
4. redirect to Supabase authorize endpoint
5. receive authorization code
6. exchange code with verifier
7. hydrate the Supabase user
8. synchronize with Maintain.ai

The code explicitly checks OAuth state and refuses mismatches. fileciteturn159file0

### Registration

For email/password registration, the browser calls Supabase signup with metadata. If Supabase does not immediately return an access token, the UI waits for email confirmation and can call the Supabase resend endpoint. fileciteturn158file0

The repository does not directly call Resend. If Resend is used for the project's email delivery, it is configured behind Supabase's email/SMTP pipeline rather than in the frontend source.

## 5. `/api/auth/supabase/sync`

This endpoint is the bridge between Supabase identity and Maintain application identity.

It:

1. requires a Supabase Bearer token
2. verifies the token
3. validates application context
4. finds the Maintain user by Supabase ID/email
5. creates an organization/user when onboarding a genuinely new identity
6. checks existing application access
7. synchronizes the organization claim to Supabase on a best-effort basis
8. returns Maintain identity information

A user attempting "new organization" registration with an identity already linked to an organization is rejected rather than silently attaching to the existing organization. fileciteturn154file0

## 6. `/api/auth/me`

`/api/auth/me` is the canonical client session-context endpoint after authentication.

It returns the Maintain user ID, username, role, organization ID/name, and password-change state. fileciteturn154file0

Clients should treat this as display/session context, not as permission data that overrides backend checks.

## 7. Application access

The backend checks:

```text
Supabase identity
      |
      v
Maintain user
      |
      v
UserApplicationAccess
      |
      +--> engineering
      +--> android
      +--> workforce
```

This prevents a valid Supabase account from automatically gaining every MAINTAIN AI client.

## 8. Workforce technician authentication

The Workforce client signs in with Supabase email/password. Its `ApiClient.supabaseLogin()`:

1. requests a Supabase password token
2. stores access/refresh tokens
3. calls `/api/auth/supabase/sync`
4. calls `/api/auth/me`
5. uses the returned Maintain user as the authoritative worker context

The client sends `X-Maintain-Application: workforce` with backend API calls. fileciteturn149file0

The backend can require a first password change for administrator-created temporary technician accounts. The Workforce client explicitly handles `password_change_required`. fileciteturn149file0

## 9. Android authentication

The Android contract is:

1. authenticate with Supabase using the publishable key
2. store the returned access/refresh token
3. call `/api/auth/supabase/sync`
4. call `/api/auth/me`
5. use organization/role information as session context
6. send the Supabase access token to the Maintain backend for authorized REST calls

This is documented in the Android client contract and implemented through its repository/API layer. fileciteturn164file0turn164file2

## 10. Legacy Maintain JWT

The backend still contains a legacy email/password JWT path for compatibility. `backend/app/auth.py` creates/decodes the application JWT, and `deps.py` can resolve it when a Supabase identity cannot be resolved.

This is not a second authorization model that clients should invent. It is a compatibility path inside the backend.

When authenticated legacy users are resolved, application access is checked as well. fileciteturn153file0

## 11. Authorization versus authentication

Authentication answers:

> Who is this identity?

Authorization answers:

> What may this identity access or mutate?

The platform deliberately separates them.

For example, a technician can be authenticated successfully but still receive `403`/`404` behavior for a machine outside their assignment.

## 12. Technician authorization chain

```text
Supabase user
   |
   v
Maintain user
   |
   v
organization_id
   |
   v
role = technician
   |
   v
UserMachineAssignment
   |
   v
Machine
   |
   v
Telemetry / faults / maintenance / work orders
```

The client never creates this chain locally.

## 13. Realtime authentication

Realtime uses a separate short-lived token because the client needs to authenticate with Supabase Realtime while preserving Maintain.ai tenant and machine scope.

The client calls:

`POST /api/auth/realtime-token`

The backend builds a JWT containing:

- Supabase subject
- authenticated role
- organization ID
- Maintain user ID
- application
- active authorized machine IDs
- issue time
- expiry

The token currently expires after 55 minutes. fileciteturn154file0

This token is not a replacement for the normal Supabase identity token. It is a scoped realtime authorization token.

## 14. Web Realtime flow

```text
Browser
  |
  | Supabase access token -> /api/auth/realtime-token
  v
FastAPI
  |
  | query organization + machine assignments
  v
short-lived Realtime JWT
  |
  v
Supabase WebSocket
  |
  v
private organization telemetry topic
```

The web client opens the Supabase WebSocket and uses the backend-issued token when joining the private topic. fileciteturn157file0

## 15. Android/Workforce Realtime flow

```text
Client
  |
  | POST /api/auth/realtime-token
  v
FastAPI
  |
  +--> organization
  +--> role
  +--> machine assignments
  |
  v
scoped realtime JWT
  |
  v
Supabase Realtime
  |
  +--> machine:101:telemetry
  +--> machine:102:telemetry
```

Android and Workforce subscribe only to machine-scoped channels that the backend has authorized. The authorization is also enforced by Supabase RLS; client-side filtering is only UX. fileciteturn165file1

## 16. Device authentication is different

IoT devices do not log in as users.

They send:

`X-Device-Key: <machine-device-key>`

to:

`POST /api/devices/ingest`

The device key identifies one machine. It is not an organization-wide user credential.

The gateway explicitly does not use worker login credentials. fileciteturn150file0

## 17. Secrets

Never expose:

- `SUPABASE_SECRET_KEY`
- `SUPABASE_JWT_SECRET`
- database credentials
- Firebase service account JSON
- Gemini API credentials
- machine device keys

Client-visible configuration may include:

- Supabase URL
- Supabase publishable key
- API base URL

## 18. Authentication troubleshooting order

When login succeeds at Supabase but the app says unauthorized:

1. inspect `/api/auth/supabase/sync`
2. inspect `/api/auth/me`
3. verify the Maintain user has an organization
4. verify `UserApplicationAccess`
5. verify the correct `X-Maintain-Application`
6. verify machine assignment for technician users
7. only then inspect UI state

When REST works but realtime fails:

1. call `/api/auth/realtime-token`
2. inspect token issuance
3. verify Supabase Realtime JWT secret/configuration
4. verify RLS policy
5. verify topic name
6. verify authorized machine IDs
7. inspect WebSocket reconnect state

## 19. Non-goals

- Supabase Auth does not decide Maintain machine assignments.
- Neon/Postgres does not issue user authentication tokens.
- The frontend does not authorize cross-tenant access.
- Android and Workforce do not connect directly to Neon.
- IoT devices do not use Supabase user credentials.
