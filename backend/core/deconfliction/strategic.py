"""Strategic Deconfliction — 사전 비행 4D 시공간 충돌 검사.

비행 전에 계획된 경로(경유점 + 출발시각 + 속도)를 기반으로,
두 경로가 시간적·공간적으로 근접하는 구간이 있는지 검사한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from models.common import Position3D
from core.path_engine.astar import haversine_distance


@dataclass
class PlannedRoute:
    """사전 비행 계획 경로."""
    drone_id: str
    waypoints: list[Position3D]
    departure_time_sec: float  # 에포크 기준 출발 시각 (초)
    speed_ms: float = 10.0


@dataclass
class SegmentConflict:
    """경로 구간 충돌 결과."""
    drone_id_a: str
    drone_id_b: str
    segment_a: tuple[int, int]  # (from_wp_idx, to_wp_idx)
    segment_b: tuple[int, int]
    min_distance_m: float
    time_overlap_start: float
    time_overlap_end: float
    conflict_point: Position3D  # 최소 거리 발생 위치 (A 기준)


def _segment_length(a: Position3D, b: Position3D) -> float:
    """두 경유점 사이 3D 거리 (m)."""
    h = haversine_distance(a, b)
    dz = b.alt_m - a.alt_m
    return math.sqrt(h * h + dz * dz)


def _interpolate(a: Position3D, b: Position3D, t: float) -> Position3D:
    """두 점 사이 선형 보간 (t: 0~1)."""
    return Position3D(
        lat=a.lat + (b.lat - a.lat) * t,
        lon=a.lon + (b.lon - a.lon) * t,
        alt_m=a.alt_m + (b.alt_m - a.alt_m) * t,
    )


def _distance_3d(a: Position3D, b: Position3D) -> float:
    h = haversine_distance(a, b)
    dz = b.alt_m - a.alt_m
    return math.sqrt(h * h + dz * dz)


def _compute_segment_times(route: PlannedRoute) -> list[float]:
    """각 경유점 도착 시각을 계산한다.

    Returns:
        경유점별 절대 도착 시각 리스트 (초).
    """
    times = [route.departure_time_sec]
    for i in range(1, len(route.waypoints)):
        seg_len = _segment_length(route.waypoints[i - 1], route.waypoints[i])
        duration = seg_len / route.speed_ms if route.speed_ms > 0 else 0.0
        times.append(times[-1] + duration)
    return times


def check_route_conflict(
    route_a: PlannedRoute,
    route_b: PlannedRoute,
    separation_h_m: float = 100.0,
    separation_v_m: float = 30.0,
    time_samples: int = 10,
) -> list[SegmentConflict]:
    """두 계획 경로 간 4D 충돌을 검사한다.

    각 경로를 시간 기반으로 분해하여, 동시에 근접하는 구간을 찾는다.

    Args:
        route_a, route_b: 계획 경로.
        separation_h_m: 수평 최소 이격거리.
        separation_v_m: 수직 최소 이격거리.
        time_samples: 구간당 샘플 수 (정밀도).

    Returns:
        충돌 구간 목록.
    """
    times_a = _compute_segment_times(route_a)
    times_b = _compute_segment_times(route_b)

    conflicts: list[SegmentConflict] = []

    for i in range(len(route_a.waypoints) - 1):
        t_a_start = times_a[i]
        t_a_end = times_a[i + 1]

        for j in range(len(route_b.waypoints) - 1):
            t_b_start = times_b[j]
            t_b_end = times_b[j + 1]

            # 시간 겹침 확인
            overlap_start = max(t_a_start, t_b_start)
            overlap_end = min(t_a_end, t_b_end)
            if overlap_start >= overlap_end:
                continue

            # 겹치는 시간 구간에서 거리 샘플링
            min_dist = float("inf")
            min_point = route_a.waypoints[i]

            for s in range(time_samples + 1):
                t = overlap_start + (overlap_end - overlap_start) * s / time_samples

                # A 경로에서의 위치
                if t_a_end > t_a_start:
                    ratio_a = (t - t_a_start) / (t_a_end - t_a_start)
                else:
                    ratio_a = 0.0
                pos_a = _interpolate(route_a.waypoints[i], route_a.waypoints[i + 1], ratio_a)

                # B 경로에서의 위치
                if t_b_end > t_b_start:
                    ratio_b = (t - t_b_start) / (t_b_end - t_b_start)
                else:
                    ratio_b = 0.0
                pos_b = _interpolate(route_b.waypoints[j], route_b.waypoints[j + 1], ratio_b)

                dist = _distance_3d(pos_a, pos_b)
                if dist < min_dist:
                    min_dist = dist
                    min_point = pos_a

            # 이격거리 위반 검사
            h_dist = haversine_distance(min_point,
                                        Position3D(lat=min_point.lat, lon=min_point.lon, alt_m=0))
            # 간이 검사: 3D 거리 기반
            v_dist = abs(min_point.alt_m -
                         _interpolate(route_b.waypoints[j], route_b.waypoints[j + 1], 0.5).alt_m)

            if min_dist < math.sqrt(separation_h_m ** 2 + separation_v_m ** 2):
                conflicts.append(SegmentConflict(
                    drone_id_a=route_a.drone_id,
                    drone_id_b=route_b.drone_id,
                    segment_a=(i, i + 1),
                    segment_b=(j, j + 1),
                    min_distance_m=round(min_dist, 2),
                    time_overlap_start=round(overlap_start, 2),
                    time_overlap_end=round(overlap_end, 2),
                    conflict_point=min_point,
                ))

    return conflicts


def check_all_routes(
    routes: list[PlannedRoute],
    separation_h_m: float = 100.0,
    separation_v_m: float = 30.0,
) -> list[SegmentConflict]:
    """전체 계획 경로 간 충돌을 검사한다.

    Args:
        routes: 계획 경로 리스트.
        separation_h_m: 수평 최소 이격거리.
        separation_v_m: 수직 최소 이격거리.

    Returns:
        모든 충돌 구간 목록.
    """
    all_conflicts: list[SegmentConflict] = []
    for i in range(len(routes)):
        for j in range(i + 1, len(routes)):
            conflicts = check_route_conflict(
                routes[i], routes[j],
                separation_h_m, separation_v_m,
            )
            all_conflicts.extend(conflicts)
    return all_conflicts
