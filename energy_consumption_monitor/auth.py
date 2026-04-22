"""
Pydantic Models for API request/response validation
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any


class SensorDataResponse(BaseModel):
    time: datetime
    device_id: str
    location: Optional[str] = None
    power_watts: Optional[float] = None
    voltage: Optional[float] = None
    current: Optional[float] = None
    power_factor: Optional[float] = None
    frequency: Optional[float] = None

    class Config:
        from_attributes = True


class DeviceResponse(BaseModel):
    device_id: str
    device_name: str
    location: Optional[str] = None
    device_type: Optional[str] = None
    rated_power: Optional[float] = None
    installation_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    time: datetime
    device_id: Optional[str] = None
    alert_type: str
    severity: str
    message: str
    threshold_value: Optional[float] = None
    actual_value: Optional[float] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PowerStatsResponse(BaseModel):
    device_id: str
    avg_power: Optional[float] = None
    max_power: Optional[float] = None
    min_power: Optional[float] = None
    stddev_power: Optional[float] = None
    sample_count: int

    class Config:
        from_attributes = True


class HealthResponse(BaseModel):
    status: str
    database: bool
    mqtt: bool
    timestamp: datetime
