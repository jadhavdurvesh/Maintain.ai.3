# Mobile & Gateway Implementation Contracts

## Android

Repository: `Maintain.ai.android`

The Android client is a REST-first operations client. Its README documents Retrofit/OkHttp, Compose, ViewModel/state, WorkManager, DataStore, and PDF generation. fileciteturn146file0

### Authentication contract

```text
Supabase password auth
 -> access/refresh tokens
 -> Maintain /api/auth/supabase/sync
 -> Maintain /api/auth/me
```

The repository's client contract explicitly requires this sequence. fileciteturn164file0

### Realtime contract

`RealtimeTelemetry.kt` builds the Supabase Realtime WebSocket URL and works with backend-authorized machine IDs. fileciteturn163file0

### API contract

The documented API surface includes:

- machines
- alerts
- work orders
- machine readings
- model status
- risk predictions
- model training

The Android client must not interpret these as an independent source of truth; backend authorization and model semantics remain canonical. fileciteturn146file0

## Workforce

Repository: `Maintain.ai-workforce-client`

### Authentication

`lib/main.dart` stores worker access/refresh tokens, refreshes sessions through Supabase, calls Maintain sync/me, and sends the workforce application header. fileciteturn149file0

### Technician state

The backend can require a first-login password change. The client blocks normal workforce access until the password-change operation completes.

### Realtime

The client requests `/api/auth/realtime-token` and joins machine-scoped topics. The contract says Supabase RLS validates the authorized machine IDs. fileciteturn165file1

### Notifications

The Flutter dependency set includes Firebase Messaging and local notification support. fileciteturn148file0

The backend stores notification devices and sends FCM pushes through Firebase Admin. fileciteturn171file0

## IoT Gateway

Repository: `MAINTAIN-AI-IoT-Gateway`

### Identity

The gateway is a device principal, not a user principal.

```text
X-Device-Key -> one machine
```

### Data transport

```text
Serial JSON
 -> gateway validation
 -> event_id
 -> HTTPS POST /api/devices/ingest
```

### Offline queue

Failed telemetry is written to local SQLite and retried. Unique event IDs prevent duplicate queue rows and backend `409` responses are treated as successful deduplication. fileciteturn167file0

### Secret storage

Device keys are stored through the OS credential store. Configuration is stored separately under the gateway configuration directory. fileciteturn166file0

### Connectivity testing

The gateway uses `/api/devices/ping` for key validation. A connectivity test therefore does not create telemetry.

## Sensor simulator

The simulator is a testing producer. It should exercise the same ingestion endpoint and event schema used by real devices/gateway deployments.

## Contract invariant

All mobile/gateway clients must preserve this boundary:

```text
Client/device
    |
    v
FastAPI
    |
    +--> authentication
    +--> authorization
    +--> data validation
    +--> Neon persistence
    +--> ML processing
    +--> notifications/realtime
```

No mobile app or gateway may bypass FastAPI and write directly to Neon.
