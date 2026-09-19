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
# needs a separate migration. API requests can then report the real DB error
# instead of failing the entire function invocation.
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

# Lightweight compatibility migrations for existing SQLite/Postgres databases.
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

    # UserApplicationAccess is created by SQLAlchemy when it is missing.
    # Keep this separate from the ALTER statements so legacy databases can
    # receive the new auth column without needing a destructive migration.
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

# Authentication is a hard dependency for the hosted app.
app.include_router(auth.router)

# Optional feature routers are isolated so one optional dependency/import
# cannot take down the entire Vercel ASGI function.
_OPTIONAL_ROUTERS = (
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

for _router_name in _OPTIONAL_ROUTERS:
    try:
        _module = importlib.import_module(f"{__package__}.routers.{_router_name}")
        app.include_router(_module.router)
    except Exception:
        continue


@app.get("/")
def root():
    return {"status": "ok", "service": "MAINTAIN AI backend"}
