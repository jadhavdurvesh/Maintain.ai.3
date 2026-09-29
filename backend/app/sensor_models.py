from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index
from .database import Base

class ComponentSensor(Base):
    __tablename__ = "component_sensors"
    __table_args__ = (Index("ix_component_sensors_component", "component_id"),)
    id = Column(Integer, primary_key=True, index=True)
    component_id = Column(Integer, ForeignKey("components.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    reading_type = Column(String, nullable=False)
    unit = Column(String, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
