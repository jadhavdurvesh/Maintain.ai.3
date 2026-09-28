from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from ..database import Base


class MLForecastRun(Base):
    """Durable point-in-time forecast generated from a concrete telemetry snapshot."""

    __tablename__ = "ml_forecast_runs"
    __table_args__ = (
        UniqueConstraint(
            "machine_id",
            "reading_type",
            "model",
            "horizon",
            "input_last_reading_id",
            name="uq_ml_forecast_input",
        ),
        Index("ix_ml_forecast_machine_signal_created", "machine_id", "reading_type", "created_at"),
        Index("ix_ml_forecast_machine_created", "machine_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    reading_type = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False, default="chronos-bolt-tiny")
    horizon = Column(Integer, nullable=False, default=12)

    input_first_reading_id = Column(Integer, nullable=True)
    input_last_reading_id = Column(Integer, nullable=False, index=True)
    input_started_at = Column(DateTime, nullable=True)
    input_ended_at = Column(DateTime, nullable=True)
    input_reading_count = Column(Integer, nullable=False, default=0)

    forecast_json = Column(Text, nullable=True)
    next_prediction = Column(Float, nullable=True)
    end_prediction = Column(Float, nullable=True)
    trend = Column(String, nullable=True)

    status = Column(String, nullable=False, default="running", index=True)
    trigger = Column(String, nullable=False, default="automatic")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
