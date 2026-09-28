from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, inspect, text

from ..database import Base, engine


class MLForecastRun(Base):
    """Durable forecast generated from a concrete telemetry snapshot."""

    __tablename__ = "ml_forecast_runs"
    __table_args__ = (
        UniqueConstraint(
            "machine_id",
            "reading_type",
            "model",
            "horizon",
            "input_last_reading_id",
            "forecast_window",
            name="uq_ml_forecast_input",
        ),
        Index("ix_ml_forecast_machine_signal_created", "machine_id", "reading_type", "created_at"),
        Index("ix_ml_forecast_machine_created", "machine_id", "created_at"),
        Index("ix_ml_forecast_machine_window_created", "machine_id", "forecast_window", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=False, index=True)
    reading_type = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False, default="chronos-bolt-tiny")
    horizon = Column(Integer, nullable=False, default=12)
    forecast_window = Column(String, nullable=True, index=True)
    step_seconds = Column(Integer, nullable=True)

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


def ensure_forecast_schema() -> None:
    """Upgrade the pre-window Postgres unique constraint without touching forecast rows."""
    try:
        inspector = inspect(engine)
        if "ml_forecast_runs" not in inspector.get_table_names():
            return
        if engine.dialect.name != "postgresql":
            return
        constraints = inspector.get_unique_constraints("ml_forecast_runs")
        existing = next((item for item in constraints if item.get("name") == "uq_ml_forecast_input"), None)
        if existing and "forecast_window" in (existing.get("column_names") or []):
            return
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE ml_forecast_runs DROP CONSTRAINT IF EXISTS uq_ml_forecast_input"))
            connection.execute(text(
                "ALTER TABLE ml_forecast_runs ADD CONSTRAINT uq_ml_forecast_input "
                "UNIQUE (machine_id, reading_type, model, horizon, input_last_reading_id, forecast_window)"
            ))
    except Exception:
        # Startup must remain compatible with local SQLite/demo databases; create_all handles new schemas.
        return
