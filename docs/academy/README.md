# MAINTAIN AI User & Operations Academy

The **MAINTAIN AI User & Operations Academy** is the planned training system for people who operate the MAINTAIN AI ecosystem. It is **not developer documentation**. Its purpose is to teach users how to operate the applications, machines, sensors, gateway, DeviceOS, maintenance workflows, predictive features, alerts, and safety functions.

## Purpose

The Academy should allow a new user to progress from basic MAINTAIN AI understanding to role-specific operational competence through lessons, guided procedures, screenshots, practical exercises, simulations, assessments, and completion records.

## Scope

The Academy covers the user-facing MAINTAIN AI ecosystem currently represented by these systems:

- **MAINTAIN AI 3** — primary industrial maintenance-intelligence/application platform.
- **MAINTAIN AI Android** — native mobile operations client for fleet monitoring, alerts, predictive analytics, work orders and reports.
- **Industrial Workforce Client** — cross-platform worker/technician client for assigned machines, work orders and alerts.
- **MAINTAIN AI IoT Gateway** — desktop connectivity layer between serial industrial devices/controllers and the MAINTAIN AI backend.
- **MAINTAIN AI DeviceOS** — standalone device provisioning, firmware generation, compilation/upload, verification and machine-edge configuration application.
- **MAINTAIN AI Sensor Simulator** — browser/cloud simulator used to exercise telemetry workflows without physical hardware.
- **Physical machine + sensors + edge boards** — the operational layer that produces machine telemetry.

The Academy should explain the relationship between these systems without teaching their source code.

## Core Learning Model

```text
                    MAINTAIN AI ACADEMY
                           │
             ┌─────────────┴─────────────┐
             │                           │
          LEARN                       PRACTICE
             │                           │
      lessons / media             real application
      procedures / concepts       guided exercises
             │                           │
             └─────────────┬─────────────┘
                           ▼
                       ASSESS
                           │
                 knowledge + practical
                           │
                           ▼
                       COMPLETE
                           │
                           ▼
                     CERTIFICATION
```

## Role Paths

All learners begin with a common foundation. After the foundation, the Academy branches into role-specific paths.

### Common Foundation

1. Welcome to MAINTAIN AI
2. Understanding the MAINTAIN AI ecosystem
3. Machines, components and assets
4. Sensors and telemetry
5. Machine health and condition
6. Alerts and notifications
7. Maintenance and work orders
8. Predictive maintenance and AI
9. Safety fundamentals

### Technician

- Assigned machines
- Machine condition review
- Alerts
- Work orders
- Inspection workflow
- Maintenance execution
- Resolution notes
- Component replacement records
- Android operations
- Workforce operations
- Sensor/telemetry troubleshooting
- Safety procedures
- Practical technician scenarios

### Maintenance Manager

- Fleet dashboard
- Fleet health
- Maintenance workload
- Work-order oversight
- Reliability and analytics
- Predictive insights
- Reports
- Escalations
- Team/workforce visibility
- Operational scenarios

### Administrator

- Organization setup
- Users and roles
- Machine records
- Machine assignments
- Operational configuration
- Device and sensor associations
- Alerts and notifications
- Access/authorization concepts
- Administration scenarios

### IoT Operator

- Machine-to-device relationship
- Sensors and parameters
- Edge boards
- DeviceOS workflow
- Pin/wiring instructions
- Firmware generation and upload
- Gateway workflow
- Device identity
- Telemetry verification
- Simulator-based testing
- Hardware troubleshooting
- Safe device commissioning

### Workforce Operator

- Workforce application
- Assigned-machine view
- Work-order acknowledgement
- Work-order resolution
- Alerts
- Machine information
- Operational refresh/fallback behavior
- Technician scenarios

## Course Structure

### 00 — Welcome to MAINTAIN AI

- What MAINTAIN AI is
- What predictive maintenance means
- Who uses the ecosystem
- What each application is for
- The difference between application, device, gateway and machine layers

### 01 — The MAINTAIN AI Ecosystem

- MAINTAIN AI 3
- Android client
- Workforce client
- IoT Gateway
- DeviceOS
- Sensor Simulator
- Machines and sensors
- End-to-end information flow

### 02 — MAINTAIN AI Web Application

- Sign in
- Dashboard
- Machines
- Machine details
- Components
- Machine health
- Alerts
- Maintenance
- Work orders
- Analytics
- Reports
- AI maintenance assistant
- Settings and account functions

### 03 — Android Operations

- Application access
- Dashboard
- Fleet health
- Machine information
- Alerts and notifications
- Predictive analytics
- Work orders
- Reports
- Server configuration where applicable
- Common connection problems

### 04 — Workforce Operations

- Technician/workforce sign-in
- Assigned machines
- Machine details
- Work-order acknowledgement
- Work-order resolution
- Required resolution information
- Alerts
- Refresh and temporary backend-unavailable behavior

### 05 — Machines & Assets

- Machine lifecycle
- Machine information
- Components
- Operating information
- Machine health
- Fault history
- Maintenance history
- Machine-specific/specialized views

### 06 — Sensors & Telemetry

- What telemetry is
- Sensor parameters
- Temperature
- Humidity
- Vibration
- Current
- Load
- Sensor status
- Normal vs abnormal readings
- Reading history
- Component telemetry

### 07 — DeviceOS & Machine Commissioning

The DeviceOS operational course follows its actual lifecycle:

**Connect → Identify → Configure → Validate → Wire → Generate → Compile → Upload → Verify → Save/Export**

Lessons:

- Connect a board
- Identify the board
- Select the board/version
- Associate a machine/device
- Select parameters
- Configure sensors
- Understand pin assignments
- Follow wiring instructions
- Generate firmware
- Compile
- Upload
- Open serial monitor
- Verify readings
- Save/export the configuration
- Commission the device

The Academy should teach the operator what each step means and how to recognize success/failure, not how to program firmware.

### 08 — IoT Gateway

- Purpose of the gateway
- Connecting a serial device
- Selecting/identifying a port
- Baud rate
- JSON-line telemetry concept
- Machine pairing
- Device-key concept
- Connection status
- Backend status
- Live readings
- Upload status
- Multiple connected devices
- Offline/retry behavior where supported
- Gateway troubleshooting

The gateway is taught as a connectivity layer, not as the main MAINTAIN AI application.

### 09 — Sensor Simulator

- When to use the simulator
- Temperature control
- Humidity control
- Vibration control
- Current control
- Normal/warning/critical presets
- Send interval
- Request log
- Device key handling
- Continuous simulation
- Using simulation to test alerts and telemetry workflows

### 10 — Machine Health & Predictive Maintenance

- Health scores
- Health trends
- Risk information
- Prediction reasoning
- Model status
- Forecast history/status
- Difference between observed telemetry and prediction
- Why predictions are evidence rather than certainty
- How maintenance outcomes become operational evidence

### 11 — Alerts & Notifications

- Alert types
- Severity
- Machine alerts
- Maintenance alerts
- Acknowledgement
- Resolution
- Android notifications
- Workforce alerts
- What to do when an alert appears

### 12 — Maintenance & Work Orders

- Creating/receiving maintenance work
- Priority
- Assignment
- Status lifecycle
- Recommended actions
- Inspection
- Resolution notes
- Completion
- Maintenance history
- Linking maintenance outcomes to machine history

### 13 — AI Maintenance Assistant

- What the assistant does
- Diagnostic reasoning
- Clarifying questions
- Confirmed/likely/possible/insufficient-information distinctions
- Inspection guidance
- Safety notice
- How technicians should use AI assistance
- What the assistant does not replace

### 14 — Machine Safety & Automatic Shutdown

This is a dedicated safety curriculum.

- Safety concepts
- Condition monitoring
- Safety thresholds/policies
- Safety alerts
- Automatic shutdown pathway
- Device command concepts
- What an operator sees
- Immediate response procedure
- Post-shutdown procedure
- Verification before return to service
- Safety scenarios
- Safety assessment

Safety training must clearly distinguish ordinary AI/predictive information from controlled safety intervention.

### 15 — Analytics & Reports

- Fleet analytics
- Machine trends
- Reliability
- Failure causes
- Predictive information
- Model status
- Forecast history
- CSV/PDF/Excel reporting
- Android PDF reports

### 16 — Administration

- Organizations
- Users
- Roles
- Technicians
- Viewers
- Machine assignments
- Device associations
- Notifications
- Operational configuration

### 17 — Troubleshooting

Scenario-based troubleshooting rather than generic technical support.

Initial scenarios:

1. Machine is not showing telemetry.
2. Sensor values are stale.
3. Gateway sees the device but backend does not receive data.
4. DeviceOS upload fails.
5. Wrong sensor/pin configuration.
6. Android cannot reach the backend.
7. Workforce application cannot refresh assigned machines.
8. Alert appears but expected notification is missing.
9. Machine health does not update.
10. Prediction appears but expected history/status is missing.
11. Simulator sends data but the machine does not reflect it.
12. Automatic shutdown/safety event requires investigation.

Every troubleshooting lesson should use:

**Symptom → Checks → Expected observation → Action → Verification → Escalation**

### 18 — Real-World Scenarios

The Academy should contain complete end-to-end exercises, including:

- New machine commissioning
- New sensor commissioning
- Abnormal vibration
- High temperature
- Sensor disconnected
- Scheduled maintenance
- Predictive degradation
- Work-order completion
- Safety intervention
- Fleet review
- New technician onboarding

### 19 — Final Practical Assessment

Learners complete role-specific practical tasks and scenario questions. The assessment should verify that the learner can operate the relevant MAINTAIN AI systems, not merely remember definitions.

## Lesson Template

Every lesson should use a consistent structure:

1. **Objective** — what the learner will be able to do.
2. **Role** — who needs this lesson.
3. **Prerequisites** — required previous lessons/access.
4. **Concept** — short explanation in plain language.
5. **Procedure** — numbered real-world steps.
6. **Visual guide** — current screenshot/diagram where useful.
7. **Expected result** — what success looks like.
8. **Common mistakes** — frequent operator errors.
9. **Safety note** — when applicable.
10. **Practical exercise** — learner performs the task.
11. **Knowledge check** — short questions.
12. **Completion criteria** — what must be true to finish.

## Practical Training Philosophy

The Academy should favor **doing** over passive reading.

A typical lesson should progress:

```text
Understand
   ↓
Observe
   ↓
Follow
   ↓
Perform
   ↓
Verify
   ↓
Explain
```

The final stages should increasingly remove step-by-step assistance so the learner demonstrates independent operation.

## Certification Model

Initial certification families:

- MAINTAIN AI User — Foundation
- MAINTAIN AI Technician — Level 1
- MAINTAIN AI Maintenance Manager — Level 1
- MAINTAIN AI Administrator — Level 1
- MAINTAIN AI Workforce Operator — Level 1
- MAINTAIN AI IoT Operator — Level 1
- MAINTAIN AI Safety Operator — Level 1

Certification names and passing thresholds are provisional until the Academy assessment specification is finalized.

## Academy Application — Planned Product

The Academy itself should be a separate application from MAINTAIN AI 3. The first release should not require deep integration with MAINTAIN AI.

### MVP

- Academy login
- Role selection
- Course catalog
- Lesson viewer
- Progress tracking
- Quizzes
- Practical exercise checklists
- Completion state
- Basic certificate/record

### Later integration

- Deep links into MAINTAIN AI applications
- Practical-task verification through MAINTAIN AI APIs where safe and appropriate
- Organization-specific training assignments
- Administrator training dashboards
- Scenario simulator
- Certificates and renewal
- Version-aware lessons

## Versioning

Because the MAINTAIN AI ecosystem changes frequently, Academy content must be versioned.

Each lesson should identify:

- Academy version
- Applicable application/version
- Last reviewed date
- Role(s)
- Safety relevance
- Whether the workflow is live, simulated, or documentation-only

A major application workflow change should trigger a review of the affected Academy lessons.

## Source of Truth

The Academy must be based on the actual user-facing behavior of the current MAINTAIN AI ecosystem. Repository READMEs, product documentation, current application screens, and verified operational behavior should be used to create lessons. Developer-only implementation details should not be exposed merely because they exist in source code.

Where a feature is planned, experimental, unavailable, or different between applications, the lesson must say so rather than presenting it as an established workflow.

## Next Build Stage

The next stage is **Academy Content Specification**: turn each module above into a lesson-by-lesson inventory with exact learning objectives, practical tasks, assessment questions, required screenshots, and applicable application/version. Only after that inventory is stable should the separate Academy application be implemented.
