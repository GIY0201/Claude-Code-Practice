"""성능 메트릭 수집기.

시뮬레이션 중 텔레메트리·충돌·회피 명령을 기록하고,
시뮬레이션 완료 시 전체 요약을 생성한다.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from models.common import Position3D
from models.telemetry import Telemetry
from models.metrics import MetricsSummary, DroneMetrics


def _haversine_m(p1: Position3D, p2: Position3D) -> float:
    """두 WGS84 좌표 간 Haversine 거리 (m)."""
    R = 6_371_000
    lat1, lat2 = math.radians(p1.lat), math.radians(p2.lat)
    dlat = lat2 - lat1
    dlon = math.radians(p2.lon - p1.lon)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class _DroneTracker:
    """개별 드론 추적 상태."""
    drone_id: str
    start_position: Position3D | None = None
    last_position: Position3D | None = None
    total_distance_m: float = 0.0
    start_battery: float = 100.0
    last_battery: float = 100.0
    start_time: float = 0.0
    last_time: float = 0.0
    completed: bool = False


@dataclass
class MetricsCollector:
    """시뮬레이션 성능 메트릭 수집기."""

    _trackers: dict[str, _DroneTracker] = field(default_factory=dict, init=False)
    _total_conflicts: int = field(default=0, init=False)
    _total_avoidance: int = field(default=0, init=False)
    _conflict_timestamps: list[float] = field(default_factory=list, init=False)
    _avoidance_timestamps: list[float] = field(default_factory=list, init=False)
    _total_drones: int = field(default=0, init=False)
    _completed_drones: int = field(default=0, init=False)

    def record_tick(
        self,
        telemetry_list: list[Telemetry],
        conflict_count: int = 0,
        avoidance_count: int = 0,
    ) -> None:
        """한 틱의 텔레메트리와 충돌/회피 정보를 기록한다."""
        now = time.monotonic()

        for telem in telemetry_list:
            tracker = self._trackers.get(telem.drone_id)
            if tracker is None:
                tracker = _DroneTracker(
                    drone_id=telem.drone_id,
                    start_position=telem.position,
                    last_position=telem.position,
                    start_battery=telem.battery_percent,
                    last_battery=telem.battery_percent,
                    start_time=now,
                    last_time=now,
                )
                self._trackers[telem.drone_id] = tracker
                self._total_drones += 1
            else:
                # 거리 누적
                if tracker.last_position:
                    dist = _haversine_m(tracker.last_position, telem.position)
                    tracker.total_distance_m += dist
                tracker.last_position = telem.position
                tracker.last_battery = telem.battery_percent
                tracker.last_time = now

        if conflict_count > 0:
            self._total_conflicts += conflict_count
            self._conflict_timestamps.append(now)

        if avoidance_count > 0:
            self._total_avoidance += avoidance_count
            self._avoidance_timestamps.append(now)

    def record_completion(self, drone_id: str) -> None:
        """드론 미션 완료를 기록한다."""
        tracker = self._trackers.get(drone_id)
        if tracker and not tracker.completed:
            tracker.completed = True
            tracker.last_time = time.monotonic()
            self._completed_drones += 1

    def get_summary(self) -> MetricsSummary:
        """전체 메트릭 요약을 생성한다."""
        if not self._trackers:
            return MetricsSummary()

        drone_metrics: dict[str, DroneMetrics] = {}
        total_distance = 0.0
        total_route_eff = 0.0
        total_flight_time = 0.0
        total_battery_consumed = 0.0
        valid_route_count = 0

        for did, tracker in self._trackers.items():
            flight_time = tracker.last_time - tracker.start_time
            battery_consumed = tracker.start_battery - tracker.last_battery

            # 직선 거리 (이상적 경로)
            ideal_dist = 0.0
            if tracker.start_position and tracker.last_position:
                ideal_dist = _haversine_m(tracker.start_position, tracker.last_position)

            # 경로 효율: ideal / actual (1에 가까울수록 효율적)
            route_eff = 0.0
            if tracker.total_distance_m > 0:
                route_eff = min(ideal_dist / tracker.total_distance_m, 1.0)
                valid_route_count += 1
                total_route_eff += route_eff

            dm = DroneMetrics(
                drone_id=did,
                total_distance_m=round(tracker.total_distance_m, 1),
                ideal_distance_m=round(ideal_dist, 1),
                route_efficiency=round(route_eff, 4),
                battery_consumed=round(battery_consumed, 2),
                flight_time_sec=round(flight_time, 2),
                completed=tracker.completed,
            )
            drone_metrics[did] = dm
            total_distance += tracker.total_distance_m
            total_flight_time += flight_time
            total_battery_consumed += battery_consumed

        num_drones = len(self._trackers)

        # 충돌 회피율
        if self._total_conflicts > 0:
            avoidance_rate = min(self._total_avoidance / self._total_conflicts, 1.0)
        else:
            avoidance_rate = 1.0

        # 평균 경로 효율
        avg_route_eff = total_route_eff / valid_route_count if valid_route_count > 0 else 1.0

        # 평균 응답 시간 (충돌→회피 사이 시간)
        avg_response_ms = 0.0
        if self._conflict_timestamps and self._avoidance_timestamps:
            # 간단히 평균 간격 계산
            response_times = []
            avoid_idx = 0
            for ct in self._conflict_timestamps:
                while avoid_idx < len(self._avoidance_timestamps) and self._avoidance_timestamps[avoid_idx] < ct:
                    avoid_idx += 1
                if avoid_idx < len(self._avoidance_timestamps):
                    response_times.append(
                        (self._avoidance_timestamps[avoid_idx] - ct) * 1000
                    )
            if response_times:
                avg_response_ms = sum(response_times) / len(response_times)

        # 에너지 효율 (m/%)
        energy_eff = 0.0
        if total_battery_consumed > 0:
            energy_eff = total_distance / total_battery_consumed

        # 미션 완료율
        mission_rate = self._completed_drones / self._total_drones if self._total_drones > 0 else 0.0

        # 평균 비행 시간
        avg_flight = total_flight_time / num_drones if num_drones > 0 else 0.0

        return MetricsSummary(
            collision_avoidance_rate=round(avoidance_rate, 4),
            route_efficiency=round(avg_route_eff, 4),
            avg_response_time_ms=round(avg_response_ms, 2),
            energy_efficiency=round(energy_eff, 2),
            mission_completion_rate=round(mission_rate, 4),
            avg_flight_time_sec=round(avg_flight, 2),
            total_conflicts_detected=self._total_conflicts,
            total_avoidance_maneuvers=self._total_avoidance,
            total_distance_m=round(total_distance, 1),
            drone_metrics=drone_metrics,
        )

    def reset(self) -> None:
        """수집기를 초기화한다."""
        self._trackers.clear()
        self._total_conflicts = 0
        self._total_avoidance = 0
        self._conflict_timestamps.clear()
        self._avoidance_timestamps.clear()
        self._total_drones = 0
        self._completed_drones = 0
