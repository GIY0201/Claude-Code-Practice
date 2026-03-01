"""공역 데이터 모델."""

from pydantic import BaseModel, Field

from .common import ZoneType


class AirspaceZone(BaseModel):
    """공역 구역."""
    zone_id: str
    name: str
    zone_type: ZoneType
    geometry: dict = Field(..., description="GeoJSON Polygon geometry")
    floor_altitude_m: float = Field(0.0, ge=0)
    ceiling_altitude_m: float = Field(400.0, gt=0)
    active: bool = True
    schedule: str | None = None
    restrictions: list[str] = Field(default_factory=list)


class AirspaceZoneCreate(BaseModel):
    """공역 구역 생성 요청."""
    name: str
    zone_type: ZoneType
    geometry: dict
    floor_altitude_m: float = 0.0
    ceiling_altitude_m: float = 400.0
    restrictions: list[str] = Field(default_factory=list)
