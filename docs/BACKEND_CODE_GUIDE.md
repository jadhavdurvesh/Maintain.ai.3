# Backend Code Guide

## 1. Request lifecycle

```text
HTTP/WebSocket request
 -> FastAPI router
 -> dependency/authentication
 -> organization/machine authorization
 -> SQLAlchemy session
 -> domain/helper/ML operation
 -> database mutation/read
 -> audit/notification/realtime side effects
 -> response
```

## 2. Application entry

`backend/app/main.py` creates the FastAPI application, middleware and router registration. Router loading is centralized so import failures can be detected during startup/CI.

## 3. Database

`backend/app/database.py` owns the SQLAlchemy engine/session factory. `DATABASE_URL` controls SQLite versus PostgreSQL/Neon. fileciteturn155file0

## 4. Models

`backend/app/models.py` contains the relational entities and enums. The important ownership chain is:

`Organization -> User -> Machine -> operational records`

and:

`User -> UserApplicationAccess / UserMachineAssignment / NotificationDevice`

## 5. Authentication dependencies

`backend/app/deps.py` is the main authorization gateway for normal routes.

It can resolve:

- Supabase identity
- legacy Maintain JWT
- explicitly configured local unauthenticated development mode

After identity resolution it checks organization membership and application access. Technician machine visibility is calculated from assignments. fileciteturn153file0

## 6. Supabase bridge

`backend/app/supabase_auth.py` handles:

- token verification
- Supabase admin user creation/deletion
- organization claim synchronization
- authenticated password changes
- invitation support

It is a server-side integration and contains the secret-key boundary. fileciteturn152file0

## 7. Authentication router

`backend/app/routers/auth.py` owns:

- auth status
- legacy register/login compatibility
- Supabase identity synchronization
- password change
- Realtime token issuance
- current-user session information

The Realtime token is generated only after Maintain authorization has resolved the user's organization/application/machine scope. fileciteturn154file0

## 8. Devices router

`backend/app/routers/devices.py` is one of the most important integration boundaries.

It handles:

- device-key telemetry ingestion
- device connectivity checks
- machine safety policy
- REST/WebSocket telemetry processing
- native telemetry WebSocket
- device command paths
- online intelligence invocation
- anomaly/degradation processing
- Supabase Broadcast publication

`_process_reading()` is the shared telemetry processing function. fileciteturn168file0

## 9. Machine scope helper

The device router's `_get_scoped_machine()` verifies organization ownership and, for technicians, assignment. This pattern should be reused rather than replaced by client-side filtering. fileciteturn168file0

## 10. ML layers

The backend separates:

- deterministic maintenance/safety logic
- online behaviour learning
- degradation evidence
- temporal windows/labels
- supervised artifacts
- optional pretrained temporal inference
- optional Gemini maintenance assistance

These layers must not be collapsed into a generic "AI score".

## 11. Notifications

`notification_service.py` persists an in-app notification and then performs best-effort FCM delivery. Push failures do not break the main operation. fileciteturn171file0

## 12. Realtime

`supabase_realtime.py` is the server-side Broadcast publisher. It uses the Supabase secret key and publishes private topics. fileciteturn156file0

## 13. Router responsibilities

| Router | Responsibility |
|---|---|
| `auth.py` | identity/session/auth bridge |
| `machines.py` | machine CRUD/archive/restore |
| `maintenance.py` | maintenance lifecycle |
| `work_orders.py` | maintenance work workflow |
| `faults.py` | fault records/outcomes |
| `alerts.py` | alerts |
| `devices.py` | IoT + telemetry + realtime |
| `analytics.py` | model status, predictions, training/analysis |
| `ai_assistant.py` | diagnostic assistant |
| `reports.py` | reports/exports |
| `audit_log.py` | audit history |
| `notifications.py` | worker notification/device operations |
| `users.py` | user/application access/admin operations |

## 14. Backend rules for new endpoints

Every new route must answer:

1. Who is authenticated?
2. What organization owns the resource?
3. Is application access required?
4. If technician, is the machine assigned?
5. Is archive state relevant?
6. Is the mutation idempotent?
7. Does the action require audit logging?
8. Does it produce a notification?
9. Does it produce realtime data?
10. Does it touch ML evidence?
11. What regression test proves isolation?

## 15. Error semantics

Use authorization errors consistently. Do not expose cross-tenant existence through overly specific responses when a 404/denied response is the intended isolation boundary.

## 16. What not to do

- do not read the database from frontend/mobile
- do not trust client organization IDs
- do not make technician permissions client-side
- do not put Supabase secret credentials in client code
- do not publish unscoped realtime telemetry
- do not turn an ML evidence score into a probability without calibration
