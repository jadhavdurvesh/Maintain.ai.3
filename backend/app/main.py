import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models
from .bootstrap import ensure_bootstrap_organization
from .database import Base, engine
from .routers import (
    auth,
    machines,
    maintenance,
    work_orders,
    alerts,
    faults,
    spare_parts,
    reports,
    users,
    settings,
    audit_log,
    devices,
)

# Database initialization is deliberately best-effort at import time.
# Vercel/serverless must be able to import FastAPI even if an old database
# needs a separate migration.
def _initialize_database():
    try:
        Base.metadata.create_all(bind=engine)
        ensure_ai_conversation_schema()
        ensure_user_auth_schema()
        ensure_user_work_order_schema()
        ensure_lab_ml_schema()
        ensure_bootstrap_organization()
    except Exception:
        pass


def ensure_ai_conversation_schema():
    inspector = inspect(engine)
    if not inspector.has_table("ai_diagnostic_sessions"):
        return
    columns = {column["name"] for column in inspector.get_columns("ai_diagnostic_sessions")}
    if "conversation_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE ai_diagnostic_sessions ADD COLUMN conversation_id INTEGER"))


def ensure_user_auth_schema():
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    additions = []

    if "supabase_user_id" not in user_columns:
        additions.append("ALTER TABLE users ADD COLUMN supabase_user_id VARCHAR")
    if "active" not in user_columns:
        additions.append("ALTER TABLE users ADD COLUMN active BOOLEAN DEFAULT TRUE")

    if additions:
        with engine.begin() as connection:
            for statement in additions:
                connection.execute(text(statement))
            if "active" not in user_columns:
                connection.execute(text("UPDATE users SET active = TRUE WHERE active IS NULL"))

    Base.metadata.create_all(bind=engine)


def ensure_user_work_order_schema():
    inspector = inspect(engine)
    if not inspector.has_table("work_orders"):
        return
    work_order_columns = {column["name"] for column in inspector.get_columns("work_orders")}
    if "fault_id" not in work_order_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE work_orders ADD COLUMN fault_id INTEGER"))


def ensure_lab_ml_schema():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass


_initialize_database()

if os.getenv("SEED_DEMO_DATA", "").lower() == "true":
    try:
        from .seed_data import seed
        seed()
    except Exception:
        pass

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

# Core application routers are required and are loaded explicitly. Previously
# these were imported through a broad try/except loop, which could silently
# remove a router and turn valid API calls into unexplained 404 responses.
app.include_router(auth.router)
app.include_router(machines.router)
app.include_router(maintenance.router)
app.include_router(work_orders.router)
app.include_router(alerts.router)
app.include_router(faults.router)
app.include_router(spare_parts.router)
app.include_router(reports.router)
app.include_router(users.router)
app.include_router(settings.router)
app.include_router(audit_log.router)
app.include_router(devices.router)

# Heavy/optional services are isolated so an unavailable ML dependency does not
# prevent the core maintenance API and dashboard from starting.
try:
    from .routers import analytics
    app.include_router(analytics.router)
except Exception:
    pass

try:
    from .routers import ai_assistant
    app.include_router(ai_assistant.router)
except Exception:
    pass

try:
    from .routers import notifications
    app.include_router(notifications.router)
except Exception:
    pass


@app.get("/")
def root():
    return {"status": "ok", "service": "MAINTAIN AI backend"}
