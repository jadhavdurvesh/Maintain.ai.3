# Maintain.ai 3 — Architecture, Audit & Implementation Source of Truth

Status: **Lab branch architecture baseline**
Branch: `Lab`
Purpose: prevent architectural drift while Maintain.ai 3 is being hardened and the Advanced Maintain AI work is implemented.

This document is the working constitution for the product. When a new feature conflicts with this document, update the document deliberately before changing the architecture.

---

## 1. Product boundary

Maintain.ai is an industrial maintenance-management and predictive-maintenance platform.

The core relationship is:

`Organization → User → Machine → Telemetry / Faults / Alerts / Maintenance / Work Orders → Technician outcome → ML evidence`

The platform has three important security boundaries:

1. **Organization boundary** — no tenant can read or mutate another tenant's data.
2. **Machine-assignment boundary** — technicians can only operate on machines assigned to them.
3. **Application boundary** — engineering, Android, and workforce access are explicit application permissions.

The backend is authoritative. Frontend visibility is UX only.

---

## 2. Global invariants

### Tenant isolation

Every tenant-owned resource must resolve to an organization through a trusted path.

Preferred paths:

- direct `organization_id`
- `machine_id → machines.organization_id`
- `user_id → users.organization_id`
- `work_order_id → machine_id → organization_id`
- `maintenance_id → machine_id → organization_id`
- ML evidence → machine → organization

Never use a user-supplied organization ID as the authorization decision.

New records must use the authenticated organization. Do not introduce new hard-coded `organization_id=1` behavior.

### Technician isolation

A technician sees only:

- assigned, active machines
- resources attached to those machines
- work orders they are authorized to act on
- notifications targeted to them or their assigned machines
- realtime telemetry for assigned machines

A client-side `machine_id` filter is never sufficient authorization.

### Application access

Authenticated identity flow is:

`Identity → Maintain user → Organization → Application access → Role → Machine assignment → Resource`

Application access is checked for Supabase identities and legacy JWT identities. Legacy password accounts are backfilled into the engineering application.

### Archived machines

Archived machines are excluded from normal operational visibility.

Archive preserves history.

Restore must be able to locate archived machines and re-enable them.

---

## 3. UI information architecture

### Machine context

A machine page owns machine-specific operational context:

- Overview
- Telemetry
- Faults
- Maintenance history
- Work orders
- Safety
- AI diagnosis
- Intelligence
  - behaviour
  - degradation
  - forecasts
  - advanced model evidence

### Global context

Global pages operate across the visible fleet:

- Maintenance
- Work Orders
- Fault Log
- Alerts
- Reports
- History / Audit
- Model Lab

A global page must not silently become a second machine-detail page.

### History terminology

Keep these concepts separate:

- **Audit History** — who changed what and when.
- **Maintenance History** — maintenance records for a machine.
- **ML Evidence** — telemetry-derived anomaly/degradation/model evidence.

---

## 4. Backend authorization rules

### Machines

- Admin: create/update/archive/restore.
- Technician: read assigned active machines.
- Viewer: read visible organization machines.
- Cross-organization access: 404/denied.

### Maintenance

- Admin: schedule and complete.
- Technician: see assigned machine maintenance and perform only the explicitly permitted technician actions.
- Viewer: read only.
- Completion is idempotent.

### Work orders

- Admin: create and manage.
- Technician: act only on assigned work orders and use the allowed status progression.
- Viewer: read only.
- Completion is idempotent.
- Completion actor is the authenticated user.

### Audit

Audit list and count use the same visibility boundary.

### Reports/exports

All datasets are built from the current visible machine set, with direct organization scoping for organization-level datasets.

### IoT

Device keys identify a single machine.

A device key is never accepted as an organization-wide credential.

### Realtime

Native telemetry fanout is partitioned by organization and, for technicians, by assigned machine IDs.

The server filters events before delivery.

---

## 5. Realtime architecture

There are two realtime concerns:

### Native application WebSocket

`/api/devices/stream`

Authentication:

1. validate token
2. resolve Maintain user
3. validate application access
4. resolve organization
5. if technician, resolve assigned active machine IDs
6. subscribe connection with that machine allow-list
7. publish only events whose machine ID is allowed

Organization-only fanout is insufficient for technician access.

### Supabase broadcast

Supabase broadcast uses two scopes:

- Engineering: `org:<organization_id>:telemetry`
- Android/workforce: `machine:<machine_id>:telemetry`

The short-lived Realtime token carries:

- Supabase subject
- Maintain user ID
- organization ID
- application
- authorized active machine IDs
- short expiry

Supabase RLS must enforce the application scope and machine IDs. Mobile clients must never rely on client-side filtering as the authorization boundary.

---

## 6. Machine archive semantics

Normal machine helper:

- organization scoped
- active machine only
- technician assignment checked

Restore helper:

- admin only
- organization scoped
- intentionally includes archived machines

Repeated restore is harmless.

---

## 7. Maintenance and work-order correctness

### Maintenance completion

Completion must:

- verify organization
- verify technician assignment when applicable
- reject archived/missing machines
- set completion time once
- record the authenticated actor
- adjust machine health once
- produce one completion audit event

Repeating the same completion request must not repeatedly increase health.

### Work-order completion

Completion must:

- require the required resolution information
- transition through valid statuses
- capture technician outcome once
- create the linked maintenance record once
- create outcome feedback once
- be safe against repeated completion requests

---

## 8. ML architecture

ML is evidence-driven and machine-scoped.

### Layer A — live telemetry

Sensor readings are stored with:

- machine
- reading type
- value
- unit
- source
- timestamp
- optional external event ID

### Layer B — online behaviour learning

Per machine/signal state tracks:

- sample count
- mean
- variance
- EWMA
- last value
- anomaly score

This is operational evidence, not a failure probability.

### Layer C — degradation evidence

Degradation snapshots combine multi-signal evidence and trends.

The UI must not call degradation score a calibrated failure probability.

### Layer D — temporal windows and labels

Telemetry windows are point-in-time.

Future labels must only use outcomes that occur after the window.

No future leakage.

### Layer E — supervised advanced model

The advanced model is stored as a tenant-scoped artifact.

Required artifact metadata:

- organization
- model type/version
- training sample count
- positive count
- metrics
- training timestamp
- serialized artifact
- active flag

Inference must resolve the artifact through the machine's organization.

### Layer F — horizon risk

24h / 48h / 7d / 30d risk must not be displayed as calibrated probabilities until:

1. enough leakage-safe labels exist
2. horizon-specific models are trained
3. holdout evaluation is performed
4. calibration is validated
5. false-positive/false-negative behavior is measured
6. production thresholds are versioned

---

## 9. Existing ML models: terminology rules

The existing Random Forest baseline uses machine health-score targets. It is therefore a **health/baseline model**, not a future-failure probability model.

The temporal bootstrap model is a representation/bootstrap model and is not a production-calibrated industrial failure predictor.

The online behaviour and degradation systems are evidence layers.

The advanced supervised artifact is the intended path for trained failure-risk inference once valid labels and evaluation exist.

Never silently turn a heuristic score into a probability.

---

## 10. Audit findings and resolutions

### P0 — technician realtime isolation
**Finding:** organization-level native telemetry fanout previously allowed a technician connection to receive organization events; the frontend filtered by machine.

**Resolution:** server-side machine allow-list filtering was added to the native telemetry stream.

### P0 — legacy JWT application boundary
**Finding:** Supabase identities had explicit application access, but the legacy JWT path did not.

**Resolution:** engineering application access is now required for legacy authenticated users; legacy password accounts are backfilled.

### P0 — audit count mismatch
**Finding:** technician audit list was machine scoped but audit count was organization wide.

**Resolution:** count now uses the same machine-derived visibility scope as the list.

### P0 — archive restore
**Finding:** the normal active-machine helper could not reach archived records for restore.

**Resolution:** restore uses a dedicated organization-scoped archived-inclusive helper.

### P0 — advanced artifact model mismatch
**Finding:** `advanced.py` referenced `MLAdvancedArtifact` without a corresponding model/table.

**Resolution:** tenant-scoped `MLAdvancedArtifact` storage was added and analytics now exposes scoped advanced-model status and machine risk inference.

### P1 — maintenance completion repeatability
**Finding:** repeated completion could repeatedly mutate health and audit state.

**Resolution:** completion is idempotent and records the authenticated actor.

### P1 — work-order completion repeatability
**Finding:** an already-completed work order could be processed again through permissive update paths.

**Resolution:** repeated completion requests return the completed record without creating a second completion side effect.

### P1 — CORS hardening
**Finding:** CORS was globally permissive.

**Resolution:** origins and allowed headers/methods are configuration-driven.

### P1 — router diagnostic exposure
**Finding:** router-load diagnostics were publicly reachable.

**Resolution:** router status requires an authenticated administrator.

### P1 — CI coverage
**Finding:** CI compiled/imported the application but did not exercise tenant/assignment invariants.

**Resolution:** architecture regression tests were added and CI now runs them.

### P1 — reports import correctness
**Finding:** reports referenced `HTTPException` without importing it.

**Resolution:** import corrected.

---

## 11. Regression tests

Minimum required security/correctness tests:

- organization A cannot read organization B machine
- organization A cannot read organization B maintenance
- organization A cannot read organization B history
- technician cannot read unassigned machine
- technician cannot receive unassigned telemetry
- viewer cannot mutate machine
- viewer cannot complete maintenance
- new organization starts empty
- archived machine can be restored
- repeated maintenance completion is idempotent
- repeated work-order completion is idempotent
- AI session is machine scoped
- ML artifact is organization scoped
- realtime channel is organization scoped
- technician realtime is assignment scoped

The Lab branch now contains baseline regression tests for technician machine visibility, archive visibility/restore lookup, and advanced artifact tenant scope. Expand the endpoint-level suite before production release.

---

## 12. Database migration discipline

Current startup schema repair is intentionally compatibility-oriented, but it is not a replacement for a formal migration system.

Rules:

- startup repair may create missing compatibility columns/tables
- migration failures must not be silently treated as successful production migrations
- new schema changes should be represented in a durable migration history
- tenant backfills must have explicit ownership assumptions
- never assign new tenant data to organization 1 as a shortcut

Future hardening phase: move compatibility DDL into versioned migrations and make deployment fail loudly when required migrations are missing.

---

## 13. Startup and operational hardening

Required production settings:

- `REQUIRE_AUTH=true`
- explicit `CORS_ORIGINS`
- Supabase signing/Realtime secrets configured only server-side
- device keys treated as secrets
- router status restricted to admins
- CI must fail if an expected router cannot import

Avoid swallowing database initialization errors without an operational signal. Compatibility startup must remain observable.

---

## 14. Phased implementation plan

### Phase 0 — Constitution
- keep this document current
- treat `PRODUCT_ARCHITECTURE.md` and `docs/FEATURES_AND_ARCHITECTURE.md` as product architecture references
- review every new feature against the invariants above

### Phase 1 — Isolation and security
- tenant scope every resource
- technician assignment scope every machine resource
- application access before role/resource access
- assignment-aware realtime
- same visibility logic for counts and lists
- device/safety authorization
- export/report scope
- endpoint authorization matrix
- endpoint-level regression suite

### Phase 2 — Machine / maintenance / history boundaries
- machine page owns machine context
- global maintenance owns fleet maintenance
- history is audit history
- ML evidence is surfaced in Model Lab / Intelligence
- remove duplicated semantics from pages

### Phase 3 — Correctness
- idempotent completion
- actor attribution
- archive/restore
- transaction boundaries
- audit coverage
- notification correctness
- duplicate telemetry event handling

### Phase 4 — Advanced Maintain AI
- collect leakage-safe telemetry windows
- derive future outcome labels
- validate class balance
- train horizon-specific models
- hold out machines/time periods
- evaluate precision/recall, PR-AUC, calibration, false alarms
- version artifacts
- scope artifacts by organization
- expose evidence + uncertainty
- only then expose calibrated horizon probabilities

### Phase 5 — Production validation
- integration authorization tests
- realtime authorization tests
- migration tests
- API contract tests
- frontend build
- backend compile/import
- CI regression suite
- production CORS/auth configuration
- operational logging and error visibility
- final architecture review

---

## 15. Endpoint review checklist

For every new endpoint ask:

1. Who is the identity?
2. Which organization owns the resource?
3. Is the resource archived?
4. If technician, is the machine assigned?
5. Does the operation require admin?
6. Is application access enforced?
7. Can the same ID be guessed across tenants?
8. Does the endpoint return counts/aggregates that leak hidden rows?
9. Does realtime filter server-side?
10. Does export use the same visible machine set?
11. Does ML query through a trusted machine scope?
12. Is the mutation idempotent?
13. Is the actor recorded?
14. Is the event audited?
15. Are tests added?

---

## 16. Do-not-drift rules

Do not:

- add organization-wide technician access because it is easier
- rely on frontend filtering for authorization
- use organization 1 for new records
- call heuristic health/anomaly/degradation scores probabilities
- expose archived machines in operational pages
- mix audit history with maintenance history
- let a model artifact load without tenant scope
- add a second competing authorization path
- silently swallow a failed production migration
- add unrelated features while an isolation/security invariant is broken

---

## 17. Definition of done for a feature

A feature is not complete until:

- backend authorization is implemented
- tenant and machine scope are verified
- UI hides actions the role cannot perform
- mutation is safe on retry
- audit/event behavior is defined
- ML evidence is properly labeled
- tests cover the security boundary
- CI runs the test
- documentation is updated

This is the source-of-truth contract for future Maintain.ai 3 work.


## 18. Additional hardening findings

### Notification tenant consistency
Machine-to-worker notification fanout now verifies that the assigned user and machine belong to the same organization. This protects against malformed or legacy cross-tenant assignment rows.

### Notification authentication
Notification endpoints now use the application-aware current-user dependency so Supabase identities are supported consistently and application access remains enforced.

### User directory privacy
The organization member directory is administrator-only. A technician or viewer can inspect only their own assignment surface where the endpoint permits it.

### AI key settings
Reading Gemini key configuration status is administrator-only. The secret value itself remains organization-scoped in the settings store.

### Work-order → maintenance linkage
Completed work orders create a maintenance record with a unique `source_work_order_id`. This makes the side effect retry-safe and provides an explicit provenance link.

### Frontend authorization UX
Machine-detail write controls and safety-policy controls are hidden for non-admin users. Global maintenance scheduling remains admin-only, while maintenance completion remains available to administrators and technicians because the backend permits assigned technicians to complete their maintenance records.

---

## 19. Known limitations that must not be mistaken for completed work

These are deliberately documented instead of being hidden behind optimistic UI:

1. The advanced supervised model is **wired and tenant-scoped**, but an active production artifact still requires leakage-safe training data and validated training.
2. The current temporal bootstrap representation is not a calibrated industrial failure model.
3. The Random Forest baseline remains a health/baseline model.
4. Startup schema repair remains compatibility-oriented rather than a full versioned migration system.
5. CI regression coverage is now present, but the complete endpoint/realtime matrix still needs to be expanded to cover every router.
6. Supabase Realtime authorization policies must remain synchronized with the server-issued tenant claims and organization topic conventions.
7. Production deployment must set `REQUIRE_AUTH=true` and explicit `CORS_ORIGINS`.

The correct behavior for an unavailable or unvalidated model is to expose its state as unavailable/not calibrated, not to fabricate a probability.
