"""CRUD operations for SkyMind database."""

import uuid
from sqlalchemy.orm import Session

from db.orm_models import DroneORM, FlightPlanORM, WaypointORM, AirspaceZoneORM
from models.common import Position3D, Velocity3D
from models.drone import Drone, DroneCreate, DroneUpdate
from models.flight_plan import FlightPlan, FlightPlanCreate
from models.waypoint import Waypoint
from models.airspace import AirspaceZone, AirspaceZoneCreate


def _gen_id() -> str:
    return str(uuid.uuid4())[:8]


# ──────────────── ORM ↔ Pydantic 변환 ────────────────

def _drone_orm_to_pydantic(orm: DroneORM) -> Drone:
    """DroneORM → Drone Pydantic 모델."""
    return Drone(
        drone_id=orm.drone_id,
        callsign=orm.callsign,
        type=orm.type,
        status=orm.status,
        position=Position3D(lat=orm.lat, lon=orm.lon, alt_m=orm.alt_m),
        velocity=Velocity3D(vx=orm.vx, vy=orm.vy, vz=orm.vz),
        heading=orm.heading,
        battery_percent=orm.battery_percent,
        max_speed_ms=orm.max_speed_ms,
        max_altitude_m=orm.max_altitude_m,
        endurance_minutes=orm.endurance_minutes,
        weight_kg=orm.weight_kg,
        current_flight_plan_id=orm.current_flight_plan_id,
    )


def _waypoint_orm_to_pydantic(orm: WaypointORM) -> Waypoint:
    """WaypointORM → Waypoint Pydantic 모델."""
    return Waypoint(
        waypoint_id=orm.waypoint_id,
        name=orm.name,
        position=Position3D(lat=orm.lat, lon=orm.lon, alt_m=orm.alt_m),
        waypoint_type=orm.waypoint_type,
        speed_constraint_ms=orm.speed_constraint_ms,
        altitude_constraint_m=orm.altitude_constraint_m,
        estimated_time=orm.estimated_time,
    )


def _flight_plan_orm_to_pydantic(orm: FlightPlanORM) -> FlightPlan:
    """FlightPlanORM → FlightPlan Pydantic 모델."""
    waypoints = [_waypoint_orm_to_pydantic(w) for w in orm.waypoints]

    departure_wp = Waypoint(
        waypoint_id="dep",
        name="Departure",
        position=Position3D(lat=orm.departure_lat, lon=orm.departure_lon, alt_m=orm.departure_alt_m),
        waypoint_type="DEPARTURE",
    )
    destination_wp = Waypoint(
        waypoint_id="arr",
        name="Destination",
        position=Position3D(lat=orm.destination_lat, lon=orm.destination_lon, alt_m=orm.destination_alt_m),
        waypoint_type="ARRIVAL",
    )

    return FlightPlan(
        plan_id=orm.plan_id,
        drone_id=orm.drone_id,
        status=orm.status,
        departure=departure_wp,
        destination=destination_wp,
        waypoints=waypoints,
        departure_time=orm.departure_time,
        estimated_arrival=orm.estimated_arrival,
        cruise_altitude_m=orm.cruise_altitude_m,
        cruise_speed_ms=orm.cruise_speed_ms,
        priority=orm.priority,
        mission_type=orm.mission_type,
        route_distance_m=orm.route_distance_m,
        estimated_energy_wh=orm.estimated_energy_wh,
    )


def _airspace_orm_to_pydantic(orm: AirspaceZoneORM) -> AirspaceZone:
    """AirspaceZoneORM → AirspaceZone Pydantic 모델."""
    return AirspaceZone(
        zone_id=orm.zone_id,
        name=orm.name,
        zone_type=orm.zone_type,
        geometry=orm.geometry,
        floor_altitude_m=orm.floor_altitude_m,
        ceiling_altitude_m=orm.ceiling_altitude_m,
        active=orm.active,
        schedule=orm.schedule,
        restrictions=orm.restrictions or [],
    )


# ──────────────── Drone CRUD ────────────────

def create_drone(db: Session, data: DroneCreate) -> Drone:
    """드론 등록."""
    orm = DroneORM(
        drone_id=_gen_id(),
        callsign=data.callsign,
        type=data.type.value if hasattr(data.type, 'value') else data.type,
        max_speed_ms=data.max_speed_ms,
        max_altitude_m=data.max_altitude_m,
        endurance_minutes=data.endurance_minutes,
        weight_kg=data.weight_kg,
    )
    db.add(orm)
    db.commit()
    db.refresh(orm)
    return _drone_orm_to_pydantic(orm)


def get_drone(db: Session, drone_id: str) -> Drone | None:
    """드론 조회."""
    orm = db.query(DroneORM).filter(DroneORM.drone_id == drone_id).first()
    if orm is None:
        return None
    return _drone_orm_to_pydantic(orm)


def get_drone_by_callsign(db: Session, callsign: str) -> Drone | None:
    """호출부호로 드론 조회."""
    orm = db.query(DroneORM).filter(DroneORM.callsign == callsign).first()
    if orm is None:
        return None
    return _drone_orm_to_pydantic(orm)


def list_drones(db: Session, status: str | None = None) -> list[Drone]:
    """드론 목록 조회."""
    query = db.query(DroneORM)
    if status:
        query = query.filter(DroneORM.status == status)
    return [_drone_orm_to_pydantic(orm) for orm in query.all()]


def update_drone(db: Session, drone_id: str, data: DroneUpdate) -> Drone | None:
    """드론 상태 업데이트."""
    orm = db.query(DroneORM).filter(DroneORM.drone_id == drone_id).first()
    if orm is None:
        return None
    if data.status is not None:
        orm.status = data.status.value if hasattr(data.status, 'value') else data.status
    if data.position is not None:
        orm.lat = data.position.lat
        orm.lon = data.position.lon
        orm.alt_m = data.position.alt_m
    if data.velocity is not None:
        orm.vx = data.velocity.vx
        orm.vy = data.velocity.vy
        orm.vz = data.velocity.vz
    if data.heading is not None:
        orm.heading = data.heading
    if data.battery_percent is not None:
        orm.battery_percent = data.battery_percent
    if data.current_flight_plan_id is not None:
        orm.current_flight_plan_id = data.current_flight_plan_id
    db.commit()
    db.refresh(orm)
    return _drone_orm_to_pydantic(orm)


def delete_drone(db: Session, drone_id: str) -> bool:
    """드론 삭제."""
    orm = db.query(DroneORM).filter(DroneORM.drone_id == drone_id).first()
    if orm is None:
        return False
    db.delete(orm)
    db.commit()
    return True


# ──────────────── FlightPlan CRUD ────────────────

def create_flight_plan(db: Session, data: FlightPlanCreate) -> FlightPlan:
    """비행계획 생성."""
    orm = FlightPlanORM(
        plan_id=_gen_id(),
        drone_id=data.drone_id,
        departure_lat=data.departure_position.lat,
        departure_lon=data.departure_position.lon,
        departure_alt_m=data.departure_position.alt_m,
        destination_lat=data.destination_position.lat,
        destination_lon=data.destination_position.lon,
        destination_alt_m=data.destination_position.alt_m,
        departure_time=data.departure_time,
        cruise_altitude_m=data.cruise_altitude_m,
        cruise_speed_ms=data.cruise_speed_ms,
        priority=data.priority.value if hasattr(data.priority, 'value') else data.priority,
        mission_type=data.mission_type.value if hasattr(data.mission_type, 'value') else data.mission_type,
    )
    db.add(orm)
    db.commit()
    db.refresh(orm)
    return _flight_plan_orm_to_pydantic(orm)


def get_flight_plan(db: Session, plan_id: str) -> FlightPlan | None:
    """비행계획 조회."""
    orm = db.query(FlightPlanORM).filter(FlightPlanORM.plan_id == plan_id).first()
    if orm is None:
        return None
    return _flight_plan_orm_to_pydantic(orm)


def list_flight_plans(db: Session, status: str | None = None, drone_id: str | None = None) -> list[FlightPlan]:
    """비행계획 목록 조회."""
    query = db.query(FlightPlanORM)
    if status:
        query = query.filter(FlightPlanORM.status == status)
    if drone_id:
        query = query.filter(FlightPlanORM.drone_id == drone_id)
    return [_flight_plan_orm_to_pydantic(orm) for orm in query.all()]


def update_flight_plan_status(db: Session, plan_id: str, status: str) -> FlightPlan | None:
    """비행계획 상태 변경."""
    orm = db.query(FlightPlanORM).filter(FlightPlanORM.plan_id == plan_id).first()
    if orm is None:
        return None
    orm.status = status
    db.commit()
    db.refresh(orm)
    return _flight_plan_orm_to_pydantic(orm)


def add_waypoints_to_plan(db: Session, plan_id: str, waypoints: list[dict]) -> FlightPlan | None:
    """비행계획에 경유점 추가.

    Args:
        plan_id: 비행계획 ID.
        waypoints: [{"lat": float, "lon": float, "alt_m": float, "waypoint_type": str, "name": str}] 리스트.
    """
    orm = db.query(FlightPlanORM).filter(FlightPlanORM.plan_id == plan_id).first()
    if orm is None:
        return None
    for i, wp in enumerate(waypoints):
        wp_orm = WaypointORM(
            waypoint_id=_gen_id(),
            flight_plan_id=plan_id,
            name=wp.get("name", f"WP-{i}"),
            lat=wp["lat"],
            lon=wp["lon"],
            alt_m=wp.get("alt_m", 100.0),
            waypoint_type=wp.get("waypoint_type", "ENROUTE"),
            sequence=i,
        )
        db.add(wp_orm)
    db.commit()
    db.refresh(orm)
    return _flight_plan_orm_to_pydantic(orm)


def delete_flight_plan(db: Session, plan_id: str) -> bool:
    """비행계획 삭제 (경유점 cascade 삭제)."""
    orm = db.query(FlightPlanORM).filter(FlightPlanORM.plan_id == plan_id).first()
    if orm is None:
        return False
    db.delete(orm)
    db.commit()
    return True


# ──────────────── AirspaceZone CRUD ────────────────

def create_airspace_zone(db: Session, data: AirspaceZoneCreate) -> AirspaceZone:
    """공역 구역 생성."""
    orm = AirspaceZoneORM(
        zone_id=_gen_id(),
        name=data.name,
        zone_type=data.zone_type.value if hasattr(data.zone_type, 'value') else data.zone_type,
        geometry=data.geometry,
        floor_altitude_m=data.floor_altitude_m,
        ceiling_altitude_m=data.ceiling_altitude_m,
        restrictions=data.restrictions,
    )
    db.add(orm)
    db.commit()
    db.refresh(orm)
    return _airspace_orm_to_pydantic(orm)


def get_airspace_zone(db: Session, zone_id: str) -> AirspaceZone | None:
    """공역 구역 조회."""
    orm = db.query(AirspaceZoneORM).filter(AirspaceZoneORM.zone_id == zone_id).first()
    if orm is None:
        return None
    return _airspace_orm_to_pydantic(orm)


def list_airspace_zones(db: Session, active_only: bool = True) -> list[AirspaceZone]:
    """공역 구역 목록."""
    query = db.query(AirspaceZoneORM)
    if active_only:
        query = query.filter(AirspaceZoneORM.active == True)
    return [_airspace_orm_to_pydantic(orm) for orm in query.all()]


def update_airspace_zone_active(db: Session, zone_id: str, active: bool) -> AirspaceZone | None:
    """공역 구역 활성/비활성."""
    orm = db.query(AirspaceZoneORM).filter(AirspaceZoneORM.zone_id == zone_id).first()
    if orm is None:
        return None
    orm.active = active
    db.commit()
    db.refresh(orm)
    return _airspace_orm_to_pydantic(orm)


def delete_airspace_zone(db: Session, zone_id: str) -> bool:
    """공역 구역 삭제."""
    orm = db.query(AirspaceZoneORM).filter(AirspaceZoneORM.zone_id == zone_id).first()
    if orm is None:
        return False
    db.delete(orm)
    db.commit()
    return True
