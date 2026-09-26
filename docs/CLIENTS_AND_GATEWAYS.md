# MAINTAIN AI 3 — Clients, Mobile Apps & Gateways

This is the cross-repository contract for the external clients that connect to `Maintain.ai.3`.

## 1. Engineering Web

Repository: `Maintain.ai.3`

Technology:

- React
- Vite
- browser WebSocket
- Supabase Auth

Primary files:

- `frontend/src/AuthContext.jsx` — session lifecycle
- `frontend/src/supabaseAuth.js` — direct Supabase Auth transport
- `frontend/src/api/client.js` — REST transport
- `frontend/src/realtime.js` — Supabase Realtime WebSocket
- `frontend/src/pages/*` — feature UI

Backend boundary:

- REST: `/api/*`
- realtime: Supabase private Broadcast

## 2. Android Operations App

Repository: `Maintain.ai.android`

Technology:

- Kotlin
- Jetpack Compose
- Retrofit
- OkHttp
- DataStore/Android local storage
- WorkManager

The Android client is a mobile operations client, not a database client. It talks to FastAPI through REST and uses Supabase Realtime for live telemetry.

Primary code areas documented by the Android repository:

- `data/Api.kt` — Retrofit API contract
- `data/Models.kt` — API/application models
- `data/Repository.kt` — authentication, networking, data aggregation
- `data/RealtimeTelemetry.kt` — realtime telemetry
- `MainActivity.kt` — application/UI entry
- `AlertWorker.kt` — background alert processing
- `ReportPdf.kt` — PDF reports

Authentication:

```text
Supabase Auth
 -> access token
 -> /api/auth/supabase/sync
 -> /api/auth/me
 -> Maintain API
```

Realtime:

```text
/api/auth/realtime-token
 -> short-lived scoped token
 -> Supabase WebSocket
 -> machine:<id>:telemetry
```

The Android client contract explicitly states that organization/role information returned by `/api/auth/me` is session context and the backend remains authoritative. fileciteturn164file0

## 3. Workforce / Technician App

Repository: `Maintain.ai-workforce-client`

Technology:

- Flutter
- Dart
- HTTP
- `web_socket_channel`
- Shared Preferences
- Firebase Messaging
- local notifications

Primary code areas:

- `lib/main.dart` — app bootstrap, auth, API client, primary application state
- `lib/realtime_service.dart` — Supabase Realtime
- `lib/notification_service.dart` — FCM/local notification integration
- `lib/machine_details_page.dart` — machine context
- `lib/app_config.dart` — deployment configuration

Authentication:

```text
Supabase email/password
 -> access/refresh token
 -> /api/auth/supabase/sync
 -> /api/auth/me
 -> workforce application access
```

The client sends `X-Maintain-Application: workforce` and handles the backend's first-login password-change state. fileciteturn149file0

Realtime:

```text
POST /api/auth/realtime-token
 -> machine allow-list
 -> Supabase private Broadcast
 -> machine:<id>:telemetry
```

The Workforce client contract states that RLS validates the machine IDs in the backend-issued token; Flutter filtering is only UX. fileciteturn165file1

## 4. IoT Gateway

Repository: `MAINTAIN-AI-IoT-Gateway`

Technology:

- Python
- PySide6
- pyserial
- requests
- SQLite offline queue
- keyring
- PyInstaller/Inno Setup packaging

Primary code areas:

- `gateway/config.py` — config + OS credential-store keys
- `gateway/api_client.py` — ingestion, retries, offline queue, connectivity check
- `gateway/*serial*` — serial device layer
- `ui/*` — desktop interface
- `protocol/*` — device protocol support

The gateway authenticates as a machine using `X-Device-Key`, not as a human user. fileciteturn150file0

### Offline behavior

The gateway stores failed telemetry in local SQLite with a unique `event_id`. It retries queued events when connectivity returns and treats `409` as successful deduplication. fileciteturn167file0

### Credential storage

Device keys are kept in the operating system credential store through `keyring`. General gateway configuration is stored under `~/.maintain-ai-iot-gateway/`. fileciteturn166file0

## 5. Local Intelligence node

Repository: `MAINTAIN-AI-Local-Intelligence`

This component is intentionally separate from the main application database and identity system.

Its role is local/edge model execution. The main platform should remain the source of truth for organization, users, machines, work orders, maintenance, and authorization.

Integration direction:

```text
Maintain.ai backend
    |
    | authenticated/local controlled request
    v
Local Intelligence API
    |
    v
model inference
    |
    v
structured evidence
    |
    v
Maintain.ai backend
```

See the local repository's `docs/INTEGRATION.md` and `docs/ARCHITECTURE.md` for its internal model/runtime contract.

## 6. Sensor simulator

Repository: `MAINTAIN-AI-Sensor-Simulator`

Its role is development/testing telemetry generation. It should use the same canonical device-ingestion contract rather than inventing a separate data schema.

## 7. Cross-client headers

### Engineering web

`X-Maintain-Application: engineering`

### Android

The Android client uses the Android application contract when calling Maintain APIs.

### Workforce

`X-Maintain-Application: workforce`

### IoT

`X-Device-Key: <machine-device-key>`

These are different credentials because they represent different principals.

## 8. Shared endpoint contracts

| Capability | Web | Android | Workforce | Gateway |
|---|---:|---:|---:|---:|
| Supabase user auth | yes | yes | yes | no |
| `/api/auth/supabase/sync` | yes | yes | yes | no |
| `/api/auth/me` | yes | yes | yes | no |
| `/api/auth/realtime-token` | yes | yes | yes | no |
| machine REST APIs | yes | yes | assigned only | no |
| work-order APIs | yes | yes | assigned only | no |
| telemetry REST ingestion | no | no | no | yes |
| private Supabase Realtime | yes | yes | yes | no |
| device key | no | no | no | yes |
| FCM push registration | web notification surfaces vary | supported | supported | no |

## 9. Compatibility definition

A client is compatible when it:

- uses the shared Supabase/HTTP authentication contract
- identifies its application context
- never decides tenant authorization locally
- consumes only backend-authorized machine data
- uses the canonical telemetry schema
- respects backend ML semantics
- reconnects safely
- does not create a second tenant model

## 10. Change rule

When a backend contract changes:

1. update the main backend
2. update this document
3. update Android contract/code
4. update Workforce contract/code
5. update gateway contract/code when telemetry/device behavior changes
6. add an integration test
7. only then treat the contract as changed
