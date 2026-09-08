import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Boolean,
    ForeignKey, Enum
)
from sqlalchemy.orm import relationship

from .database import Base


class HealthStatus(str, enum.Enum):
    healthy = "healthy"
    attention = "attention"
    critical = "critical"


class Criticality(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class MaintenanceType(str, enum.Enum):
    preventive = "preventive"
    corrective = "corrective"
    breakdown = "breakdown"
    predictive = "predictive"


class MaintenanceStatus(str, enum.Enum):
    scheduled = "scheduled"
    overdue = "overdue"
    completed = "completed"


class WorkOrderStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertSeverity(str, enum.Enum):
    normal = "normal"
    warning = "warning"
    high = "high"
    critical = "critical"


class UserRole(str, enum.Enum):
    admin = "admin"
    technician = "technician"
    viewer = "viewer"


class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    machine_code = Column(String, unique=True, index=True, nullable=False)  # e.g. M-001
    name = Column(String, nullable=False)
    category = Column(String)
    manufacturer = Column(String)
    model_number = Column(String)
    installation_date = Column(DateTime)
    location = Column(String)
    department = Column(String)
    operating_hours = Column(Float, default=0)
    criticality = Column(Enum(Criticality), default=Criticality.medium)

    health_score = Column(Integer, default=100)
    status = Column(Enum(HealthStatus), default=HealthStatus.healthy)

    maintenance_interval_hours = Column(Float, default=500)
    last_maintenance_date = Column(DateTime, nullable=True)
    next_maintenance_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    archived = Column(Boolean, default=False)  # soft-delete: history is never destroyed

    # Multi-tenant scoping. Defaults to the bootstrap org (id=1) so existing
    # single-company/local-mode data (and any machine created while
    # REQUIRE_AUTH is off) keeps working exactly as before — this column is
    # invisible in that mode, not a breaking change.
    organization_id = Column(Integer, ForeignKey("organizations.id"), default=1, nullable=False)

    # Optional live-sensor/ESP32 integration — off by default. A machine with
    # iot_enabled=False rejects device readings even if someone has the key;
    # manual entry (the default) is completely unaffected either way.
    iot_enabled = Column(Boolean, default=False)
    device_key = Column(String, unique=True, index=True, nullable=True)

    components = relationship("Component", back_populates="machine", cascade="all, delete-orphan")
    faults = relationship("FaultRecord", back_populates="machine", cascade="all, delete-orphan")
    sensor_readings = relationship("SensorReading", back_populates="machine", cascade="all, delete-orphan")
    maintenance_records = relationship("MaintenanceRecord", back_populates="machine", cascade="all, delete-orphan")
    work_orders = relationship("WorkOrder", back_populates="machine", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="machine", cascade="all, delete-orphan")
    ai_sessions = relationship("AIDiagnosticSession", back_populates="machine", cascade="all, delete-orphan")


class Component(Base):
    __tablename__ = "components"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"))
    name = Column(String, nullable=False)
    description = Column(Text)

    machine = relationship("Machine", back_populates="components")


class FaultRecord(Base):
    __tablename__ = "fault_records"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"))
    description = Column(Text, nullable=False)
    symptoms = Column(Text)  # comma separated for simplicity
    cause = Column(Text)
    resolution = Column(Text)
    severity = Column(Enum(AlertSeverity), default=AlertSeverity.warning)
    reported_date = Column(DateTime, default=datetime.utcnow)
    resolved_date = Column(DateTime, nullable=True)

    machine = relationship("Machine", back_populates="faults")


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"))
    reading_type = Column(String, nullable=False)  # temperature, vibration, current, load
    value = Column(Float, nullable=False)
    unit = Column(String)
    source = Column(String, default="manual")  # manual | sensor
    recorded_at = Column(DateTime, default=datetime.utcnow)

    machine = relationship("Machine", back_populates="sensor_readings")


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"))
    type = Column(Enum(MaintenanceType), default=MaintenanceType.preventive)
    description = Column(Text)
    scheduled_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    status = Column(Enum(MaintenanceStatus), default=MaintenanceStatus.scheduled)
    performed_by = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    machine = relationship("Machine", back_populates="maintenance_records")


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"))
    problem = Column(Text, nullable=False)
    priority = Column(Enum(Priority), default=Priority.medium)
    status = Column(Enum(WorkOrderStatus), default=WorkOrderStatus.pending)
    recommended_actions = Column(Text)  # newline separated
    assigned_to = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    machine = relationship("Machine", back_populates="work_orders")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"))
    alert_type = Column(String, nullable=False)  # overheating, high_vibration, overdue_maintenance, etc.
    severity = Column(Enum(AlertSeverity), default=AlertSeverity.warning)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    acknowledged = Column(Boolean, default=False)
    resolved = Column(Boolean, default=False)

    machine = relationship("Machine", back_populates="alerts")


class SparePart(Base):
    __tablename__ = "spare_parts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    part_number = Column(String, unique=True, index=True)
    quantity = Column(Integer, default=0)
    minimum_stock = Column(Integer, default=1)
    compatible_machine_categories = Column(String, nullable=True)  # comma separated
    last_used_date = Column(DateTime, nullable=True)


class KnowledgeBaseEntry(Base):
    __tablename__ = "knowledge_base_entries"

    id = Column(Integer, primary_key=True, index=True)
    machine_category = Column(String, nullable=False, index=True)  # e.g. "induction_motor"
    fault_name = Column(String, nullable=False)
    symptoms = Column(Text)  # JSON list as text
    causes = Column(Text)  # JSON list of {cause, confidence} as text
    questions = Column(Text)  # JSON list of clarifying questions as text
    recommended_procedure = Column(Text)  # JSON list of steps as text
    safety_notes = Column(Text)


class AIDiagnosticSession(Base):
    __tablename__ = "ai_diagnostic_sessions"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    problem_description = Column(Text)
    questions_asked = Column(Text)  # JSON list as text
    answers = Column(Text, nullable=True)  # JSON list as text
    likely_causes = Column(Text)  # JSON list of {cause, confidence} as text
    recommended_action = Column(Text)
    final_technician_result = Column(Text, nullable=True)
    source = Column(String, default="offline")  # offline | gemini
    created_at = Column(DateTime, default=datetime.utcnow)

    machine = relationship("Machine", back_populates="ai_sessions")


class Organization(Base):
    """A company/tenant. Every user belongs to exactly one. When auth is
    disabled (the default, local-first mode), everything implicitly belongs
    to a single bootstrap Organization (id=1) and this is invisible to the
    user — nothing about the existing single-machine/single-company
    experience changes unless REQUIRE_AUTH is turned on."""
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String)
    role = Column(Enum(UserRole), default=UserRole.technician)

    # Auth fields — nullable because pre-existing local-mode Users (added
    # via Settings > Add User, no login) don't have credentials. A user
    # needs email+password_hash set to actually log in.
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)


class AppSetting(Base):
    """Generic local key-value store — used for the Gemini API key so it lives
    in the user's own local database instead of a source file or the installer."""
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(String, nullable=True)


class AuditLog(Base):
    """Permanent, append-only record of everything that happens in the system.
    Never edited or deleted by the app itself — this is the 'nothing is ever
    lost' guarantee: every machine added, every job completed, every alert
    resolved leaves a row here forever, independent of whatever happens to
    the underlying record itself."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False, index=True)  # machine | work_order | maintenance | alert | spare_part | ai_session
    entity_id = Column(Integer, nullable=True, index=True)
    action = Column(String, nullable=False)  # created | updated | completed | archived | resolved | acknowledged
    description = Column(Text, nullable=False)
    performed_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
