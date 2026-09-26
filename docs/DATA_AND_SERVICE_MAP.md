# MAINTAIN AI 3 — Data, Services & Code Map

## 1. Why this document exists

When debugging a feature, first answer three questions:

1. Which client initiated it?
2. Which backend route owns it?
3. Which service/database is authoritative for the resulting state?

Do not infer ownership from the UI.

## 2. Main backend layers

```text
backend/app/
  main.py                 FastAPI application + router loading
  database.py             SQLAlchemy engine/session
  models.py               database entities/enums
  deps.py                 identity + authorization dependencies
  auth.py                 legacy application JWT/password primitives
  supabase_auth.py        Supabase token/user administration bridge
  supabase_realtime.py    server-side Supabase Broadcast publisher
  notification_service.py FCM + in-app notification delivery
  audit.py                append-only audit event helper
  ml/                     online intelligence + temporal/advanced model logic
  routers/                HTTP/WebSocket API boundaries
```

The router list includes authentication, machines, maintenance, work orders, faults, alerts, analytics, reports, AI assistant, notifications, audit, devices, and user/admin operations. fileciteturn175file0

## 3. Database connection

`backend/app/database.py` reads `DATABASE_URL`.

Default local development:

`sqlite:///./maintain_ai.db`

Hosted PostgreSQL is supported without changing the SQLAlchemy model layer. When running serverless on Vercel with PostgreSQL, the code uses `NullPool` so frozen serverless processes do not retain stale database connections. fileciteturn155file0

## 4. Core relational ownership

The central data relationship is:

```text
Organization
  |
  +--> User
  |      |
  |      +--> UserApplicationAccess
  |      +--> UserMachineAssignment
  |      +--> NotificationDevice
  |      +--> InAppNotification
  |
  +--> Machine
         |
         +--> SensorReading
         +--> FaultRecord
         +--> Alert
         +--> MaintenanceRecord
         +--> WorkOrder
         +--> MachineSafetyPolicy
         +--> MachineSafetyEvent
         +--> ML evidence
```

The exact schema is implemented in `backend/app/models.py`; this map describes the ownership path used by authorization and feature flows.

## 5. Machines

Primary API: `backend/app/routers/machines.py`.

Machines are organization-owned. A technician's effective visibility is further constrained by `UserMachineAssignment`.

Archived machines remain in history but are excluded from normal operational visibility. Restore is an explicit admin operation.

## 6. Telemetry

Primary API: `backend/app/routers/devices.py`.

Inputs:

- REST device ingestion
- device WebSocket ingestion
- simulator/gateway sources

A reading is stored with machine, reading type, value, unit, source, timestamp, and optional external event ID.

Processing then runs through the online health/intelligence path before realtime delivery.

## 7. Telemetry processing pipeline

`_process_reading()` is the shared processing function for REST and WebSocket ingestion. fileciteturn168file0

```text
IngestPayload
   |
   v
SensorReading
   |
   +--> live sensor health
   +--> deterministic machine alert evaluation
   +--> online behaviour state
   +--> degradation processing
   +--> temporal window materialization
   +--> safety policy
   +--> anomaly event
   +--> worker notification
   |
   v
Supabase Broadcast + native WebSocket
```

Telemetry processing errors in feature materialization are intentionally prevented from taking down ingestion, although operational visibility for such failures remains important.

## 8. Online intelligence

The online layer is machine/signal scoped and tracks learned behaviour such as sample count, mean, variance, EWMA, last value, and anomaly score.

It is evidence of current behaviour, not automatically a calibrated failure probability.

## 9. Advanced ML

Advanced model artifacts are tenant scoped. Model status/inference routes must resolve through the machine's organization.

The existing product documentation explicitly distinguishes:

- Random Forest health/baseline model
- temporal bootstrap representation
- online behaviour/degradation evidence
- future supervised failure-risk artifacts

Only the final category can become a calibrated horizon-risk probability after leakage-safe labels and evaluation exist.

## 10. Work orders

Work orders are machine-linked maintenance operations.

The backend checks organization and, for technicians, machine assignment before allowing worker operations.

Completion creates downstream maintenance/outcome evidence exactly once by design.

## 11. Maintenance

Maintenance records are machine-linked historical/operational records.

Completion records the authenticated actor and is intended to be idempotent.

Machine health adjustments must not happen repeatedly when a client retries the same completion request.

## 12. Faults

Faults are machine-scoped records. Reporting a fault can produce in-app/push notifications to technicians assigned to that machine.

## 13. Alerts

Alerts are machine-scoped operational signals.

They may be generated by:

- maintenance conditions
- machine health conditions
- telemetry anomalies
- safety thresholds
- ML/behaviour evidence

High/critical worker notifications are handled by `notification_service.py`.

## 14. Notifications

There are two layers:

### In-app

`InAppNotification` records are stored in the application database.

### Push

Firebase Admin is initialized lazily from `FIREBASE_SERVICE_ACCOUNT_JSON`. Active `NotificationDevice` rows are turned into FCM messages. Invalid/unregistered tokens are deactivated. Push failures are deliberately prevented from breaking the core API transaction. fileciteturn171file0

## 15. Email

Current source code directly calls Supabase Auth's email-related endpoints:

- `/auth/v1/signup`
- `/auth/v1/resend`

The repository does not directly contain a Resend API integration. Therefore:

```text
React -> Supabase Auth -> configured email/SMTP provider -> user mailbox
```

If the external Supabase project is configured to use Resend SMTP, Resend belongs behind that boundary. The actual provider configuration is not represented by the repository code inspected here.

## 16. Realtime publisher

`backend/app/supabase_realtime.py` publishes private Broadcast events through Supabase using the backend-only secret key. fileciteturn156file0

This publisher is server-side only.

The frontend never receives the Supabase secret key.

## 17. Native WebSocket

`backend/app/routers/devices.py` also contains `/api/devices/stream`.

The connection is authorized by:

1. token validation
2. application context
3. Maintain user resolution
4. organization resolution
5. technician assignment resolution
6. machine allow-list filtering

The process-local stream therefore has server-side machine filtering rather than relying on the UI. fileciteturn169file0

## 18. IoT Gateway data path

The gateway is a connectivity layer, not a user client.

```text
Serial controller
  |
  v
Gateway serial parser
  |
  v
ApiClient
  |
  +--> X-Device-Key
  +--> event_id
  +--> reading_type/value/unit
  +--> recorded_at
  |
  v
POST /api/devices/ingest
```

The gateway stores offline telemetry in a local SQLite queue. Event IDs are unique, allowing retry/deduplication semantics. `409` is treated as successful delivery of an already-known event. fileciteturn167file0

## 19. Gateway secrets and configuration

Gateway configuration is stored under:

`~/.maintain-ai-iot-gateway/`

Device keys are stored through the OS credential store via `keyring`, while non-secret configuration is stored in JSON. fileciteturn166file0

The gateway's connectivity test calls `/api/devices/ping`, not telemetry ingestion, so a diagnostic check does not create fake readings.

## 20. Android data path

Android uses Retrofit/OkHttp and a repository abstraction. The client does not connect to Neon directly.

The current documented API includes machine, alert, work-order, readings, model-status, risk-prediction, and model-training operations. fileciteturn146file0

Authentication and realtime are additional cross-client contracts described in `AUTHENTICATION_AND_IDENTITY.md`.

## 21. Workforce data path

Flutter uses HTTP for REST operations and `web_socket_channel` for realtime. Its dependencies also include Firebase messaging/local notifications. fileciteturn148file0

The client obtains its Supabase session first, then calls the shared Maintain backend.

## 22. Frontend API client

`frontend/src/api/client.js` is the shared React HTTP client.

It:

- reads `VITE_API_URL`
- uses a desktop-provided backend URL when running inside Electron
- adds `Authorization: Bearer ...` when a token exists
- adds `X-Maintain-Application: engineering`
- caches GET requests briefly
- coalesces identical in-flight GET requests
- clears cache after mutations
- converts 401 responses into auth-state invalidation

fileciteturn160file0

## 23. Frontend realtime client

`frontend/src/realtime.js` connects to Supabase Realtime over WebSocket, requests a backend-issued realtime token, joins the organization telemetry topic, sends heartbeats, and reconnects with exponential backoff. fileciteturn157file0

## 24. Frontend auth state

`AuthContext.jsx` is the React session orchestrator. It:

- checks auth status
- restores Supabase session
- synchronizes the identity with Maintain.ai
- loads `/api/auth/me`
- stores organization context for realtime
- handles logout
- handles onboarding
- handles email confirmation state
- clears API cache when auth changes

fileciteturn158file0

## 25. Deployment boundary

The repository currently describes Vercel as the hosted deployment target. The production topology is therefore:

```text
Vercel-hosted web/backend
        |
        +--> Neon/Postgres
        +--> Supabase Auth
        +--> Supabase Realtime
        +--> Firebase FCM
        +--> optional external AI/email providers
```

A desktop client may package the frontend/backend differently but still communicate with the same hosted API when configured that way.

## 26. Debugging a feature end-to-end

Use this sequence:

```text
UI event
  -> client API/realtime function
  -> HTTP/WebSocket request
  -> FastAPI router
  -> auth dependency
  -> organization/machine scope
  -> service/model helper
  -> database mutation/read
  -> side effect (audit/notification/realtime/ML)
  -> client state refresh
```

If a value looks wrong, locate it at each boundary rather than patching the final UI.

## 27. Common mistakes to avoid

- reading Neon directly from a client
- putting service secrets in Vite/Android/Flutter config
- treating Supabase Realtime as durable storage
- treating an FCM token as a user identity
- using a device key for user authorization
- trusting a client-provided organization ID
- filtering technician machine data only in UI
- treating an anomaly score as a failure probability
- assuming an email provider is Resend merely because an email is sent
