import importlib
import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models
from .bootstrap import ensure_bootstrap_organization
from .database import Base, engine
from .routers import auth

# Database initialization is deliberately best-effort at import time.
# Vercel/serverless must be able to import FastAPI even if an old database
# needs a separate migration. API requests can then report the real DB error.
def _initialize_database():
    try:
        Base.metadata.create_all(bind=engine)
        ensure_ai_conversation_schema()
        ensure_user_auth_schema()
        ensure_user_work_order_schema()
        ensure_lab_ml_schema()
        ensure_tenant_schema()
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
    columns = {column["name"] for column in inspector.get_columns("work_orders")}
    if "fault_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE work_orders ADD COLUMN fault_id INTEGER"))


def ensure_lab_ml_schema():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass



def ensure_tenant_schema():
    """Add tenant ownership to legacy shared tables without destroying existing data.
    Existing rows are assigned to the bootstrap organization; new rows are scoped
    explicitly by the authenticated organization.
    """
    inspector = inspect(engine)
    additions = []
    if inspector.has_table("spare_parts"):
        columns = {column["name"] for column in inspector.get_columns("spare_parts")}
        if "organization_id" not in columns:
            additions.append(("spare_parts", "organization_id", "INTEGER"))
    if inspector.has_table("ml_model_artifacts"):
        columns = {column["name"] for column in inspector.get_columns("ml_model_artifacts")}
        if "organization_id" not in columns:
            additions.append(("ml_model_artifacts", "organization_id", "INTEGER"))
    if inspector.has_table("audit_log"):
        columns = {column["name"] for column in inspector.get_columns("audit_log")}
        if "organization_id" not in columns:
            additions.append(("audit_log", "organization_id", "INTEGER"))
    if inspector.has_table("sensor_readings"):
        columns = {column["name"] for column in inspector.get_columns("sensor_readings")}
        if "external_id" not in columns:
            additions.append(("sensor_readings", "external_id", "VARCHAR"))
    if not additions:
        return
    with engine.begin() as connection:
        for table, column, sql_type in additions:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
            connection.execute(text(f"UPDATE {table} SET {column} = 1 WHERE {column} IS NULL"))
    Base.metadata.create_all(bind=engine)

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

# Authentication is mandatory and must never be hidden by an optional-router
# import failure.
app.include_router(auth.router)

# Feature routers are isolated. A single optional dependency/import problem
# must not crash the Vercel Python function and take authentication down with it.
_ROUTER_NAMES = (
    "machines",
    "maintenance",
    "work_orders",
    "alerts",
    "faults",
    "notifications",
    "spare_parts",
    "ai_assistant",
    "reports",
    "users",
    "settings",
    "audit_log",
    "analytics",
    "devices",
)

_ROUTER_LOAD_ERRORS = {}

for _router_name in _ROUTER_NAMES:
    try:
        _module = importlib.import_module(f"{__package__}.routers.{_router_name}")
        app.include_router(_module.router)
    except Exception as _exc:
        _ROUTER_LOAD_ERRORS[_router_name] = f"{type(_exc).__name__}: {_exc}"


@app.get("/")
def root():
    return {"status": "ok", "service": "MAINTAIN AI backend"}



@app.get("/api/system/router-status")
def router_status():
    return {
        "loaded": [name for name in _ROUTER_NAMES if name not in _ROUTER_LOAD_ERRORS],
        "failed": _ROUTER_LOAD_ERRORS,
    }
