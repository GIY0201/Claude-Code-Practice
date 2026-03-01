"""SQLAlchemy ORM 모델."""

import uuid
from datetime import datetime

from sqlalchemy import (
    String, Float, Boolean, DateTime, Integer, Enum as SAEnum,
    ForeignKey, Text, JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())[:8]


class DroneORM(Base):
    """드론 테이블."""
    __tablename__ = "drones"

    drone_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)
    callsign: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="MULTIROTOR")
    status: Mapped[str] = mapped_column(String(20), default="IDLE")
    # 위치 (단순 컬럼 — PostGIS geometry는 추후 확장)
    lat: Mapped[float] = mapped_column(Float, default=37.5665)
    lon: Mapped[float] = mapped_column(Float, default=126.978)
    alt_m: Mapped[float] = mapped_column(Float, default=0.0)
    # 속도
    vx: Mapped[float] = mapped_column(Float, default=0.0)
    vy: Mapped[float] = mapped_column(Float, default=0.0)
    vz: Mapped[float] = mapped_column(Float, default=0.0)
    heading: Mapped[float] = mapped_column(Float, default=0.0)
    battery_percent: Mapped[float] = mapped_column(Float, default=100.0)
    max_speed_ms: Mapped[float] = mapped_column(Float, default=15.0)
    max_altitude_m: Mapped[float] = mapped_column(Float, default=400.0)
    endurance_minutes: Mapped[float] = mapped_column(Float, default=30.0)
    weight_kg: Mapped[float] = mapped_column(Float, default=2.0)
    current_flight_plan_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    flight_plans: Mapped[list["FlightPlanORM"]] = relationship(back_populates="drone")


class WaypointORM(Base):
    """경유점 테이블."""
    __tablename__ = "waypoints"

    waypoint_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)
    flight_plan_id: Mapped[str] = mapped_column(String(32), ForeignKey("flight_plans.plan_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), default="")
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    alt_m: Mapped[float] = mapped_column(Float, default=100.0)
    waypoint_type: Mapped[str] = mapped_column(String(20), default="ENROUTE")
    speed_constraint_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    altitude_constraint_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)  # 경유점 순서

    flight_plan: Mapped["FlightPlanORM"] = relationship(back_populates="waypoints")


class FlightPlanORM(Base):
    """비행계획 테이블."""
    __tablename__ = "flight_plans"

    plan_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)
    drone_id: Mapped[str] = mapped_column(String(32), ForeignKey("drones.drone_id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    # 출발/도착 좌표 (인라인)
    departure_lat: Mapped[float] = mapped_column(Float, nullable=False)
    departure_lon: Mapped[float] = mapped_column(Float, nullable=False)
    departure_alt_m: Mapped[float] = mapped_column(Float, default=0.0)
    destination_lat: Mapped[float] = mapped_column(Float, nullable=False)
    destination_lon: Mapped[float] = mapped_column(Float, nullable=False)
    destination_alt_m: Mapped[float] = mapped_column(Float, default=0.0)
    departure_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    estimated_arrival: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cruise_altitude_m: Mapped[float] = mapped_column(Float, default=100.0)
    cruise_speed_ms: Mapped[float] = mapped_column(Float, default=10.0)
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL")
    mission_type: Mapped[str] = mapped_column(String(30), default="DELIVERY")
    route_distance_m: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_energy_wh: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    drone: Mapped["DroneORM"] = relationship(back_populates="flight_plans")
    waypoints: Mapped[list["WaypointORM"]] = relationship(
        back_populates="flight_plan",
        cascade="all, delete-orphan",
        order_by="WaypointORM.sequence",
    )


class AirspaceZoneORM(Base):
    """공역 구역 테이블."""
    __tablename__ = "airspace_zones"

    zone_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_type: Mapped[str] = mapped_column(String(20), nullable=False)
    geometry: Mapped[dict] = mapped_column(JSON, nullable=False)  # GeoJSON
    floor_altitude_m: Mapped[float] = mapped_column(Float, default=0.0)
    ceiling_altitude_m: Mapped[float] = mapped_column(Float, default=400.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    schedule: Mapped[str | None] = mapped_column(Text, nullable=True)
    restrictions: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
