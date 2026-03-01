"""단일 드론 물리 시뮬레이터.

경유점 리스트를 따라 드론을 이동시키며, 매 틱마다 위치·속도·헤딩·배터리를
업데이트하고 Telemetry 객체를 생성한다.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from dataclasses import dataclass, field

from models.common import (
    Position3D, Velocity3D, DroneStatus, GPSFixType, MotorStatus,
    Alert, AlertLevel,
)
from models.telemetry import Telemetry
from core.path_engine.astar import haversine_distance


# 지구 반지름(m) — 좌표↔미터 변환에 사용
_EARTH_R = 6_371_000.0


def _bearing(start: Position3D, end: Position3D) -> float:
    """두 WGS84 좌표 사이 방위각(heading)을 도(°) 단위로 반환한다 (0=N, 시계방향)."""
    lat1 = math.radians(start.lat)
    lat2 = math.radians(end.lat)
    dlon = math.radians(end.lon - start.lon)
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    heading = math.degrees(math.atan2(x, y)) % 360
    return heading


def _distance_3d(a: Position3D, b: Position3D) -> float:
    """3D 거리 (수평 haversine + 수직)."""
    h = haversine_distance(a, b)
    dz = b.alt_m - a.alt_m
    return math.sqrt(h * h + dz * dz)


@dataclass
class DroneSim:
    """단일 드론 비행 시뮬레이터.

    Args:
        drone_id: 드론 고유 ID.
        waypoints: 비행 경유점 리스트 (출발 → ... → 도착).
        speed_ms: 순항 속도 (m/s).
        battery_percent: 초기 배터리 (%).
        battery_drain_per_sec: 초당 배터리 소모량 (%).
        arrival_threshold_m: 경유점 도착 판정 거리 (m).
    """

    drone_id: str
    waypoints: list[Position3D]
    speed_ms: float = 10.0
    battery_percent: float = 100.0
    battery_drain_per_sec: float = 0.05
    arrival_threshold_m: float = 5.0

    # 내부 상태
    _current_wp_idx: int = field(default=1, init=False)
    _position: Position3D = field(default=None, init=False)  # type: ignore[assignment]
    _velocity: Velocity3D = field(default_factory=Velocity3D, init=False)
    _heading: float = field(default=0.0, init=False)
    _status: DroneStatus = field(default=DroneStatus.IDLE, init=False)
    _elapsed_sec: float = field(default=0.0, init=False)
    _completed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if len(self.waypoints) < 2:
            raise ValueError("waypoints must have at least 2 points (departure + destination)")
        self._position = self.waypoints[0].model_copy()
        self._heading = _bearing(self.waypoints[0], self.waypoints[1])
        self._status = DroneStatus.AIRBORNE

    # ──────────── Public API ────────────

    @property
    def position(self) -> Position3D:
        return self._position

    @property
    def status(self) -> DroneStatus:
        return self._status

    @property
    def completed(self) -> bool:
        return self._completed

    @property
    def current_waypoint_index(self) -> int:
        return self._current_wp_idx

    def tick(self, dt_sec: float = 0.1) -> Telemetry:
        """한 프레임을 진행하고 텔레메트리를 반환한다.

        Args:
            dt_sec: 시뮬레이션 시간 간격 (초).

        Returns:
            현재 상태의 Telemetry 객체.
        """
        self._elapsed_sec += dt_sec

        if not self._completed:
            self._move(dt_sec)
            self._drain_battery(dt_sec)

        alerts = self._check_alerts()
        return self._build_telemetry(alerts)

    # ──────────── Movement ────────────

    def _move(self, dt_sec: float) -> None:
        """목표 경유점을 향해 드론을 이동시킨다."""
        target = self.waypoints[self._current_wp_idx]
        dist_to_target = _distance_3d(self._position, target)

        # 도착 판정
        if dist_to_target <= self.arrival_threshold_m:
            self._position = target.model_copy()
            self._advance_waypoint()
            return

        # 이동 거리 계산
        move_dist = self.speed_ms * dt_sec
        if move_dist >= dist_to_target:
            # 오버슈트 방지 — 목표 지점에 정확히 도착
            self._position = target.model_copy()
            self._advance_waypoint()
            return

        # 방위각 + 상승각 계산
        self._heading = _bearing(self._position, target)
        horiz_dist = haversine_distance(self._position, target)
        dz = target.alt_m - self._position.alt_m

        if dist_to_target > 0:
            ratio = move_dist / dist_to_target
        else:
            ratio = 0.0

        # 수평 이동량 (미터 → 도)
        horiz_move = horiz_dist * ratio
        heading_rad = math.radians(self._heading)
        dlat = (horiz_move * math.cos(heading_rad)) / 111_320.0
        dlon = (horiz_move * math.sin(heading_rad)) / (
            111_320.0 * math.cos(math.radians(self._position.lat))
        )
        alt_move = dz * ratio

        new_lat = self._position.lat + dlat
        new_lon = self._position.lon + dlon
        new_alt = max(0.0, self._position.alt_m + alt_move)

        # 속도 벡터 계산 (m/s)
        vx = self.speed_ms * math.sin(heading_rad)  # 동서
        vy = self.speed_ms * math.cos(heading_rad)  # 남북
        vz = dz * ratio / dt_sec if dt_sec > 0 else 0.0

        self._position = Position3D(lat=new_lat, lon=new_lon, alt_m=new_alt)
        self._velocity = Velocity3D(vx=round(vx, 4), vy=round(vy, 4), vz=round(vz, 4))

    def _advance_waypoint(self) -> None:
        """다음 경유점으로 전환. 마지막이면 비행 완료."""
        if self._current_wp_idx >= len(self.waypoints) - 1:
            self._completed = True
            self._status = DroneStatus.LANDED
            self._velocity = Velocity3D()
            return
        self._current_wp_idx += 1
        self._heading = _bearing(self._position, self.waypoints[self._current_wp_idx])

    # ──────────── Battery ────────────

    def _drain_battery(self, dt_sec: float) -> None:
        """배터리 소모."""
        self.battery_percent = max(0.0, self.battery_percent - self.battery_drain_per_sec * dt_sec)
        if self.battery_percent <= 0:
            self._status = DroneStatus.EMERGENCY
            self._completed = True

    # ──────────── Alerts ────────────

    def _check_alerts(self) -> list[Alert]:
        """배터리 수준에 따른 알림 생성."""
        alerts: list[Alert] = []
        if self.battery_percent < 10:
            alerts.append(Alert(level=AlertLevel.CRITICAL, message="Battery critical"))
            self._status = DroneStatus.EMERGENCY
        elif self.battery_percent < 20:
            alerts.append(Alert(level=AlertLevel.WARNING, message="Battery low"))
        return alerts

    # ──────────── Telemetry ────────────

    def _build_telemetry(self, alerts: list[Alert]) -> Telemetry:
        return Telemetry(
            drone_id=self.drone_id,
            timestamp=datetime.now(timezone.utc),
            position=self._position.model_copy(),
            velocity=self._velocity.model_copy(),
            heading=self._heading,
            battery_percent=round(self.battery_percent, 2),
            gps_fix=GPSFixType.FIX_3D,
            signal_strength=100.0,
            motor_status=[MotorStatus.OK] * 4,
            alerts=alerts,
        )
