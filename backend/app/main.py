import importlib
import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from . import models
from .bootstrap import ensure_bootstrap_organization
from .database import Base, engine
from .routers import auth
from .deps import get_current_user, CurrentUser


def _initialize_database():
    try:
        Base.metadata.create_all(bind=engine)
        ensure_ai_conversation_schema()
        ensure_user_auth_schema()
        ensure_user_work_order_schema()
        ensure_maintenance_work_order_schema()
        ensure_lab_ml_schema()
        ensure_tenant_schema()
        ensure_legacy_application_access_schema()
        ensure_safety_policy_schema()
        ensure_bootstrap_organization()
    except Exception:
        pass


def ensure_safety_policy_schema():
    """Migrate safety policies from one-per-machine to one-per-signal."""
    try:
        inspector = inspect(engine)
        if not inspector.has_table("machine_safety_policies"):
            return
        if engine.dialect.name == "postgresql":
            with engine.begin() as connection:
                connection.execute(text("""
                    DO $body$
                    DECLARE constraint_name TEXT;
                    BEGIN
                        SELECT conname INTO constraint_name
                        FROM pg_constraint
                        WHERE conrelid = 'machine_safety_policies'::regclass
                          AND contype = 'u'
                          AND pg_get_constraintdef(oid) = 'UNIQUE (machine_id)';
                        IF constraint_name IS NOT NULL THEN
                            EXECUTE format('ALTER TABLE machine_safety_policies DROP CONSTRAINT %I', constraint_name);
                        END IF;
                    END $body$;
                """))
                connection.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_machine_safety_policies_machine_id "
                    "ON machine_safety_policies (machine_id)"
                ))
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
    if "password_change_required" not in user_columns:
        additions.append("ALTER TABLE users ADD COLUMN password_change_required BOOLEAN DEFAULT FALSE")
    if additions:
        with engine.begin() as connection:
            for statement in additions:
                connection.execute(text(statement))
            if "active" not in user_columns:
                connection.execute(text("UPDATE users SET active = TRUE WHERE active IS NULL"))
            if "password_change_required" not in user_columns:
                connection.execute(text("UPDATE users SET password_change_required = FALSE WHERE password_change_required IS NULL"))
    Base.metadata.create_all(bind=engine)


def ensure_user_work_order_schema():
    inspector = inspect(engine)
    if not inspector.has_table("work_orders"):
        return
    columns = {column["name"] for column in inspector.get_columns("work_orders")}
    if "fault_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE work_orders ADD COLUMN fault_id INTEGER"))


def ensure_maintenance_work_order_schema():
    inspector = inspect(engine)
    if not inspector.has_table("maintenance_records"):
        return
    columns = {column["name"] for column in inspector.get_columns("maintenance_records")}
    with engine.begin() as connection:
        if "source_work_order_id" not in columns:
            connection.execute(text("ALTER TABLE maintenance_records ADD COLUMN source_work_order_id INTEGER"))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_maintenance_source_work_order "
            "ON maintenance_records(source_work_order_id)"
        ))
    Base.metadata.create_all(bind=engine)


def ensure_lab_ml_schema():
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass


def ensure_tenant_schema():
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


def ensure_legacy_application_access_schema():
    inspector = inspect(engine)
    if not inspector.has_table("users") or not inspector.has_table("user_application_access"):
        return
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO user_application_access (user_id, application, enabled, created_at) "
            "SELECT u.id, 'engineering', TRUE, CURRENT_TIMESTAMP "
            "FROM users u "
            "WHERE u.password_hash IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM user_application_access a "
            "WHERE a.user_id = u.id AND a.application = 'engineering')"
        ))


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

# The simulator is a separate browser origin. Keep production CORS explicit,
# but always include the fixed simulator origin so its HTTPS fallback and
# durable command ACK endpoints work even when CORS_ORIGINS is set by Render.
_configured_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if o.strip()
]
_simulator_origin = "https://maintain-ai-sensor-simulator.jadhavdurvesh65.workers.dev"
_cors_origins = list(dict.fromkeys([*_configured_origins, _simulator_origin]))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Key", "X-Maintain-Application"],
)

app.include_router(auth.router)

# device_commands is intentionally registered before devices so the durable
# REST safety-test route wins over the legacy in-process implementation.
_ROUTER_NAMES = (
    "device_commands",
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
def router_status(current: CurrentUser = Depends(get_current_user)):
    if current.role != models.UserRole.admin.value:
        raise HTTPException(status_code=403, detail="administrator access required")
    return {
        "loaded": [name for name in _ROUTER_NAMES if name not in _ROUTER_LOAD_ERRORS],
        "failed": _ROUTER_LOAD_ERRORS,
    }
