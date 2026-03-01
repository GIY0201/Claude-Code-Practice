"""텔레메트리 데이터 모델."""

from datetime import datetime

from pydantic import BaseModel, Field

from .common import (
    Position3D, Velocity3D, GPSFixType, MotorStatus, Alert,
)


class Telemetry(BaseModel):
    """드론 텔레메트리 (실시간 스트리밍)."""
    drone_id: str
    timestamp: datetime
    position: Position3D
    velocity: Velocity3D
    heading: float = Field(0.0, ge=0, lt=360)
    battery_percent: float = Field(100.0, ge=0, le=100)
    gps_fix: GPSFixType = GPSFixType.FIX_3D
    signal_strength: float = Field(100.0, ge=0, le=100, description="통신 신호 강도 (%)")
    motor_status: list[MotorStatus] = Field(default_factory=lambda: [MotorStatus.OK] * 4)
    alerts: list[Alert] = Field(default_factory=list)
