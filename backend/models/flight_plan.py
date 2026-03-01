"""비행계획 데이터 모델."""

from datetime import datetime

from pydantic import BaseModel, Field

from .common import PlanStatus, Priority, MissionType, Position3D
from .waypoint import Waypoint, WaypointCreate


class FlightPlan(BaseModel):
    """비행계획."""
    plan_id: str
    drone_id: str
    status: PlanStatus = PlanStatus.DRAFT
    departure: Waypoint
    destination: Waypoint
    waypoints: list[Waypoint] = Field(default_factory=list)
    departure_time: datetime
    estimated_arrival: datetime | None = None
    cruise_altitude_m: float = Field(100.0, ge=30, le=400)
    cruise_speed_ms: float = Field(10.0, gt=0)
    priority: Priority = Priority.NORMAL
    mission_type: MissionType = MissionType.DELIVERY
    route_distance_m: float = 0.0
    estimated_energy_wh: float = 0.0


class FlightPlanCreate(BaseModel):
    """비행계획 생성 요청."""
    drone_id: str
    departure_position: Position3D
    destination_position: Position3D
    departure_time: datetime
    cruise_altitude_m: float = 100.0
    cruise_speed_ms: float = 10.0
    priority: Priority = Priority.NORMAL
    mission_type: MissionType = MissionType.DELIVERY


class FlightPlanResponse(FlightPlan):
    """비행계획 API 응답 (경로 포함)."""
    pass
