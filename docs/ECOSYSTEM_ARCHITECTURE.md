# MAINTAIN AI 3 — Complete Ecosystem Architecture

Status: living architecture document for `main`.

This document explains how the repositories, runtimes, identity systems, databases, realtime transports, notifications, AI services, and deployment services fit together. It is intentionally written from the implementation currently present in the repositories; when a service is configured outside Git, that boundary is marked explicitly.

## 1. The ecosystem at a glance

```text
                                   MAINTAIN AI 3
                                         |
             +---------------------------+---------------------------+
             |                           |                           |
             v                           v                           v
      Engineering Web             Android Operations        Workforce / Technician
      React + Vite                Kotlin + Compose           Flutter
             |                           |                           |
             +------------- HTTPS / REST + Auth --------------------+
                                         |
                                         v
                                FastAPI application
                                         |
                    +--------------------+--------------------+
                    |                    |                    |
                    v                    v                    v
              Neon/Postgres       Supabase Auth        AI / ML services
             system of record       identity             local + optional Gemini
                    |                    |
                    |                    +--> Realtime Broadcast/WebSocket
                    |
                    +--> organizations/users/machines/
                         telemetry/faults/maintenance/
                         work orders/audit/ML evidence

 IoT path:

 Industrial sensors / controller
            |
        USB / Serial
            |
            v
 MAINTAIN-AI-IoT-Gateway
            |
     X-Device-Key + HTTPS
            |
            v
   POST /api/devices/ingest
            |
            v
      FastAPI backend
            |
            +--> Neon/Postgres
            +--> online intelligence / anomaly / safety
            +--> alerts / notifications
            +--> Supabase Realtime
            +--> client dashboards

 Notification path:

 Backend event -> in-app notification row -> Firebase Cloud Messaging -> mobile device
```

## 2. Repositories

| Repository | Runtime | Responsibility |
|---|---|---|
| `Maintain.ai.3` | React/Vite + FastAPI/Python | canonical platform/backend and engineering client |
| `Maintain.ai.android` | Kotlin/Android/Compose | Android engineering/operations client |
| `Maintain.ai-workforce-client` | Flutter/Dart | technician/workforce client |
| `MAINTAIN-AI-IoT-Gateway` | Python/PySide6 | industrial serial-to-cloud gateway |
| `MAINTAIN-AI-Local-Intelligence` | Python desktop/local service | local/edge model runtime; separate deployment unit |
| `MAINTAIN-AI-Sensor-Simulator` | separate repository | test/simulation source for telemetry |

The first four are the primary cross-client ecosystem documented here. The local-intelligence repository is an AI execution component and must not become a second tenant database or identity authority.

## 3. Authority model

There are three different kinds of authority and they must not be confused:

### Identity authority — Supabase Auth

Supabase Auth owns the authentication identity and issues access/refresh tokens. The browser and mobile clients use the Supabase publishable key. The Supabase secret/service credentials remain backend-only.

### Application authorization authority — Maintain.ai backend

The FastAPI backend resolves the Supabase identity to a Maintain user, organization, role, application access, and machine assignments. Client-side filtering is never the authorization boundary.

### Data authority — Neon/Postgres

The application database stores the organization and operational records. Hosted deployments use PostgreSQL/Neon through SQLAlchemy. Local development can use SQLite by changing `DATABASE_URL`.

This gives the canonical chain:

`Supabase identity -> Maintain user -> organization -> application access -> role -> machine assignment -> resource`

## 4. What each external service does

### Supabase

Used for:

- authentication
- OAuth provider flows
- password authentication
- session refresh
- Realtime WebSocket transport
- private Broadcast topics

Not the primary application database. The backend's Neon/Postgres data remains the source of truth for organization membership and authorization.

### Neon/Postgres

Used for the hosted application database. SQLAlchemy models are the application schema. The backend resolves tenant ownership and all resource visibility from this database.

### Vercel

The README and deployment configuration identify Vercel as the current hosted web/backend deployment target. The deployed frontend calls the hosted API; the backend uses PostgreSQL/Neon and external Supabase services.

### Firebase Cloud Messaging

Used for worker/technician push notifications. The backend lazily initializes Firebase Admin from `FIREBASE_SERVICE_ACCOUNT_JSON`, stores notification-device records in the application database, and sends FCM messages to active device tokens.

### Resend / email delivery

The repository does **not** contain a direct Resend API client or `RESEND_API_KEY`. Email confirmation is requested through Supabase Auth (`/auth/v1/signup` and `/auth/v1/resend`). If Resend is configured as the Supabase project's SMTP/email provider, Resend is therefore an external delivery service behind Supabase rather than a service called directly by this repository. The actual SMTP/provider configuration lives outside Git and must be documented separately when its project settings are available.

### Gemini

The maintenance assistant can use Gemini as an optional enhancement. Gemini is not the identity provider, operational database, or authorization system. AI output must remain subject to the backend's machine/organization context and the product's diagnostic semantics.

## 5. Client communication rules

### Web engineering client

- REST/HTTPS to FastAPI for application data.
- Supabase Auth directly from the browser for identity.
- Backend-issued short-lived Realtime token for private Supabase Realtime subscriptions.
- Supabase WebSocket transport for live telemetry.

### Android

- Supabase password authentication with publishable key.
- Store access/refresh tokens locally.
- Call `/api/auth/supabase/sync`.
- Call `/api/auth/me`.
- Call application APIs with `Authorization: Bearer <Supabase access token>`.
- Request `/api/auth/realtime-token` before private Realtime subscriptions.
- Join machine-scoped telemetry topics returned from backend-authorized machine visibility.

### Workforce Flutter

- Supabase password authentication.
- Store access/refresh tokens in app preferences.
- Sync with Maintain.ai backend.
- Enforce first-login password change when `password_change_required` is returned.
- Use `X-Maintain-Application: workforce`.
- Request a backend-issued Realtime token.
- Subscribe to assigned-machine topics.
- Register mobile notification devices with the backend/FCM path.

### IoT Gateway

The gateway does not use a worker's Supabase login. It authenticates machine telemetry using a machine-specific device key sent as `X-Device-Key` to `/api/devices/ingest`.

## 6. Data flow: sign-in

```text
Client
  |
  | email + password
  v
Supabase Auth
  |
  | access_token + refresh_token
  v
Client
  |
  | POST /api/auth/supabase/sync
  | Authorization: Bearer <Supabase token>
  v
FastAPI
  |
  +--> verify Supabase token
  +--> find/create Maintain user
  +--> resolve organization
  +--> check application access
  +--> refresh Supabase organization claim (best effort)
  v
/api/auth/me
  |
  v
Client session context
```

## 7. Data flow: telemetry

```text
Sensor
  -> Gateway
  -> POST /api/devices/ingest
  -> device-key authentication
  -> machine resolution
  -> SensorReading persisted
  -> health update
  -> deterministic alert evaluation
  -> online behaviour model
  -> degradation processing
  -> temporal window materialization
  -> anomaly event / safety event
  -> worker notification when applicable
  -> Supabase private broadcast
  -> web/android/workforce realtime client
```

REST and the native device WebSocket ingestion path share `_process_reading`, so telemetry processing semantics are intended to remain consistent.

## 8. Data flow: work order

```text
Engineering client
  -> POST/PATCH work-order API
  -> FastAPI authorization
  -> organization + machine scope
  -> WorkOrder row
  -> optional worker notification
  -> technician client refresh/realtime
  -> technician completes
  -> maintenance record + outcome evidence
  -> audit history
```

Completion is intended to be idempotent so retrying the same operation does not create duplicate maintenance/outcome side effects.

## 9. Realtime architecture

There are two realtime mechanisms in the platform:

1. Native FastAPI WebSocket `/api/devices/stream`.
2. Supabase Realtime private Broadcast, which is the client-facing hosted realtime path.

The hosted web/mobile clients use Supabase Realtime. The native FastAPI stream remains an additional application WebSocket path for supported clients/device flows.

### Supabase topic scopes

Engineering:

`org:<organization_id>:telemetry`

Android/workforce:

`machine:<machine_id>:telemetry`

The backend-issued Realtime JWT contains the active organization, application, Maintain user ID, and authorized machine IDs. Supabase RLS uses these claims for private topic authorization.

## 10. Security boundaries

The backend must enforce:

- organization isolation
- application access
- role permissions
- technician machine assignment
- archived-machine visibility
- device-key ownership
- ML artifact tenant scope
- report/export tenant scope
- notification tenant consistency

A frontend hiding a machine is not a security control.

## 11. Local development versus hosted deployment

Local development can use:

- FastAPI on `localhost:8000`
- Vite on `localhost:5173`
- SQLite via default `DATABASE_URL`
- local Supabase project or hosted Supabase configuration
- Android emulator `10.0.2.2:8000`
- LAN IP for physical devices

Hosted deployment uses the configured Vercel backend/frontend, Neon/Postgres, Supabase Auth/Realtime, and Firebase where mobile push is enabled.

## 12. Configuration ownership

| Configuration | Client/Service | Secret? |
|---|---|---|
| `VITE_SUPABASE_URL` | web | no |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | web | publishable |
| `SUPABASE_URL` | backend | no |
| `SUPABASE_PUBLISHABLE_KEY` | backend | publishable |
| `SUPABASE_SECRET_KEY` | backend | **yes** |
| `SUPABASE_JWT_SECRET` | backend | **yes** |
| `DATABASE_URL` | backend | **yes** when it contains DB credentials |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | backend | **yes** |
| `MAINTAIN_API_URL` | gateway/mobile | no |
| machine `X-Device-Key` | gateway | **yes** |
| Gemini API key/settings | backend | **yes** |
| Supabase SMTP/Resend configuration | Supabase project | **external to repo** |

Never place backend secrets in React, Android APK source, Flutter client configuration, firmware, or the gateway's checked-in source.

## 13. What is authoritative where?

| Question | Authoritative source |
|---|---|
| Is this person authenticated? | Supabase Auth token/session |
| Is this person a Maintain user? | Neon/Postgres + backend mapping |
| Which organization? | Maintain user row in Neon/Postgres |
| Which role? | Maintain user row |
| Which application can they use? | `UserApplicationAccess` in Neon/Postgres |
| Which machines can a technician access? | `UserMachineAssignment` + machine organization |
| What is the machine's telemetry history? | `SensorReading` in Neon/Postgres |
| What is live telemetry delivery? | Supabase Realtime transport, authorized by backend-issued claims/RLS |
| Which push devices belong to a worker? | `NotificationDevice` in Neon/Postgres |
| How is push delivered? | Firebase Cloud Messaging |
| How is confirmation email delivered? | Supabase Auth email pipeline; provider may be Resend/SMTP configured outside this repo |
| How does a machine authenticate telemetry? | machine-specific device key |

## 14. Important non-goals

- Supabase Realtime must not become the database of record.
- Android/Flutter must not query Neon directly.
- IoT devices must not receive user credentials.
- The local-intelligence node must not become the tenant/auth database.
- Clients must not invent organization or machine permissions.
- Resend must not be added directly to the browser for transactional identity mail.

## 15. Source repositories

- Main platform: `jadhavdurvesh/Maintain.ai.3`
- Android: `jadhavdurvesh/Maintain.ai.android`
- Workforce: `jadhavdurvesh/Maintain.ai-workforce-client`
- IoT gateway: `jadhavdurvesh/MAINTAIN-AI-IoT-Gateway`
- Local intelligence: `jadhavdurvesh/MAINTAIN-AI-Local-Intelligence`

See `CROSS_CLIENT_ARCHITECTURE_AUDIT.md` for the security audit and acceptance-test matrix.
