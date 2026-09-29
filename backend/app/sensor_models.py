from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base


class ComponentSensor(Base):
    __tablename__ = 'component_sensors'
    __table_args__ = (Index('ix_component_sensors_component', 'component_id'),)
    id = Column(Integer, primary_key=True, index=True)
    component_id = Column(Integer, ForeignKey('components.id'), nullable=False, index=True)
    name = Column(String, nullable=False)
    reading_type = Column(String, nullable=False)
    unit = Column(String, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    readings = relationship('ComponentSensorReading', back_populates='sensor', cascade='all, delete-orphan')


class ComponentSensorReading(Base):
    __tablename__ = 'component_sensor_readings'
    __table_args__ = (
        Index('ix_component_sensor_readings_sensor_time', 'sensor_id', 'recorded_at', 'id'),
        UniqueConstraint('sensor_id', 'external_id', name='uq_component_sensor_reading_event'),
    )
    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(Integer, ForeignKey('component_sensors.id'), nullable=False, index=True)
    component_id = Column(Integer, ForeignKey('components.id'), nullable=False, index=True)
    reading_type = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=True)
    source = Column(String, default='manual')
    external_id = Column(String, nullable=True, index=True)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sensor = relationship('ComponentSensor', back_populates='readings')
