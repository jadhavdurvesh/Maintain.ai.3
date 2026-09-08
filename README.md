# MAINTAIN AI

*(temporary name — rename anytime, it's just a folder name and a page title)*

AI-powered predictive maintenance & intelligent maintenance management
system. Runs as a web app or as an installable desktop app (same code,
Electron-wrapped), manual data entry for now with the door left open for
real sensors, and an AI diagnostic assistant that works completely offline
with Gemini as an optional enhancement rather than a dependency.

## Quick start (web version)

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt --break-system-packages
python3 -m app.seed_data
python3 -m uvicorn app.main:app --reload

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173. The seed script loads 4 demo machines
(a motor, pump, conveyor, and compressor) so the dashboard isn't empty.
Full walkthrough (including troubleshooting) is in `SETUP.md`.

## Installable desktop app

`desktop/` wraps the same frontend + backend into a real installer
(.exe/.dmg/.AppImage) — no Python or Node required on the end user's
machine. Full build pipeline, the cross-compilation caveat, and where the
Gemini API key actually lives (spoiler: never in the installer) are in
`DESKTOP.md`.

## What's built (V1, functional and tested end to end)

- Visual design: neumorphic panels (soft light/dark shadow pairs, pure CSS,
  no JS cost) combined with a light `backdrop-filter` frosted blur, on the
  sidebar, topbar, and every page panel/stat-tile; light and dark themes
  with a toggle (persisted locally). A prior version used a physically-
  modeled glass library with ray-traced refraction and an animated particle
  background — it looked great but cost real sustained CPU (~28% in
  testing) from continuous particle animation and cursor-tracked
  recalculation. This design gets a similar frosted look for near-zero
  cost at rest. A **"Reduce visual effects" toggle in Settings** drops the
  blur entirely (falls back to solid panels) for hardware where
  `backdrop-filter` isn't hardware-accelerated — verified in testing to
  cut GPU load dramatically on such hardware.
- Dashboard with live health/alert/maintenance tiles and visual charts
  (health-distribution donut, per-machine health bars)
- Machine/asset management: profiles, components, manual sensor readings,
  fault + maintenance history
- Operating-hours-based smart maintenance scheduler
- Work order board (pending → in progress → completed), auto-logs to
  maintenance history on completion
- Smart Alert System (low health score, overdue/due-soon maintenance,
  repeated unresolved faults)
- AI Maintenance Assistant: asks clarifying questions before committing to
  a cause, rates each cause confirmed/likely/possible/insufficient-info,
  gives a step-by-step inspection procedure with a safety notice up front.
  Offline by default; optional Gemini path — key entered once via
  Settings in the app itself, stored in the local database. Every session
  is logged so predicted-vs-actual can be compared later.
- Spare parts inventory with low-stock flagging
- Reports: reliability, failure-cause breakdown, with charts and
  CSV/PDF/Excel export
- **Permanent audit trail**: every machine added, work order completed,
  maintenance job finished, and alert resolved is written to an
  append-only log the app itself never edits or deletes — visible on the
  new History page. "Deleting" a machine archives it (hides it from
  active lists) instead of destroying its history.
- **Local predictive model — a third, on-device AI**: a small scikit-learn
  RandomForest (tens of KB, no GPU, predicts in milliseconds) trained on
  your own accumulated machine data — operating hours, fault history,
  completed maintenance — to flag which machines are declining faster
  than their usage pattern would predict. Distinct from both the offline
  rule-based diagnostic engine and the optional Gemini path: this one
  actually trains on data that lives in your own database. Retrain
  anytime from the Reports page; predictions surface on the Dashboard.
- User/role records (admin / technician / viewer)
- **Optional live sensor integration (ESP32/IoT)** — off by default, zero
  impact on manual entry unless explicitly enabled per machine. A paired
  device gets a key (shown once) and pushes readings to `/api/devices/ingest`;
  anomalies are flagged by comparing against that machine's own recent
  baseline (needs a few readings of history first, same "no confident claim
  without enough signal" philosophy as the offline diagnostic engine) rather
  than a fixed threshold. Real working firmware example in
  `firmware/esp32_example.ino` (ESP32 + DHT22, with notes on adapting for
  vibration/current sensors). Verified end to end: paired a device, sent
  baseline readings, sent a spike, confirmed the anomaly alert fired: wrong
  or disabled keys are rejected.
- About page with project credits
- **Installable desktop packaging** (Electron + PyInstaller) — built and
  test-launched end to end, see `DESKTOP.md`

## A real trade-off worth knowing about

The earlier design (physically-accurate glass with ray-traced refraction, a
live particle background, cursor-tracked specular highlights) had a real,
measured cost — ~28% sustained CPU in the renderer process, from continuous
compositor work that never settles. That's been replaced with plain
neumorphic panels + a single `backdrop-filter` blur, which is far cheaper —
but blur itself still isn't free on hardware where it can't be
GPU-accelerated (older machines, some VMs, remote desktop sessions without
GPU passthrough). In that scenario the blur compositing can genuinely spike
GPU usage. The **"Reduce visual effects" toggle in Settings** exists exactly
for this — verified in testing to drop GPU load dramatically when enabled,
falling back to solid panels with the same neumorphic shadow depth. If this
runs on shop-floor hardware you haven't tested, worth checking early.

## Auth &amp; multi-tenancy

Off by default — set `REQUIRE_AUTH=true` on the backend to turn it on.
When off (local/desktop mode, unchanged from before this existed): no
login, single company, works exactly as it always has.

When on: companies register at `/api/auth/register` (creates an
Organization + its first admin user), sign in at `/api/auth/login`, and
get a JWT. Verified end to end with two separately-registered companies:
each only ever sees its own machines, work orders, maintenance records,
alerts, and dashboard totals — confirmed both via the list endpoints and
by directly requesting another company's record by ID (a clean 404, not a
403, so it doesn't even confirm the ID exists). Cross-company writes are
blocked the same way.

**Scoped so far**: machines, work orders, maintenance, alerts, and the
main dashboard/reliability reports.
**Not yet scoped** (still global, not filtered by company, if you turn
auth on): spare parts, AI diagnostic sessions, the predictive model, audit
log, failure-analysis/export reports, and device/IoT pairing. Same
pattern as the ones already done — join to `Machine` and filter by
`organization_id` — just not done yet.
**Not enforced yet**: roles (admin/technician/viewer) are stored per user
but don't yet restrict what an authenticated user can do.

**"Online database"**: SQLAlchemy already abstracts the SQL dialect, so
pointing `DATABASE_URL` at a hosted Postgres instance (Render, Railway,
Supabase all have free/cheap tiers) instead of local SQLite needs no code
changes — install `psycopg2-binary` (already in requirements.txt) and
change the URL. I wasn't able to test against a live Postgres server in
this sandbox (none available), so this specific path is a confident
"should work, standard SQLAlchemy usage" rather than something I've
directly verified end to end the way the SQLite path is.

## What's next (not built yet)

- Finishing organization-scoping on the routers listed above
- Role-based permission enforcement (not just role labels)
- Windows/Mac installers specifically — the pipeline is built and
  tested on Linux; producing the actual `.exe`/`.dmg` needs a build run on
  those OSes (see the cross-compilation note in `DESKTOP.md`)
- Android app — noted for later, not started: a separate, notifications
  + dashboard-only companion app, distinct from the main desktop/web app

## Repo layout

```
maintain-ai/
  backend/     FastAPI + SQLAlchemy — see backend/README.md
  frontend/    React + Vite — see frontend/README.md
  desktop/     Electron wrapper — see DESKTOP.md
```
