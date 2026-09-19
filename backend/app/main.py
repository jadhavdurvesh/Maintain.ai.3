import importlib
import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from . import models
from .bootstrap import ensure_bootstrap_organization
from .database import Base, engine
from .routers import auth
from . import schemas
from .database import get_db
from .deps import CurrentUser, get_current_user

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



# If the full Machines router cannot import because of an optional dependency,
# keep the core list endpoint available so the application does not degrade to
# a misleading 404. The normal router remains authoritative when it loads.
if "machines" in _ROUTER_LOAD_ERRORS:
    _machines_fallback = APIRouter(prefix="/api/machines", tags=["machines-fallback"])

    @_machines_fallback.get("", response_model=list[schemas.MachineOut])
    def fallback_list_machines(
        current: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return (
            db.query(models.Machine)
            .filter(
                models.Machine.organization_id == current.organization_id,
                models.Machine.archived.is_(False),
            )
            .order_by(models.Machine.name.asc())
            .all()
        )

    app.include_router(_machines_fallback)


@app.get("/api/system/router-status")
def router_status():
    return {
        "loaded": [name for name in _ROUTER_NAMES if name not in _ROUTER_LOAD_ERRORS],
        "failed": _ROUTER_LOAD_ERRORS,
    }
