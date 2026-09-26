# MAINTAIN AI 3 Documentation

This directory is the engineering knowledge base for the whole MAINTAIN AI ecosystem.

## Read first

1. **[ECOSYSTEM_ARCHITECTURE.md](ECOSYSTEM_ARCHITECTURE.md)** — how every platform, repository and external service connects.
2. **[MAINTAIN_AI_SOURCE_OF_TRUTH.md](MAINTAIN_AI_SOURCE_OF_TRUTH.md)** — security, authorization, data boundaries, ML semantics and architectural invariants.
3. **[DATA_AND_SERVICE_MAP.md](DATA_AND_SERVICE_MAP.md)** — what gets data from where and which code/service owns each operation.
4. **[AUTHENTICATION_AND_IDENTITY.md](AUTHENTICATION_AND_IDENTITY.md)** — Supabase Auth, Maintain users, roles, application access, JWT compatibility, Realtime tokens and device identity.
5. **[CLIENTS_AND_GATEWAYS.md](CLIENTS_AND_GATEWAYS.md)** — Web, Android, Workforce and IoT Gateway contracts.
6. **[CROSS_CLIENT_ARCHITECTURE_AUDIT.md](CROSS_CLIENT_ARCHITECTURE_AUDIT.md)** — cross-client security audit and acceptance matrix.
7. **[FEATURES_AND_ARCHITECTURE.md](FEATURES_AND_ARCHITECTURE.md)** — product features and intelligence architecture.
8. **[ROADMAP.md](ROADMAP.md)** — future implementation direction.

## Existing supporting documents

- `PRODUCT_ARCHITECTURE.md` — product-level architecture
- `SETUP.md` — development/setup guide
- `DESKTOP.md` — desktop packaging and runtime
- `SUPABASE_REALTIME_RLS.sql` — Realtime authorization policy source

## Documentation rule

Documentation must distinguish three states:

- **Implemented** — confirmed in source code.
- **Configured externally** — depends on a cloud/project setting that is not stored in Git.
- **Planned/experimental** — intended or tested but not production-complete.

Do not turn a planned architecture into a statement that it is already implemented.

## Ecosystem repositories

- Main platform: `jadhavdurvesh/Maintain.ai.3`
- Android: `jadhavdurvesh/Maintain.ai.android`
- Workforce: `jadhavdurvesh/Maintain.ai-workforce-client`
- IoT Gateway: `jadhavdurvesh/MAINTAIN-AI-IoT-Gateway`
- Local Intelligence: `jadhavdurvesh/MAINTAIN-AI-Local-Intelligence`
- Sensor Simulator: `jadhavdurvesh/MAINTAIN-AI-Sensor-Simulator`

## External services

| Service | Role |
|---|---|
| Supabase Auth | identity/authentication |
| Supabase Realtime | private realtime transport |
| Neon/Postgres | hosted application system of record |
| Vercel | hosted web/backend deployment target described by the repository |
| Firebase Cloud Messaging | mobile push notifications |
| Gemini | optional AI assistant enhancement |
| Resend | possible external email/SMTP provider behind Supabase; no direct Resend client is currently present in the repository |

## Contract change rule

A shared contract change is incomplete until the main backend, affected clients/gateways, tests, and documentation are updated together.
