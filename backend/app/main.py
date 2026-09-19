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
        ensure_user_work_order_schema()
        ensure_lab_ml_schema()
        ensure_bootstrap_organization()
    except Exception:
        pass

# Lightweight compatibility migrations for existing SQLite/Postgres databases.
def ensure_ai_conversation_schema():
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("ai_diagnostic_sessions")}
    if "conversation_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE ai_diagnostic_sessions ADD COLUMN conversation_id INTEGER"))


def ensure_user_work_order_schema():
    inspector = inspect(engine)

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "active" not in user_columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE users ADD COLUMN active BOOLEAN DEFAULT TRUE"))
            connection.execute(text("UPDATE users SET active = TRUE WHERE active IS NULL"))

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
# cannot take down the entire Vercel ASGI function. This is particularly
# important for the serverless deployment where the ML/notification stack
# can differ from the desktop runtime.
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
        # Keep authentication and the ASGI app available. A failing optional
        # router can be diagnosed independently without causing FUNCTION_INVOCATION_FAILED.
        continue


@app.get("/")
def root():
    return {"status": "ok", "service": "MAINTAIN AI backend"}
