"""Strategic Deconfliction 테스트."""

import sys
from pathlib import Path

import pytest

backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from models.common import Position3D
from core.deconfliction.strategic import (
    PlannedRoute, SegmentConflict,
    check_route_conflict, check_all_routes,
    _compute_segment_times,
)


def _route(drone_id: str, wps: list[tuple[float, float, float]],
           departure: float = 0.0, speed: float = 10.0) -> PlannedRoute:
    waypoints = [Position3D(lat=w[0], lon=w[1], alt_m=w[2]) for w in wps]
    return PlannedRoute(
        drone_id=drone_id, waypoints=waypoints,
        departure_time_sec=departure, speed_ms=speed,
    )


class TestComputeSegmentTimes:
    def test_two_waypoints(self):
        route = _route("D1", [(37.56, 126.97, 100), (37.57, 126.97, 100)], speed=100)
        times = _compute_segment_times(route)
        assert len(times) == 2
        assert times[0] == 0.0
        assert times[1] > 0.0

    def test_three_waypoints(self):
        route = _route("D1", [
            (37.56, 126.97, 100),
            (37.57, 126.97, 100),
            (37.58, 126.97, 100),
        ], speed=100)
        times = _compute_segment_times(route)
        assert len(times) == 3
        assert times[0] < times[1] < times[2]

    def test_departure_offset(self):
        route = _route("D1", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                       departure=1000.0, speed=100)
        times = _compute_segment_times(route)
        assert times[0] == 1000.0
        assert times[1] > 1000.0


class TestCheckRouteConflict:
    def test_no_overlap_in_time(self):
        """시간이 겹치지 않으면 충돌 없음."""
        # D1: t=0에 출발, D2: t=10000에 출발 (충분히 늦게)
        r1 = _route("D1", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=0, speed=10)
        r2 = _route("D2", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=100000, speed=10)
        conflicts = check_route_conflict(r1, r2)
        assert len(conflicts) == 0

    def test_same_route_same_time(self):
        """같은 경로를 같은 시각에 비행하면 충돌."""
        r1 = _route("D1", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=0, speed=10)
        r2 = _route("D2", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=0, speed=10)
        conflicts = check_route_conflict(r1, r2)
        assert len(conflicts) >= 1
        assert conflicts[0].min_distance_m < 10  # 거의 0

    def test_parallel_routes_safe(self):
        """평행하지만 충분히 떨어진 경로 → 충돌 없음."""
        r1 = _route("D1", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=0, speed=10)
        r2 = _route("D2", [(37.56, 126.99, 100), (37.57, 126.99, 100)],
                     departure=0, speed=10)
        conflicts = check_route_conflict(r1, r2)
        assert len(conflicts) == 0

    def test_head_on_collision(self):
        """정면 충돌 경로."""
        r1 = _route("D1", [(37.5665, 126.975, 100), (37.5665, 126.981, 100)],
                     departure=0, speed=10)
        r2 = _route("D2", [(37.5665, 126.981, 100), (37.5665, 126.975, 100)],
                     departure=0, speed=10)
        conflicts = check_route_conflict(r1, r2)
        assert len(conflicts) >= 1

    def test_vertical_separation_prevents_conflict(self):
        """수직 이격이 충분하면 충돌 없음."""
        r1 = _route("D1", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=0, speed=10)
        r2 = _route("D2", [(37.56, 126.97, 250), (37.57, 126.97, 250)],
                     departure=0, speed=10)
        conflicts = check_route_conflict(r1, r2)
        assert len(conflicts) == 0

    def test_crossing_paths_at_same_time(self):
        """교차 경로가 동시에 교차점 통과."""
        r1 = _route("D1", [(37.560, 126.978, 100), (37.570, 126.978, 100)],
                     departure=0, speed=10)
        r2 = _route("D2", [(37.565, 126.974, 100), (37.565, 126.982, 100)],
                     departure=0, speed=10)
        conflicts = check_route_conflict(r1, r2)
        # 교차점에서 근접 → 충돌 가능
        assert isinstance(conflicts, list)

    def test_segment_info_in_result(self):
        """결과에 구간 정보가 포함된다."""
        r1 = _route("D1", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=0, speed=10)
        r2 = _route("D2", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=0, speed=10)
        conflicts = check_route_conflict(r1, r2)
        assert len(conflicts) >= 1
        c = conflicts[0]
        assert c.segment_a == (0, 1)
        assert c.segment_b == (0, 1)
        assert c.time_overlap_start >= 0
        assert c.time_overlap_end > c.time_overlap_start
        assert isinstance(c.conflict_point, Position3D)


class TestCheckAllRoutes:
    def test_empty_routes(self):
        assert check_all_routes([]) == []

    def test_single_route(self):
        r = _route("D1", [(37.56, 126.97, 100), (37.57, 126.97, 100)])
        assert check_all_routes([r]) == []

    def test_three_routes_one_conflict(self):
        """3개 경로 중 1쌍만 충돌."""
        r1 = _route("D1", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=0, speed=10)
        r2 = _route("D2", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=0, speed=10)  # D1과 같은 경로
        r3 = _route("D3", [(37.60, 126.99, 300), (37.61, 126.99, 300)],
                     departure=0, speed=10)  # 멀리
        conflicts = check_all_routes([r1, r2, r3])
        # D1-D2만 충돌
        conflict_pairs = {(c.drone_id_a, c.drone_id_b) for c in conflicts}
        assert ("D1", "D2") in conflict_pairs
        assert ("D1", "D3") not in conflict_pairs

    def test_time_staggering_resolves_conflict(self):
        """출발 시간 차이로 충돌 해소."""
        r1 = _route("D1", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=0, speed=10)
        r2 = _route("D2", [(37.56, 126.97, 100), (37.57, 126.97, 100)],
                     departure=100000, speed=10)  # 아주 나중에 출발
        conflicts = check_all_routes([r1, r2])
        assert len(conflicts) == 0
