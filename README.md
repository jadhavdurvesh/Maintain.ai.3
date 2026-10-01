<div align="center">

# ⚙️ MAINTAIN AI

<p>
  <a href="https://deepwiki.com/jadhavdurvesh/Maintain.ai.3"><img src="https://devin.ai/assets/askdeepwiki.png" alt="Ask DeepWiki" height="34"></a>
  <a href="https://deepwiki.com/jadhavdurvesh/Maintain.ai.3"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki" height="34"></a>
</p>

<p>
  <img src="https://img.shields.io/badge/React-UI-61DAFB?style=flat-square&logo=react&logoColor=white" alt="React">
  <img src="https://img.shields.io/badge/Vite-Build-646CFF?style=flat-square&logo=vite&logoColor=white" alt="Vite">
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Python-3.x-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white" alt="SQLAlchemy">
  <img src="https://img.shields.io/badge/scikit--learn-ML-F7931E?style=flat-square&logo=scikitlearn&logoColor=white" alt="scikit-learn">
  <img src="https://img.shields.io/badge/Electron-Desktop-47848F?style=flat-square&logo=electron&logoColor=white" alt="Electron">
  <img src="https://img.shields.io/badge/ESP32-IoT-E7352C?style=flat-square&logo=espressif&logoColor=white" alt="ESP32">
  <img src="https://img.shields.io/badge/SQLite-Database-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite">
</p>

<p><strong>AI-powered predictive maintenance and intelligent maintenance management platform.</strong></p>

<p>Monitor assets · Predict machine health · Diagnose faults · Manage maintenance · Analyze reliability · Integrate IoT</p>

</div>

---

## What is MAINTAIN AI?

**MAINTAIN AI** is a predictive-maintenance and maintenance-management platform designed to help industrial teams monitor assets, identify developing problems, manage maintenance operations, and make better decisions from machine data.

The platform combines a traditional rule-based diagnostic engine, live telemetry anomaly detection, an optional pretrained time-series foundation model, a locally trained machine-learning baseline, and an optional AI maintenance assistant. The pretrained temporal layer currently runs TimeRadar in zero-shot anomaly-detection mode; calibrated future failure risk is kept separate until MAINTAIN AI has sufficient point-in-time telemetry and technician-confirmed outcomes. It can operate through a browser or as an installable desktop application, while optional ESP32/IoT integration provides a path from manual machine records to live sensor data.

```text
                         MAINTAIN AI
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
      WEB CLIENT         DESKTOP CLIENT       IoT DEVICES
      React + Vite          Electron          ESP32 + Sensors
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ▼
                       FASTAPI BACKEND
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
          Database         AI / ML          REST API
             │                │                │
     PostgreSQL / Neon   Predictions       Platform Data
       + local SQLite
```

## ✨ Core Capabilities

### 📊 Fleet & Machine Management

- Machine and asset profiles
- Component information
- Operating-hour tracking
- Manual sensor readings
- Fault history
- Maintenance history
- Machine health information
- Archive-based machine removal that preserves historical records
- Specialized machine workspaces for machine types with domain-specific engineering data

### 🏭 Specialized Machine Engineering

Machine categories can use isolated detail workspaces instead of forcing every machine through one generic screen. The current implementation includes a specialized **3D printer** profile with dedicated machine-detail routing and machine-specific runtime signals.

Automatic runtime inference for specialized machines can use live telemetry signals to determine operating state. The 3D-printer implementation is wired into this inference path so its specialized workspace can reflect live machine activity.

### 🧠 Predictive Maintenance

MAINTAIN AI uses accumulated machine data to identify machines whose health is declining faster than their usage pattern would suggest.

The local predictive model uses information such as:

- Operating hours
- Fault history
- Completed maintenance
- Historical machine data

The model is based on a lightweight **scikit-learn Random Forest** and can be retrained from within the application. Predictions are surfaced through the dashboard and analytics views.

The temporal forecasting layer also records forecast runs and status/history information. Automatic forecast work triggered by telemetry is throttled to avoid repeatedly launching expensive forecast jobs for the same stream.

### 🤖 AI Maintenance Assistant

The maintenance assistant is designed around diagnostic reasoning rather than immediately producing a single unsupported answer.

It can:

- Ask clarifying questions before forming a diagnosis
- Separate causes into **confirmed**, **likely**, **possible**, and **insufficient information**
- Provide step-by-step inspection procedures
- Present a safety notice before inspection guidance
- Operate offline by default
- Use Gemini as an optional enhancement
- Log diagnostic sessions for later comparison between predictions and actual outcomes

### 🚨 Smart Alerts & Safety Pipeline

The alert system combines maintenance and machine-health signals to surface issues such as:

- Low health scores
- Overdue maintenance
- Maintenance approaching its due date
- Repeated unresolved faults
- Sensor anomalies from connected devices
- Component-level telemetry conditions

Component telemetry is routed through the established safety-processing pipeline so readings can participate in safety policy evaluation, anomaly/degradation processing, alerts, realtime publication, and the existing device-command/automatic-shutdown path where configured.

### 🔧 Work Order Management

Maintenance work can be tracked through a structured workflow:

```text
Pending ──────► In Progress ──────► Completed
                                      │
                                      ▼
                              Maintenance History
```

Work orders can contain machine associations, descriptions, priority, assignment, status, recommended actions, and completion information.

### 📡 IoT, Component Telemetry & ESP32 Integration

Optional device integration allows ESP32-based devices and other gateways to send readings to MAINTAIN AI through authenticated device-ingestion APIs.

```text
ESP32 / Gateway + Sensor
          │
          │ Device Key
          ▼
 /api/devices/ingest
          │
          ├──────────────► Component telemetry
          │                    │
          ▼                    ▼
    Machine reading      Safety / anomaly pipeline
          │                    │
          └────────────┬───────┘
                       ▼
                 Realtime / Alerts
                       │
                       ▼
                MAINTAIN AI UI
```

Component sensors now have dedicated configuration and reading paths, including sensor metadata, units, configured limits, enabled state, and readings. Device-originated component telemetry supports an event identifier so retries can be handled idempotently rather than creating duplicate readings.

A working example is included in `firmware/esp32_example.ino`, using an **ESP32 + DHT22** and documenting how the example can be adapted for other sensor types such as vibration or current sensors.

The anomaly system compares incoming readings against the machine's recent baseline instead of relying only on a universal fixed threshold.

### 📡 Live Telemetry Controls & Resilience

Live telemetry can be explicitly enabled or disabled for supported machine flows. The application includes resilient realtime handling with fallback polling paths so specialized machine pages can continue reflecting current telemetry when the primary realtime stream is unavailable.

Telemetry-driven runtime state is also used by specialized machine views, including recognition of active robot/3D-printer telemetry where supported.

### 🧪 Machine Simulator Compatibility

The telemetry ingestion path supports external simulator clients. Cross-origin configuration has been hardened for the deployed machine simulator so browser-based simulator telemetry can reach the backend without bypassing the normal ingestion path.

### 📈 Analytics & Reports

The platform provides maintenance and reliability analysis through dashboards and reports, including:

- Fleet health visualization
- Machine health trends
- Reliability analysis
- Failure-cause breakdowns
- Predictive health information
- Model status
- Forecast history/status
- Charts and data summaries
- CSV export
- PDF export
- Excel export

### 🧾 Audit Trail & History

MAINTAIN AI maintains an append-only activity history for important maintenance events, including machine creation, completed work orders, completed maintenance jobs, and resolved alerts.

Historical records remain associated with machines even when a machine is archived from active lists.

### 👥 Authentication & Multi-Tenancy

Authentication can be enabled with:

```text
REQUIRE_AUTH=true
```

Authenticated organizations can register and receive a JWT-based session. Organization-scoped resources include machines, work orders, maintenance records, alerts, and the main dashboard/reliability reporting paths.

The platform also stores user roles including:

- Admin
- Technician
- Viewer

## 🧩 Three-Layer Intelligence

MAINTAIN AI combines three distinct approaches to maintenance intelligence:

```text
                 MAINTAIN AI INTELLIGENCE
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
 Rule-Based Diagnostics  Local ML Model   Optional Gemini
        │                  │                  │
    Fault logic       Random Forest       AI Assistant
    Deterministic      Predictions         Reasoning
    diagnostics       from machine data   & guidance
```

This separation allows deterministic maintenance logic, data-driven prediction, and optional generative assistance to operate as distinct layers rather than treating every maintenance question as a generic AI prompt.

## 🛡️ Telemetry Integrity & Safety

The telemetry architecture now treats component readings as first-class data while preserving the existing machine telemetry pipeline.

```text
Component Sensor
      │
      ▼
Validated Reading
      │
      ├── event identity / idempotency
      ├── configured min/max validation
      ├── safety policy evaluation
      ├── anomaly / degradation processing
      ├── realtime publication
      └── device command / shutdown path
```

This keeps component-level sensor data aligned with the same safety and operational behavior used by the established device telemetry path.

## 🖥️ Web & Desktop Applications

The same application can be used as a browser-based web application or packaged as a desktop application.

```text
                 MAINTAIN AI APPLICATION
                           │
                ┌──────────┴──────────┐
                ▼                     ▼
          Web Application       Desktop Application
          React + Vite              Electron
                │                     │
                └──────────┬──────────┘
                           ▼
                    FastAPI Backend
                           │
                    SQLAlchemy ORM
                           │
                  PostgreSQL / Neon
                           │
                 Local desktop SQLite
```

The desktop package combines the frontend with the backend into an installable application. Desktop build and packaging details are documented separately in [`DESKTOP.md`](DESKTOP.md).

## 🔐 Security Verification

The deployed MAINTAIN AI website at **`maintain-ai-3.vercel.app`** received an **A grade** in an ImmuniWeb Website Security Test dated **September 11, 2026**.

<p align="center">
  <a href="https://www.immuniweb.com/websec/maintain-ai-3.vercel.app/3zbllKpI/">
    <img src="https://img.shields.io/badge/ImmuniWeb-Website%20Security%20Test%20%E2%80%94%20Grade%20A-4CAF50?style=for-the-badge&logo=security&logoColor=white" alt="ImmuniWeb Website Security Test Grade A">
  </a>
</p>

**[Verify the security test results →](https://www.immuniweb.com/websec/maintain-ai-3.vercel.app/3zbllKpI/)**

The original certificate identifies the tested target, test date, Grade A result, and independent verification page.

## 🏗️ System Architecture

```text
┌──────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                             │
│                                                                  │
│ React + Vite Web     Electron Desktop      Android / Workforce  │
│                                                                  │
│                         ESP32 / Gateway                         │
└──────────────────────────────┬───────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                         FASTAPI BACKEND                          │
│                                                                  │
│ REST API · Auth · Business Logic · Analytics · Maintenance      │
│ Alerts · Devices · Component Sensors · Reports · AI Services   │
│                                                                  │
│          Live telemetry · Safety · Idempotency pipeline          │
└──────────────────────────────┬───────────────────────────────────┘
                               │
             ┌─────────────────┼─────────────────┐
             ▼                 ▼                 ▼
      ┌──────────────┐  ┌──────────────┐  ┌───────────────┐
      │ PostgreSQL   │  │ ML / Temporal│  │ Safety /      │
      │ / Neon       │  │ Models       │  │ Diagnostics   │
      │              │  │              │  │               │
      └──────────────┘  └──────────────┘  └───────────────┘
             │                 │                 │
             └─────────────────┼─────────────────┘
                               ▼
                       AI Maintenance
                          Assistant

              Desktop / local operation may use SQLite
```

## 📚 Project Documentation

### Ecosystem knowledge base

- [`docs/README.md`](docs/README.md) — documentation hub and source hierarchy.
- [`docs/ECOSYSTEM_ARCHITECTURE.md`](docs/ECOSYSTEM_ARCHITECTURE.md) — complete cross-platform architecture.
- [`docs/AUTHENTICATION_AND_IDENTITY.md`](docs/AUTHENTICATION_AND_IDENTITY.md) — Supabase Auth, roles, application access, JWT/realtime/device identity.
- [`docs/DATA_AND_SERVICE_MAP.md`](docs/DATA_AND_SERVICE_MAP.md) — data ownership and what gets data from where.
- [`docs/CLIENTS_AND_GATEWAYS.md`](docs/CLIENTS_AND_GATEWAYS.md) — web, Android, Workforce, IoT Gateway and local intelligence contracts.
- [`docs/BACKEND_CODE_GUIDE.md`](docs/BACKEND_CODE_GUIDE.md) — backend code responsibilities and request lifecycle.
- [`docs/FRONTEND_CODE_GUIDE.md`](docs/FRONTEND_CODE_GUIDE.md) — React/Vite code and realtime/auth flow.
- [`docs/MOBILE_AND_GATEWAY_CONTRACTS.md`](docs/MOBILE_AND_GATEWAY_CONTRACTS.md) — Android, Workforce and gateway implementation contracts.
- [`docs/CROSS_CLIENT_ARCHITECTURE_AUDIT.md`](docs/CROSS_CLIENT_ARCHITECTURE_AUDIT.md) — cross-client security audit and acceptance tests.
- [`docs/MAINTAIN_AI_SOURCE_OF_TRUTH.md`](docs/MAINTAIN_AI_SOURCE_OF_TRUTH.md) — architectural invariants and security constitution.

### Product/implementation documents

- [`docs/FEATURES_AND_ARCHITECTURE.md`](docs/FEATURES_AND_ARCHITECTURE.md) — major features and intelligence architecture.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — implementation roadmap and ML direction.
- [`PRODUCT_ARCHITECTURE.md`](PRODUCT_ARCHITECTURE.md) — product architecture.
- [`SETUP.md`](SETUP.md) — development setup/troubleshooting.
- [`DESKTOP.md`](DESKTOP.md) — desktop packaging/runtime.

These documents deliberately distinguish implemented code, externally configured services, and planned/experimental work.

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React |
| Frontend Build | Vite |
| Backend | FastAPI |
| Backend Language | Python |
| ORM | SQLAlchemy |
| Hosted Database | PostgreSQL / Neon |
| Local Database | SQLite |
| Authentication | Supabase Auth + backend authorization |
| Realtime | Supabase Realtime + WebSocket + resilient fallback polling |
| Machine Learning | scikit-learn / temporal model integrations |
| Forecast Processing | Persisted forecast runs with telemetry-trigger throttling |
| Safety | Safety policy pipeline + device command path |
| Component Telemetry | Sensor configuration + validated/idempotent device readings |
| Desktop Runtime | Electron |
| IoT | ESP32 / serial gateway |
| Mobile | Android + Flutter Workforce |
| Push Notifications | Firebase Cloud Messaging |
| Optional AI | Gemini |

## 📁 Project Structure

```text
Maintain.ai.3/
├── backend/                    # FastAPI + SQLAlchemy backend
│   ├── app/                    # Application, models, routers and services
│   └── requirements.txt
├── frontend/                   # React + Vite application
├── desktop/                    # Electron desktop wrapper
├── firmware/                   # IoT firmware examples
├── scripts/                    # Utility/simulation scripts
├── supabase/                   # Supabase project SQL/policies
├── training/                   # ML training/experiments
├── docs/                       # Ecosystem + component documentation
└── .github/workflows/          # CI/build workflows
```

## 🚀 Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
python3 -m app.seed_data
python3 -m uvicorn app.main:app --reload
```

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Then open:

```text
http://localhost:5173
```

For the complete setup procedure and troubleshooting, see [`SETUP.md`](SETUP.md) and [`docs/README.md`](docs/README.md).

---

<div align="center">

**MAINTAIN AI** · Predictive Maintenance · Intelligent Operations

</div>
