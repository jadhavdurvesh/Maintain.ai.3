# Frontend Code Guide

## 1. Runtime

The web client is React + Vite. It communicates with FastAPI over HTTP and uses Supabase Realtime for live telemetry.

## 2. Authentication

`frontend/src/AuthContext.jsx` is the session orchestrator.

It:

- loads auth status
- restores Supabase sessions
- synchronizes identity with the backend
- loads `/api/auth/me`
- manages organization context
- handles registration/onboarding
- handles confirmation state
- logs out and clears client state

fileciteturn158file0

## 3. Supabase Auth transport

`frontend/src/supabaseAuth.js` implements the browser-side Supabase Auth HTTP contract without making the browser responsible for Maintain authorization.

It supports:

- password login
- signup
- email confirmation resend
- refresh tokens
- sign-out
- Google/Apple PKCE
- callback processing
- state/verifier validation

fileciteturn159file0

## 4. REST client

`frontend/src/api/client.js` is the shared HTTP transport.

It adds:

`Authorization: Bearer <token>`

and:

`X-Maintain-Application: engineering`

It also handles GET caching, in-flight request coalescing, timeout, 401 invalidation and cache clearing after mutations. fileciteturn160file0

## 5. Realtime

`frontend/src/realtime.js` creates a Supabase WebSocket connection.

The sequence is:

```text
organization context
 -> WebSocket connect
 -> POST /api/auth/realtime-token
 -> receive scoped Realtime JWT
 -> join private topic
 -> heartbeat
 -> receive telemetry broadcast
 -> reconnect if disconnected
```

fileciteturn157file0

## 6. Machine context

Machine pages should own machine-specific operational data. Global pages should operate over the visible fleet.

The source-of-truth architecture distinguishes:

- Machine Detail
- Maintenance
- Work Orders
- Fault Log
- Alerts
- Reports
- Audit History
- Model Lab

Do not silently duplicate machine-detail semantics in global pages.

## 7. API data flow

```text
React component
 -> page hook/state
 -> api client
 -> FastAPI route
 -> backend authorization
 -> JSON response
 -> React state
 -> rendered UI
```

## 8. Live telemetry flow

```text
Gateway/device
 -> FastAPI ingest
 -> Neon persistence + ML processing
 -> Supabase Broadcast
 -> frontend realtime.js
 -> CustomEvent
 -> subscribed machine UI
```

The database remains the historical source; realtime is delivery transport.

## 9. Desktop mode

The shared API client detects the Electron bridge (`window.maintainAI`) and can resolve the desktop backend URL from it. This lets the same frontend operate as a browser client or packaged desktop client. fileciteturn160file0

## 10. Client-side security rule

Frontend state is not authorization.

A disabled button improves UX, but the backend must still reject the operation for an unauthorized identity.

## 11. Debugging order

When a page shows wrong data:

1. inspect the network request
2. inspect `X-Maintain-Application`
3. inspect Bearer token presence
4. inspect backend `/api/auth/me`
5. inspect organization/machine scope
6. inspect database result
7. only then inspect React state/rendering

When live data is missing:

1. verify organization context
2. verify `/api/auth/realtime-token`
3. verify Supabase WebSocket connection
4. verify private topic join
5. verify backend Broadcast publication
6. verify Supabase RLS
7. verify UI event subscription

## 12. Do not

- fetch Neon directly
- put Supabase secret key in Vite env
- trust `organization_id` from localStorage for authorization
- use local machine filters as security
- open duplicate realtime sockets per machine detail page when the shared stream already exists
