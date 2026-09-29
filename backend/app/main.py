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
from .ml.forecast_runs import MLForecastRun  # noqa: F401 - register model with SQLAlchemy metadata
from .ml import forecast_events  # noqa: F401 - register telemetry commit listeners

def _initialize_database():
    try:
        from .routers.runtime import runtime_states
        Base.metadata.create_all(bind=engine)
        ensure_ai_conversation_schema(); ensure_user_auth_schema(); ensure_user_work_order_schema(); ensure_maintenance_work_order_schema(); ensure_lab_ml_schema(); ensure_tenant_schema(); ensure_legacy_application_access_schema(); ensure_safety_policy_schema(); ensure_bootstrap_organization()
    except Exception: pass

def ensure_safety_policy_schema():
    try:
        inspector=inspect(engine)
        if not inspector.has_table('machine_safety_policies'): return
        if engine.dialect.name=='postgresql':
            with engine.begin() as connection:
                connection.execute(text("""DO $body$ DECLARE constraint_name TEXT; BEGIN SELECT conname INTO constraint_name FROM pg_constraint WHERE conrelid = 'machine_safety_policies'::regclass AND contype = 'u' AND pg_get_constraintdef(oid) = 'UNIQUE (machine_id)'; IF constraint_name IS NOT NULL THEN EXECUTE format('ALTER TABLE machine_safety_policies DROP CONSTRAINT %I', constraint_name); END IF; END $body$;"""))
                connection.execute(text('CREATE INDEX IF NOT EXISTS ix_machine_safety_policies_machine_id ON machine_safety_policies (machine_id)'))
    except Exception: pass

def ensure_ai_conversation_schema():
    inspector=inspect(engine)