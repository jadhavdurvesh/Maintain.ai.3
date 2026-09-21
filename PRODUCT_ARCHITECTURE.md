# Maintain.ai 3 — Product & Architecture Blueprint

## 1. Product purpose
Maintain.ai is an industrial predictive-maintenance platform.

The core job is:
machine sensor data -> live telemetry -> behavioural/fault detection -> alerts/evidence -> maintenance/work order -> technician outcome -> learning evidence

The product is not a generic ERP, CRM, chat app, or IoT dashboard. New implementation work must support the maintenance intelligence workflow first.

## 2. Client applications
### Engineering Control Center
Web application for administrators and engineering users.
Required: organization setup; machine/asset registration; IoT configuration; live telemetry; fault log; alerts; maintenance; work orders; reports/history; AI/model lab; invitations, roles, application access, machine assignments.

### Maintain.ai Android
Authenticated mobile operations client for assigned/visible machines, live telemetry, condition/fault information, alerts, operational actions, and offline-tolerant UX where practical.

### Workforce Client
Technician client for authenticated organization access, assigned machines, live telemetry, assigned work orders, acknowledgement/resolution, outcome evidence, and notifications.

## 3. Backend architecture
- FastAPI + SQLAlchemy
- PostgreSQL in hosted production
- Supabase Auth for identity
- Supabase Realtime for live client delivery
- Vercel currently hosts the web/backend deployment
- IoT Gateway sends authenticated sensor readings to the backend

Authorization source of truth: Maintain.ai organization/user records. Supabase identity authenticates the user. Never trust organization IDs supplied by clients.

## 4. Tenant isolation — non-negotiable
Every organization-owned resource must be isolated: machines, sensor readings, components, faults, alerts, maintenance, work orders, safety data, AI conversations/sessions, ML state/artifacts/outcomes, spare parts, audit history, users, application access, invitations, reports/exports, and Realtime telemetry.

A fresh organization starts with zero machines, maintenance, work orders, faults/alerts, history, spare parts, and only its own users/access records.

Never use a global fallback such as organization_id=1 for new authenticated records. Legacy demo/seed data must never leak into a new organization.

## 5. Roles
Admin: organization administration, machines, users/invitations, application access, assignments, IoT, organization AI/settings, maintenance/work orders.
Technician: assigned/allowed machines, assigned work, acknowledge/resolve work, submit fault/maintenance/outcome evidence; no organization administration.
Viewer: read-only visibility according to application and organization rules.
The backend is authoritative for permissions; frontend hiding is only UX.

## 6. Authentication
Email/password, Google OAuth, and Apple OAuth through Supabase Auth.
New organization registration collects organization/company name, username, and full name.

Critical rule: a Supabase identity already linked to a Maintain.ai organization cannot be reused by the New organization flow. It must sign in to its existing organization or use a different identity.

Invitations are organization-scoped and carry role/application context. Never infer organization from email domain alone.

## 7. Live telemetry and fault detection
Normal flow:
sensor -> IoT Gateway -> authenticated backend ingestion -> persistence/online behaviour analysis -> private Realtime broadcast -> Web/Android/Workforce clients

Requirements: no polling-only dependency for immediate fault visibility; private organization-scoped Realtime channels; short-lived backend-issued Realtime JWT; clients do not publish trusted telemetry; authenticated device-key ingestion; gateway retry queue; idempotent event IDs.

## 8. Fault detection / ML
1. ingest sensor reading
2. update machine/signal behavioural state
3. calculate anomaly/degradation evidence
4. persist durable anomaly/safety/fault evidence when thresholds are met
5. surface alert/fault
6. technician performs work
7. technician records outcome
8. outcome becomes training/evaluation evidence

Gemini/LLM features are assistive for explanation, diagnostics, questions/actions, and reports. They are not authoritative for telemetry or tenant authorization.

## 9. Data ownership model
Organization is the top-level tenant.
User has organization_id. Machine has organization_id. Operational entities belong through machine_id -> machine.organization_id or directly through organization_id.

Every endpoint must: authenticate -> resolve current organization -> scope query -> apply role/assignment restrictions -> perform operation.
Never use an unscoped db.get(Model, id) for an organization-owned operation, query globally and filter in React, accept organization_id from the request as authorization, or use global seeded rows for new organizations.

## 10. UI rules
Settings shows organization name, username, and role.
Admin-only controls: members, invitations, application access, machine assignments, organization configuration.
Technicians must not see admin organization controls.
Empty organization behavior is valid: no machines, schedules, history, parts, work orders, alerts, or faults.

## 11. Current priorities
P0 security/tenant correctness: organization creation/linking; every router tenant scope; audit/history; settings/users; spare parts; maintenance; reports/exports; analytics/model lab; devices; application access.
P0 live industrial path: gateway ingestion; durable readings; online anomaly/degradation; private Realtime; Web/Android/Workforce delivery; retry/idempotency; fault/alert propagation.
P1 operational workflow: machine onboarding; IoT setup; maintenance; work orders; technician assignment; fault logging; resolution/outcome feedback.
P1 ML: behavioural baseline; anomaly detection; degradation tracking; failure evidence; training/evaluation; technician feedback.
P2 polish: reports, dashboards, UI refinement, email/notifications, performance, observability.

## 12. Do NOT build yet
Unless explicitly requested, do not add CRM, billing/subscriptions, marketplace, social/community features, generic project management, arbitrary AI agents, unrelated integrations, speculative microservices, unnecessary databases, or complex event infrastructure when the current architecture is sufficient.

Before adding a feature ask: Does it directly improve machine monitoring, fault detection, maintenance execution, technician workflow, ML evidence, or organization security? If not, defer it.

## 13. Tenant-isolation definition of done
Test organization A and B must coexist. B must see none of A's organization-owned data. A must not see B's machine. A technician must only see allowed assigned machines. Organization changes stay inside that organization. A Realtime event for A must never reach B.

## 14. Change discipline
Before implementing: read this blueprint; identify affected entities/endpoints; identify tenant/role boundaries; make the smallest required change; check all clients; verify empty-org behavior; verify A/B isolation; update this document only when architecture actually changes.

This document is the project scope guardrail. It prioritizes the predictive-maintenance workflow and prevents optional feature expansion from distracting implementation.