<div align="center">

# ⚙️ MAINTAIN AI

<p>
  <a href="https://deepwiki.com/jadhavdurvesh/Maintain.ai.3"><img src="https://devin.ai/assets/askdeepwiki.png" alt="Ask DeepWiki" height="34"></a>
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

<p>
  Monitor assets · Predict machine health · Diagnose faults · Manage maintenance · Analyze reliability · Integrate IoT
</p>

</div>

---

## What is MAINTAIN AI?

**MAINTAIN AI** is a predictive-maintenance and maintenance-management platform designed to help industrial teams monitor assets, identify developing problems, manage maintenance operations, and make better decisions from machine data.

The platform combines a traditional rule-based diagnostic engine, a locally trained machine-learning model, and an optional AI maintenance assistant. It can operate through a browser or as an installable desktop application, while optional ESP32/IoT integration provides a path from manual machine records to live sensor data.

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
           SQLite        Predictions       Platform Data
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

### 🧠 Predictive Maintenance

MAINTAIN AI uses accumulated machine data to identify machines whose health is declining faster than their usage pattern would suggest.

The local predictive model uses information such as:

- Operating hours
- Fault history
- Completed maintenance
- Historical machine data

The model is based on a lightweight **scikit-learn Random Forest** and can be retrained from within the application. Predictions are surfaced through the dashboard and analytics views.

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

### 🚨 Smart Alerts

The alert system combines maintenance and machine-health signals to surface issues such as:

- Low health scores
- Overdue maintenance
- Maintenance approaching its due date
- Repeated unresolved faults
- Sensor anomalies from connected devices

### 🔧 Work Order Management

Maintenance work can be tracked through a structured workflow:

```text
Pending ──────► In Progress ──────► Completed
                                      │
                                      ▼
                              Maintenance History
```

Work orders can contain machine associations, descriptions, priority, assignment, status, recommended actions, and completion information.

### 📡 IoT & ESP32 Integration

Optional device integration allows an ESP32-based device to send readings to MAINTAIN AI through the device-ingestion API.

```text
ESP32 + Sensor
      │
      │ Device Key
      ▼
/api/devices/ingest
      │
      ▼
Machine Baseline
      │
      ▼
Anomaly Detection
      │
      ▼
Maintenance Alert
      │
      ▼
MAINTAIN AI Dashboard
```

A working example is included in `firmware/esp32_example.ino`, using an **ESP32 + DHT22** and documenting how the example can be adapted for other sensor types such as vibration or current sensors.

The anomaly system compares incoming readings against the machine's recent baseline instead of relying only on a universal fixed threshold.

### 📈 Analytics & Reports

The platform provides maintenance and reliability analysis through dashboards and reports, including:

- Fleet health visualization
- Machine health trends
- Reliability analysis
- Failure-cause breakdowns
- Predictive health information
- Model status
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
                      SQLAlchemy
                           │
                        SQLite
```

The desktop package combines the frontend with the backend into an installable application. Desktop build and packaging details are documented separately in [`DESKTOP.md`](DESKTOP.md).

## 🔐 Security Verification

The deployed MAINTAIN AI website at **`maintain-ai-3.vercel.app`** received an **A grade** in an ImmuniWeb Website Security Test dated **September 11, 2026**. fileciteturn19file0L2-L8

<p align="center">
  <a href="https://www.immuniweb.com/websec/maintain-ai-3.vercel.app/3zbllKpI/">
    <img src="https://img.shields.io/badge/ImmuniWeb-Website%20Security%20Test%20%E2%80%94%20Grade%20A-4CAF50?style=for-the-badge&logo=security&logoColor=white" alt="ImmuniWeb Website Security Test Grade A">
  </a>
</p>

**[Verify the security test results →](https://www.immuniweb.com/websec/maintain-ai-3.vercel.app/3zbllKpI/)**

The original certificate identifies the tested target, test date, Grade A result, and independent verification page. fileciteturn19file0L3-L10

## 🏗️ System Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                       CLIENT LAYER                           │
│                                                              │
│   React + Vite Web        Electron Desktop       ESP32 IoT   │
└───────────────┬──────────────────┬──────────────────┬───────┘
                │                  │                  │
                └──────────────────┼──────────────────┘
                                   ▼
┌──────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                         │
│                                                              │
│  REST API · Authentication · Business Logic · Analytics     │
│  Maintenance · Alerts · Devices · Reports · AI Services     │
└──────────────────────────────┬───────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌────────────┐   ┌────────────┐   ┌──────────────┐
        │   SQLite   │   │ ML Model   │   │ Diagnostics  │
        │  Database  │   │  Random    │   │ Rule Engine  │
        │            │   │  Forest    │   │              │
        └────────────┘   └────────────┘   └──────────────┘
                               │
                               ▼
                        AI Maintenance
                           Assistant
```

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React |
| Frontend Build | Vite |
| Backend | FastAPI |
| Backend Language | Python |
| ORM | SQLAlchemy |
| Database | SQLite |
| Machine Learning | scikit-learn / Random Forest |
| Desktop Runtime | Electron |
| Desktop Packaging | PyInstaller + Electron tooling |
| IoT | ESP32 |
| Example Sensor | DHT22 |
| API | REST |

## 📁 Project Structure

```text
Maintain.ai.3/
├── backend/                    # FastAPI + SQLAlchemy backend
│   ├── app/                    # Application, models, routers and services
│   └── requirements.txt
│
├── frontend/                   # React + Vite application
│   ├── src/
│   │   ├── api/                # API client
│   │   ├── components/          # Shared UI components
│   │   └── pages/               # Application screens
│   └── package.json
│
├── desktop/                    # Electron desktop wrapper
├── firmware/                   # IoT firmware examples
│   └── esp32_example.ino
├── scripts/                    # Utility and simulation scripts
├── .github/workflows/           # Project build workflows
├── SETUP.md                    # Detailed setup guide
├── DESKTOP.md                  # Desktop packaging guide
└── README.md
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

The seed process provides four demonstration machines — a motor, pump, conveyor, and compressor — so the dashboard can be explored immediately.

For the complete setup procedure and troubleshooting, see [`SETUP.md`](SETUP.md).

## 🖥️ Desktop Build

The desktop application packages the MAINTAIN AI frontend and backend into an installable application using Electron and PyInstaller.

Supported package targets include:

- Windows `.exe`
- macOS `.dmg`
- Linux `.AppImage`

For the complete desktop build process and packaging details, see [`DESKTOP.md`](DESKTOP.md).

## 🔌 Backend Configuration

The backend uses SQLAlchemy for database access, allowing the application to work with SQLite locally and providing a database abstraction suitable for other SQL backends.

The default development configuration uses SQLite. Database configuration is controlled through the backend environment settings.

## 📚 Documentation

| Document | Description |
|---|---|
| [`SETUP.md`](SETUP.md) | Full development setup and troubleshooting |
| [`DESKTOP.md`](DESKTOP.md) | Desktop packaging and build instructions |
| `backend/` | FastAPI backend implementation |
| `frontend/` | React/Vite frontend implementation |
| `firmware/` | ESP32/IoT integration example |

---

<div align="center">

**MAINTAIN AI** · Predictive Maintenance · Intelligent Operations

</div>
