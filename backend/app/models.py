import enum
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Boolean,
    ForeignKey, Enum, LargeBinary
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
    machine_code = Column(String, unique=True, index=True, nullable=False)
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
    archived = Column(Boolean, default=False)

    organization_id = Column(Integer, ForeignKey("organizations.id"), default=1, nullable=False)

    iot_enabled = Column(Boolean, default=False)
    device_key = Column(String, unique=True, index=True, nullable=True)

    components = relationship("Component", back_populates="machine", cascade="all, delete-orphan")
    faults = relationship("FaultRecord", back_populates="machine", cascade="all, delete-orphan")
    sensor_readings = relationship("SensorReading", back_populates="machine", cascade="all, delete-orphan")
    maintenance_records = relationship("MaintenanceRecord", back_populates="machine", cascade="all, delete-orphan")
    work_orders = relationship("WorkOrder", back_populates="machine", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="machine", cascade="all, delete-orphan")
    ai_sessions = relationship("AIDiagnosticSession", back_populates="machine", cascade="all, delete-orphan")
    ai_conversations = relationship("AIConversation", back_populates="machine", cascade="all, delete-orphan")


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
    symptoms = Column(Text)
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
    reading_type = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String)
    source = Column(String, default="manual")
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
    recommended_actions = Column(Text)
    assigned_to = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    machine = relationship("Machine", back_populates="work_orders")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"))
    alert_type = Column(String, nullable=False)
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
    compatible_machine_categories = Column(String, nullable=True)
    last_used_date = Column(DateTime, nullable=True)


class KnowledgeBaseEntry(Base):
    __tablename__ = "knowledge_base_entries"

    id = Column(Integer, primary_key=True, index=True)
    machine_category = Column(String, nullable=False, index=True)
    fault_name = Column(String, nullable=False)
    symptoms = Column(Text)
    causes = Column(Text)
    questions = Column(Text)
    recommended_procedure = Column(Text)
    safety_notes = Column(Text)


class AIDiagnosticSession(Base):
    __tablename__ = "ai_diagnostic_sessions"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id"), nullable=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    problem_description = Column(Text)
    questions_asked = Column(Text)
    answers = Column(Text, nullable=True)
    likely_causes = Column(Text)
    recommended_action = Column(Text)
    final_technician_result = Column(Text, nullable=True)
    source = Column(String, default="offline")
    created_at = Column(DateTime, default=datetime.utcnow)

    machine = relationship("Machine", back_populates="ai_sessions")
    conversation = relationship("AIConversation", back_populates="diagnostic_sessions")


class AIConversation(Base):
    """Persistent chat container that survives page navigation and browser refreshes."""
    __tablename__ = "ai_conversations"

    id = Column(Integer, primary_key=True, index=True)
    conversation_key = Column(String, unique=True, index=True, nullable=False)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, index=True)

    machine = relationship("Machine", back_populates="ai_conversations")
    messages = relationship("AIConversationMessage", back_populates="conversation", cascade="all, delete-orphan")
    diagnostic_sessions = relationship("AIDiagnosticSession", back_populates="conversation")


class AIConversationMessage(Base):
    """Every technician/assistant turn in an AI conversation, with a timestamp."""
    __tablename__ = "ai_conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # technician | assistant | system
    message_type = Column(String, nullable=False, default="chat")  # problem | answer | diagnosis | outcome
    content = Column(Text, nullable=False)
    source = Column(String, nullable=True)  # gemini | offline | app
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    conversation = relationship("AIConversation", back_populates="messages")


class Organization(Base):
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
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)


class AppSetting(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(String, nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, nullable=False, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    action = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    performed_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class MLModelArtifact(Base):
    """Persistent serialized local ML model.

    Keeping this small artifact in the application's database makes model
    training work on serverless deployments as well as local desktop installs;
    no writable project filesystem is required.
    """
    __tablename__ = "ml_model_artifacts"

    id = Column(Integer, primary_key=True)
    model_version = Column(Integer, nullable=False)
    feature_names = Column(Text, nullable=False)
    trained_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    n_samples = Column(Integer, nullable=False, default=0)
    artifact = Column(LargeBinary, nullable=False)
