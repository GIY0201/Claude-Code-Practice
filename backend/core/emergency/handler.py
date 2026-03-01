"""Emergency procedure handler.

Executes emergency responses based on detected conditions:
- Battery low → find nearest landing zone, generate direct route
- Battery critical → immediate descent to nearest safe point
- Comms lost → maintain plan → return to launch → descend
- GPS degraded → expand separation, safe landing if persistent
- Motor failure → immediate emergency landing
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from models.common import Position3D, Priority
from core.emergency.detector import EmergencyEvent, EmergencyType, EmergencySeverity


class EmergencyAction(str, Enum):
    """High-level action to execute."""

    DIVERT_TO_LANDING = "DIVERT_TO_LANDING"
    IMMEDIATE_DESCENT = "IMMEDIATE_DESCENT"
    RETURN_TO_LAUNCH = "RETURN_TO_LAUNCH"
    HOLD_AND_DESCEND = "HOLD_AND_DESCEND"
    EXPAND_SEPARATION = "EXPAND_SEPARATION"
    CONTINUE_PLAN = "CONTINUE_PLAN"


@dataclass
class LandingZone:
    """Pre-registered safe landing location."""

    zone_id: str
    name: str
    position: Position3D
    capacity: int = 1  # how many drones can land simultaneously


@dataclass
class EmergencyResponse:
    """Actionable response to an emergency event."""

    drone_id: str
    action: EmergencyAction
    priority: Priority  # drone priority override
    landing_zone: LandingZone | None = None
    route: list[Position3D] | None = None
    separation_multiplier: float = 1.0
    message: str = ""


# ── helpers ─────────────────────────────────────────────────────────

def _haversine(a: Position3D, b: Position3D) -> float:
    """Horizontal distance in metres (Haversine)."""
    R = 6_371_000
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    la = math.radians(a.lat)
    lb = math.radians(b.lat)
    h = math.sin(dlat / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _distance_3d(a: Position3D, b: Position3D) -> float:
    h = _haversine(a, b)
    dz = b.alt_m - a.alt_m
    return math.sqrt(h * h + dz * dz)


def _direct_route(
    current: Position3D,
    target: Position3D,
    descent_alt_m: float = 30.0,
) -> list[Position3D]:
    """Generate a minimal energy direct route: fly level → descend."""
    mid = Position3D(lat=target.lat, lon=target.lon, alt_m=current.alt_m)
    landing = Position3D(lat=target.lat, lon=target.lon, alt_m=descent_alt_m)
    return [current, mid, landing]


# ── landing zone registry ──────────────────────────────────────────

# Default Seoul emergency landing zones
_DEFAULT_ZONES = [
    LandingZone(
        zone_id="ELZ-001",
        name="여의도 공원",
        position=Position3D(lat=37.5249, lon=126.9222, alt_m=10),
    ),
    LandingZone(
        zone_id="ELZ-002",
        name="한강 반포지구",
        position=Position3D(lat=37.5107, lon=126.9950, alt_m=10),
    ),
    LandingZone(
        zone_id="ELZ-003",
        name="올림픽공원",
        position=Position3D(lat=37.5209, lon=127.1230, alt_m=15),
    ),
    LandingZone(
        zone_id="ELZ-004",
        name="상암 월드컵공원",
        position=Position3D(lat=37.5681, lon=126.8975, alt_m=12),
    ),
    LandingZone(
        zone_id="ELZ-005",
        name="남산 헬기장",
        position=Position3D(lat=37.5512, lon=126.9882, alt_m=240),
    ),
]


class EmergencyHandler:
    """Determine and generate emergency responses.

    Parameters
    ----------
    landing_zones : list[LandingZone] | None
        Available emergency landing sites.  Defaults to Seoul presets.
    launch_positions : dict[str, Position3D] | None
        Per-drone launch (home) positions for RTL.
    """

    def __init__(
        self,
        landing_zones: list[LandingZone] | None = None,
        launch_positions: dict[str, Position3D] | None = None,
    ) -> None:
        self.landing_zones = landing_zones if landing_zones is not None else list(_DEFAULT_ZONES)
        self.launch_positions: dict[str, Position3D] = launch_positions or {}

    def set_launch_position(self, drone_id: str, pos: Position3D) -> None:
        self.launch_positions[drone_id] = pos

    def find_nearest_landing_zone(self, position: Position3D) -> LandingZone | None:
        """Return the closest landing zone to *position*."""
        if not self.landing_zones:
            return None
        return min(
            self.landing_zones,
            key=lambda z: _haversine(position, z.position),
        )

    def handle(
        self,
        event: EmergencyEvent,
        current_position: Position3D,
    ) -> EmergencyResponse:
        """Generate an :class:`EmergencyResponse` for the given event."""
        etype = event.emergency_type

        if etype == EmergencyType.BATTERY_CRITICAL:
            return self._handle_battery_critical(event, current_position)
        elif etype == EmergencyType.BATTERY_LOW:
            return self._handle_battery_low(event, current_position)
        elif etype == EmergencyType.COMMS_CRITICAL:
            return self._handle_comms_critical(event, current_position)
        elif etype == EmergencyType.COMMS_LOST:
            return self._handle_comms_lost(event, current_position)
        elif etype == EmergencyType.GPS_DEGRADED:
            return self._handle_gps_degraded(event, current_position)
        elif etype == EmergencyType.MOTOR_FAILURE:
            return self._handle_motor_failure(event, current_position)
        else:
            return EmergencyResponse(
                drone_id=event.drone_id,
                action=EmergencyAction.CONTINUE_PLAN,
                priority=Priority.NORMAL,
                message="Unknown emergency type — continuing plan",
            )

    # ── specific handlers ───────────────────────────────────────────

    def _handle_battery_critical(
        self, event: EmergencyEvent, pos: Position3D
    ) -> EmergencyResponse:
        lz = self.find_nearest_landing_zone(pos)
        if lz is None:
            return EmergencyResponse(
                drone_id=event.drone_id,
                action=EmergencyAction.IMMEDIATE_DESCENT,
                priority=Priority.EMERGENCY,
                route=[pos, Position3D(lat=pos.lat, lon=pos.lon, alt_m=30)],
                message="Battery critical — immediate descent (no landing zone)",
            )
        route = _direct_route(pos, lz.position)
        return EmergencyResponse(
            drone_id=event.drone_id,
            action=EmergencyAction.IMMEDIATE_DESCENT,
            priority=Priority.EMERGENCY,
            landing_zone=lz,
            route=route,
            message=f"Battery critical — emergency landing at {lz.name}",
        )

    def _handle_battery_low(
        self, event: EmergencyEvent, pos: Position3D
    ) -> EmergencyResponse:
        lz = self.find_nearest_landing_zone(pos)
        if lz is None:
            return EmergencyResponse(
                drone_id=event.drone_id,
                action=EmergencyAction.RETURN_TO_LAUNCH,
                priority=Priority.HIGH,
                message="Battery low — return to launch (no landing zone)",
            )
        route = _direct_route(pos, lz.position)
        return EmergencyResponse(
            drone_id=event.drone_id,
            action=EmergencyAction.DIVERT_TO_LANDING,
            priority=Priority.HIGH,
            landing_zone=lz,
            route=route,
            message=f"Battery low — diverting to {lz.name}",
        )

    def _handle_comms_lost(
        self, event: EmergencyEvent, pos: Position3D
    ) -> EmergencyResponse:
        # Per spec: maintain flight plan for first 30s
        return EmergencyResponse(
            drone_id=event.drone_id,
            action=EmergencyAction.CONTINUE_PLAN,
            priority=Priority.HIGH,
            message="Communications lost — maintaining current flight plan",
        )

    def _handle_comms_critical(
        self, event: EmergencyEvent, pos: Position3D
    ) -> EmergencyResponse:
        # Per spec: 60s+ → return to launch or hold-and-descend
        launch = self.launch_positions.get(event.drone_id)
        if launch is not None:
            route = _direct_route(pos, launch)
            return EmergencyResponse(
                drone_id=event.drone_id,
                action=EmergencyAction.RETURN_TO_LAUNCH,
                priority=Priority.EMERGENCY,
                route=route,
                message="Communications critical — returning to launch",
            )
        return EmergencyResponse(
            drone_id=event.drone_id,
            action=EmergencyAction.HOLD_AND_DESCEND,
            priority=Priority.EMERGENCY,
            route=[pos, Position3D(lat=pos.lat, lon=pos.lon, alt_m=30)],
            message="Communications critical — hold and descend",
        )

    def _handle_gps_degraded(
        self, event: EmergencyEvent, pos: Position3D
    ) -> EmergencyResponse:
        return EmergencyResponse(
            drone_id=event.drone_id,
            action=EmergencyAction.EXPAND_SEPARATION,
            priority=Priority.HIGH,
            separation_multiplier=2.0,
            message="GPS degraded — separation doubled, prepare for safe landing",
        )

    def _handle_motor_failure(
        self, event: EmergencyEvent, pos: Position3D
    ) -> EmergencyResponse:
        lz = self.find_nearest_landing_zone(pos)
        route = _direct_route(pos, lz.position) if lz else [
            pos,
            Position3D(lat=pos.lat, lon=pos.lon, alt_m=30),
        ]
        return EmergencyResponse(
            drone_id=event.drone_id,
            action=EmergencyAction.IMMEDIATE_DESCENT,
            priority=Priority.EMERGENCY,
            landing_zone=lz,
            route=route,
            message=f"Motor failure — emergency landing"
            + (f" at {lz.name}" if lz else ""),
        )
