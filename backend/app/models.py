import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Index,
    String,
    Float,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Enum,
    LargeBinary,
    UniqueConstraint,
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
    __table_args__ = (Index("ix_sensor_readings_machine_recorded", "machine_id", "recorded_at", "id"),)
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
    fault_id = Column(Integer, ForeignKey("fault_records.id"), nullable=True, index=True)
    problem = Column(Text, nullable=False)
    priority = Column(Enum(Priority), default=Priority.medium)
    status = Column(Enum(WorkOrderStatus), default=WorkOrderStatus.pending)
    recommended_actions = Column(Text)
    assigned_to = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
    machine = relationship("Machine", back_populates="work_orders")
    fault = relationship("FaultRecord")


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
    __tablename__ = "ai_conversation_messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    message_type = Column(String, nullable=False, default="chat")
    content = Column(Text, nullable=False)
    source = Column(String, nullable=True)
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
    supabase_user_id = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    active = Column(Boolean, default=True, nullable=False)


class UserApplicationAccess(Base):
    __tablename__ = "user_application_access"
    __table_args__ = (UniqueConstraint("user_id", "application", name="uq_user_application_access"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    application = Column(String, nullable=False, index=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    email = Column(String, nullable=False, index=True)
    role = Column(Enum(UserRole), default=UserRole.technician, nullable=False)
    application = Column(String, nullable=False, default="workforce")
    supabase_user_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="pending")
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime, nullable=True)


class UserMachineAssignment(Base):
    __tablename__ = "user_machine_assignments"
    __table_args__ = (UniqueConstraint("user_id", "machine_id", name="uq_user_machine_assignment"),)
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)


class NotificationDevice(Base):
    __tablename__ = "notification_devices"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_token = Column(String, unique=True, index=True, nullable=False)
    platform = Column(String, nullable=False, default="android")
    app_version = Column(String, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)


class InAppNotification(Base):
    __tablename__ = "in_app_notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    notification_type = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    data_json = Column(Text, nullable=True)
    read = Column(Boolean, default=False, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


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
    __tablename__ = "ml_model_artifacts"
    id = Column(Integer, primary_key=True)
    model_version = Column(Integer, nullable=False)
    feature_names = Column(Text, nullable=False)
    trained_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    n_samples = Column(Integer, nullable=False, default=0)
    artifact = Column(LargeBinary, nullable=False)


class MLBehaviourState(Base):
    """Persistent online-learning state for one machine/sensor signal."""
    __tablename__ = "ml_behaviour_states"
    __table_args__ = (
        UniqueConstraint("machine_id", "reading_type", name="uq_ml_behaviour_machine_signal"),
    )
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    reading_type = Column(String, nullable=False, index=True)
    model_version = Column(Integer, nullable=False, default=1)
    sample_count = Column(Integer, nullable=False, default=0)
    mean_value = Column(Float, nullable=False, default=0.0)
    m2 = Column(Float, nullable=False, default=0.0)
    variance = Column(Float, nullable=False, default=0.0)
    ewma = Column(Float, nullable=False, default=0.0)
    last_value = Column(Float, nullable=False, default=0.0)
    last_anomaly_score = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MLAnomalyEvent(Base):
    """Durable record of a confirmed behavioural anomaly in the Lab."""
    __tablename__ = "ml_anomaly_events"
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    reading_type = Column(String, nullable=False, index=True)
    anomaly_score = Column(Float, nullable=False, default=0.0)
    severity = Column(Enum(AlertSeverity), nullable=False, default=AlertSeverity.warning)
    message = Column(Text, nullable=False)
    evidence_json = Column(Text, nullable=True)
    notified = Column(Boolean, nullable=False, default=False)
    acknowledged = Column(Boolean, nullable=False, default=False)
    resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class MLTelemetryWindow(Base):
    """Materialized rolling time-series features for advanced ML training/inference."""
    __tablename__ = "ml_telemetry_windows"
    __table_args__ = (UniqueConstraint("machine_id", "window_end", "window_seconds", name="uq_ml_window_machine_end"),)
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    window_end = Column(DateTime, nullable=False, index=True)
    window_seconds = Column(Integer, nullable=False)
    sample_count = Column(Integer, nullable=False, default=0)
    feature_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MLTrainingLabel(Base):
    """Point-in-time outcome labels derived only from events after a telemetry window."""
    __tablename__ = "ml_training_labels"
    __table_args__ = (
        UniqueConstraint(
            "machine_id", "window_end", "window_seconds", "horizon_seconds",
            name="uq_ml_training_label_point",
        ),
        Index("ix_ml_training_labels_machine_window", "machine_id", "window_end"),
    )
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    window_end = Column(DateTime, nullable=False, index=True)
    window_seconds = Column(Integer, nullable=False)
    horizon_seconds = Column(Integer, nullable=False)
    fault_within_horizon = Column(Boolean, nullable=False, default=False)
    breakdown_work_order_within_horizon = Column(Boolean, nullable=False, default=False)
    fault_id = Column(Integer, ForeignKey("fault_records.id"), nullable=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MLSequenceSample(Base):
    """Contiguous temporal windows joined to future outcome labels."""
    __tablename__ = "ml_sequence_samples"
    __table_args__ = (
        UniqueConstraint("machine_id", "end_window_id", "sequence_length", "horizon_seconds",
                         name="uq_ml_sequence_sample"),
        Index("ix_ml_sequence_machine_end", "machine_id", "window_end"),
    )
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    end_window_id = Column(Integer, ForeignKey("ml_telemetry_windows.id"), nullable=False, index=True)
    window_end = Column(DateTime, nullable=False, index=True)
    window_seconds = Column(Integer, nullable=False)
    sequence_length = Column(Integer, nullable=False)
    horizon_seconds = Column(Integer, nullable=False)
    sequence_json = Column(Text, nullable=False)
    target_failure = Column(Boolean, nullable=False, default=False)
    fault_id = Column(Integer, ForeignKey("fault_records.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)



class MLDegradationSnapshot(Base):
    """Point-in-time machine degradation evidence derived from online telemetry."""
    __tablename__ = "ml_degradation_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    degradation_score = Column(Float, nullable=False, default=0.0)
    trend_score = Column(Float, nullable=False, default=0.0)
    active_signal_count = Column(Integer, nullable=False, default=0)
    evidence_json = Column(Text, nullable=True)
    source = Column(String, nullable=False, default="online_behaviour")


class MLOutcomeFeedback(Base):
    """Technician-confirmed outcome used to improve future predictive models."""
    __tablename__ = "ml_outcome_feedback"
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    fault_id = Column(Integer, ForeignKey("fault_records.id"), nullable=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=True, index=True)
    outcome_type = Column(String, nullable=False, index=True)
    confirmed_root_cause = Column(Text, nullable=True)
    failed_component = Column(String, nullable=True)
    corrective_action = Column(Text, nullable=True)
    downtime_minutes = Column(Float, nullable=True)
    false_alarm = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class MachineSafetyPolicy(Base):
    """Per-machine warning and automatic-shutdown interlock configuration."""
    __tablename__ = "machine_safety_policies"
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, unique=True, index=True)
    enabled = Column(Boolean, nullable=False, default=False)
    monitored_reading_type = Column(String, nullable=False, default="temperature")
    unit = Column(String, nullable=True)
    warning_low = Column(Float, nullable=True)
    warning_high = Column(Float, nullable=True)
    shutdown_low = Column(Float, nullable=True)
    shutdown_high = Column(Float, nullable=True)
    auto_shutdown_enabled = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_trip_at = Column(DateTime, nullable=True)
    last_trip_value = Column(Float, nullable=True)
    last_trip_reason = Column(Text, nullable=True)


class MachineSafetyEvent(Base):
    """Durable record of threshold warnings and shutdown requests."""
    __tablename__ = "machine_safety_events"
    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    reading_type = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=True)
    message = Column(Text, nullable=False)
    shutdown_requested = Column(Boolean, nullable=False, default=False)
    device_acknowledged = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
