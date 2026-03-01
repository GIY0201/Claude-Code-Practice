"""드론 데이터 모델."""

from pydantic import BaseModel, Field

from .common import (
    DroneType, DroneStatus, Position3D, Velocity3D,
)


class Drone(BaseModel):
    """드론 상태."""
    drone_id: str
    callsign: str = Field(..., description="호출부호 (예: SKY-001)")
    type: DroneType = DroneType.MULTIROTOR
    status: DroneStatus = DroneStatus.IDLE
    position: Position3D = Field(default_factory=lambda: Position3D(lat=37.5665, lon=126.978, alt_m=0))
    velocity: Velocity3D = Field(default_factory=Velocity3D)
    heading: float = Field(0.0, ge=0, lt=360, description="기수 방향 (degrees)")
    battery_percent: float = Field(100.0, ge=0, le=100)
    max_speed_ms: float = Field(15.0, gt=0, description="최대 속도 (m/s)")
    max_altitude_m: float = Field(400.0, gt=0, description="최대 비행 고도 (m)")
    endurance_minutes: float = Field(30.0, gt=0, description="최대 체공 시간 (분)")
    weight_kg: float = Field(2.0, gt=0, description="기체 중량 (kg)")
    current_flight_plan_id: str | None = None


class DroneCreate(BaseModel):
    """드론 등록 요청."""
    callsign: str
    type: DroneType = DroneType.MULTIROTOR
    max_speed_ms: float = 15.0
    max_altitude_m: float = 400.0
    endurance_minutes: float = 30.0
    weight_kg: float = 2.0


class DroneUpdate(BaseModel):
    """드론 상태 업데이트."""
    status: DroneStatus | None = None
    position: Position3D | None = None
    velocity: Velocity3D | None = None
    heading: float | None = None
    battery_percent: float | None = None
    current_flight_plan_id: str | None = None
