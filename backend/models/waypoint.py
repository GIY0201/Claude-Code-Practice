"""경유점 데이터 모델."""

from datetime import datetime

from pydantic import BaseModel, Field

from .common import Position3D, WaypointType


class Waypoint(BaseModel):
    """비행 경유점."""
    waypoint_id: str
    name: str = ""
    position: Position3D
    waypoint_type: WaypointType = WaypointType.ENROUTE
    speed_constraint_ms: float | None = None
    altitude_constraint_m: float | None = None
    estimated_time: datetime | None = None


class WaypointCreate(BaseModel):
    """경유점 생성 요청."""
    name: str = ""
    position: Position3D
    waypoint_type: WaypointType = WaypointType.ENROUTE
    speed_constraint_ms: float | None = None
    altitude_constraint_m: float | None = None
