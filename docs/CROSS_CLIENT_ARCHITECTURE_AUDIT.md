# Cross-Client Architecture Audit

Date: 2026-09-21
Scope:
- Maintain.ai backend/web architecture on `main`
- `Maintain.ai.android`
- `Maintain.ai-workforce-client`
- `MAINTAIN-AI-IoT-Gateway`

## Target architecture

```text
Supabase Auth
     |
     v
Maintain.ai identity
     |
     v
Organization -> User -> Role -> Application access -> Machine assignment
     |
     +--> Web engineering client
     +--> Android client
     +--> Workforce technician client
     |
     +--> Machine
            |
            +--> IoT device key
            |      |
            |      v
            |   Gateway / firmware
            |      |
            |      v
            |   /api/devices/ingest
            |
            +--> Telemetry
            +--> Faults / Alerts
            +--> Maintenance / Work Orders
            +--> ML evidence
            +--> Realtime
```

Neon/Postgres remains the system of record. Supabase is used for identity and Realtime delivery. The backend is the authorization authority.

## Audit result

The three external clients are now being aligned to the same backend contract rather than maintaining independent authorization models.

### Android

Current integration:
- Supabase password authentication.
- Maintain.ai `/api/auth/supabase/sync`.
- Maintain.ai `/api/auth/me`.
- Maintain.ai analytics and machine APIs.
- Supabase Realtime through a short-lived backend-issued token.
- Backend-authorized machine list.

Corrections made:
- configurable `MAINTAIN_API_URL`
- session validation now targets Maintain.ai backend
- Realtime uses the configured backend
- Realtime subscribes to machine-scoped topics
- release builds no longer permit cleartext traffic
- debug builds retain local HTTP support
- client architecture contract documented

### Workforce

Current integration:
- Supabase authentication.
- Maintain.ai sync/me.
- assigned machine list.
- work-order status operations.
- fault reporting.
- machine components/readings.
- Firebase notification registration.
- Supabase Realtime.

Corrections made:
- centralized configuration
- explicit workforce application context
- notification calls carry workforce application context
- Realtime subscribes to backend-authorized machine topics
- stale README/security claims corrected
- client architecture contract documented

### IoT Gateway

Current integration:
- serial device input
- local validation
- OS credential-store device keys
- HTTPS telemetry ingestion
- SQLite offline queue
- event-id retry deduplication

Corrections made:
- connectivity test no longer creates fake telemetry
- new backend `/api/devices/ping` validates device key without mutating telemetry/ML state
- endpoint remains configurable
- device contract documented

## Backend findings

### Fixed in this integration branch

1. Realtime JWT now carries the active machine IDs visible to the authenticated user.
2. Telemetry is published to machine-scoped Realtime topics in addition to the engineering organization topic.
3. Supabase RLS distinguishes engineering organization topics from Android/workforce machine topics.
4. Android/workforce machine subscriptions are authorized by JWT machine IDs, not client-side filtering.
5. Missing organization membership on a Supabase-linked identity is rejected instead of silently falling back to organization 1.
6. Authentication is required by default; local unauthenticated behavior must now be explicitly configured for development.
7. Machine ORM ownership no longer has an implicit `organization_id=1` default.
8. Demo seed machines explicitly use the bootstrap organization.
9. IoT connectivity checks are non-mutating.

### Existing architecture already verified

- tenant-scoped machine lookup
- technician machine assignment enforcement
- organization-scoped work orders
- technician work-order assignment enforcement
- fault assignment enforcement
- maintenance idempotency
- work-order completion idempotency
- ML artifact organization scope
- backend-issued Realtime tokens
- server-side native WebSocket machine allow-list
- application access for engineering/android/workforce
- archived machine restore path
- audit and ML evidence machine scoping

## Remaining risks

### 1. Native process-local WebSocket state

`/api/devices/stream` maintains process-local connected clients. It is protected by organization and technician machine scope, but multi-instance deployment requires an external fan-out layer or Supabase-only delivery.

### 2. IoT command WebSocket state

The safety shutdown command path uses a process-local device WebSocket map. It is suitable for the current single-process development topology but must use a durable/reliable device command channel before multi-instance production.

### 3. Supabase SQL must be applied

The repository contains the corrected Realtime RLS policy, but repository code alone does not apply SQL to the Supabase project. The policy must be executed in the actual Supabase project and then tested with:
- engineering user
- Android user
- assigned technician
- unassigned technician
- second organization

### 4. Formal database migrations

Startup schema repair remains compatibility-oriented. It should eventually be replaced by versioned migrations.

### 5. ML production status

The advanced model remains tenant-scoped and wired, but the existing health-score/random-forest and bootstrap temporal models must not be presented as calibrated future-failure probabilities.

## Required end-to-end acceptance tests

1. Create organization A and organization B.
2. Create machines in both organizations.
3. Create technician A and assign only machine A1.
4. Sign in through Android as technician A.
5. Verify only A1 is returned.
6. Verify Android cannot read B1 by changing a URL machine ID.
7. Connect an IoT Gateway to A1 and ingest telemetry.
8. Verify Android receives A1 telemetry.
9. Verify Android does not receive A2 telemetry.
10. Verify Android does not receive B1 telemetry.
11. Create a work order for A1.
12. Verify technician A can transition it only through the allowed states.
13. Complete it with resolution notes.
14. Verify exactly one maintenance record and one ML outcome are created.
15. Repeat completion and verify no duplicate side effect.
16. Report a fault from Workforce for A1.
17. Verify the fault notification targets the assigned worker.
18. Verify B organization never receives A telemetry, notifications, faults, or work orders.
19. Archive A1 and verify operational clients stop seeing it.
20. Restore A1 as admin and verify it becomes visible again.

## Definition of compatibility

A client is compatible only when:
- it uses the shared authentication contract
- it identifies its application explicitly
- it never decides authorization locally
- it receives only backend-authorized machine data
- it uses the canonical telemetry/event contract
- it respects ML semantics from the backend
- it handles reconnects
- it does not introduce a second tenant model
