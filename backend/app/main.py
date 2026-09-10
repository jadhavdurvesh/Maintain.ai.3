import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models
from .bootstrap import ensure_bootstrap_organization
from .database import Base, engine
from .routers import machines, maintenance, work_orders, alerts, spare_parts, ai_assistant, reports, users, settings, audit_log, analytics, devices, auth, faults

Base.metadata.create_all(bind=engine)

# Lightweight compatibility migrations for existing SQLite/Postgres databases.
def ensure_compatibility_schema():
    inspector = inspect(engine)
    work_order_columns = {column["name"] for column in inspector.get_columns("work_orders")}
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    with engine.begin() as connection:
        if "fault_id" not in work_order_columns:
            connection.execute(text("ALTER TABLE work_orders ADD COLUMN fault_id INTEGER"))
        if "active" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN active BOOLEAN NOT NULL DEFAULT 1"))
        # Older seeded/local users predate organization scoping. Keep them in
        # the bootstrap organization so the new Settings user list and
        # work-order assignee validation continue to see them.
        connection.execute(text("UPDATE users SET organization_id = 1 WHERE organization_id IS NULL"))


def ensure_ai_conversation_schema():
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("ai_diagnostic_sessions")}
    if "conversation_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE ai_diagnostic_sessions ADD COLUMN conversation_id INTEGER"))


ensure_compatibility_schema()
ensure_ai_conversation_schema()
ensure_bootstrap_organization()

if os.getenv("SEED_DEMO_DATA", "").lower() == "true":
    from .seed_data import seed
    seed()

app = FastAPI(
    title="MAINTAIN AI",
    description="AI-powered predictive maintenance & intelligent maintenance management system",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(machines.router)
app.include_router(maintenance.router)
app.include_router(work_orders.router)
app.include_router(alerts.router)
app.include_router(faults.router)
app.include_router(spare_parts.router)
app.include_router(ai_assistant.router)
app.include_router(reports.router)
app.include_router(users.router)
app.include_router(settings.router)
app.include_router(audit_log.router)
app.include_router(analytics.router)
app.include_router(devices.router)


@app.get("/")
def root():
    return {"status": "ok", "service": "MAINTAIN AI backend"}
