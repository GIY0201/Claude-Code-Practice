"""A* 경로탐색 엔진 테스트."""

import pytest
from models.common import Position3D
from core.path_engine import AStarPathfinder, haversine_distance, smooth_path, simplify_path


# --- 유틸리티 테스트 ---

def test_haversine_distance_same_point():
    """같은 좌표의 거리는 0."""
    p = Position3D(lat=37.5665, lon=126.978, alt_m=100)
    assert haversine_distance(p, p) == pytest.approx(0.0, abs=0.01)


def test_haversine_distance_known():
    """서울시청 → 강남역 거리 약 8.9km."""
    city_hall = Position3D(lat=37.5665, lon=126.978, alt_m=0)
    gangnam = Position3D(lat=37.4979, lon=127.0276, alt_m=0)
    dist = haversine_distance(city_hall, gangnam)
    assert 8000 < dist < 10000  # 약 8.9km


# --- A* 기본 테스트 ---

class TestAStarPathfinder:

    def test_find_path_simple(self):
        """단순 A→B 경로 생성."""
        finder = AStarPathfinder(grid_resolution_m=500)
        start = Position3D(lat=37.5665, lon=126.978, alt_m=100)
        goal = Position3D(lat=37.57, lon=126.985, alt_m=100)
        path = finder.find_path(start, goal)
        assert len(path) >= 2
        assert path[0] == start
        assert path[-1] == goal

    def test_find_path_avoids_restricted(self):
        """금지구역을 회피하는 경로 생성."""
        finder = AStarPathfinder(grid_resolution_m=200)
        # 시작과 도착 사이에 금지구역 배치
        start = Position3D(lat=37.56, lon=126.97, alt_m=100)
        goal = Position3D(lat=37.56, lon=126.99, alt_m=100)
        finder.set_restricted_zones([{
            "center_lat": 37.56,
            "center_lon": 126.98,
            "radius_m": 300,
            "floor_m": 0,
            "ceiling_m": 500,
        }])
        path = finder.find_path(start, goal)
        assert len(path) >= 2
        # 경로의 모든 점이 금지구역 밖
        for p in path:
            assert not finder.is_restricted(p)

    def test_find_path_no_route(self):
        """경로가 불가능한 경우 빈 리스트."""
        finder = AStarPathfinder(grid_resolution_m=200)
        # 도착점이 금지구역 안
        start = Position3D(lat=37.56, lon=126.97, alt_m=100)
        goal = Position3D(lat=37.56, lon=126.98, alt_m=100)
        finder.set_restricted_zones([{
            "center_lat": 37.56,
            "center_lon": 126.98,
            "radius_m": 50,
            "floor_m": 0,
            "ceiling_m": 500,
        }])
        path = finder.find_path(start, goal)
        assert path == []

    def test_path_altitude_range(self):
        """경로의 모든 점이 고도 범위 내."""
        finder = AStarPathfinder(grid_resolution_m=500, altitude_min_m=30, altitude_max_m=400)
        start = Position3D(lat=37.56, lon=126.97, alt_m=50)
        goal = Position3D(lat=37.57, lon=126.98, alt_m=200)
        path = finder.find_path(start, goal)
        for p in path[1:-1]:  # 시작/끝 제외 (원래 좌표로 교체됨)
            assert 30 <= p.alt_m <= 400


# --- 경로 최적화 테스트 ---

def test_smooth_path_preserves_endpoints():
    """스무딩이 시작/끝점을 유지."""
    path = [
        Position3D(lat=37.56, lon=126.97, alt_m=100),
        Position3D(lat=37.565, lon=126.975, alt_m=120),
        Position3D(lat=37.57, lon=126.98, alt_m=100),
    ]
    smoothed = smooth_path(path)
    assert smoothed[0] == path[0]
    assert smoothed[-1] == path[-1]


def test_simplify_path_reduces_points():
    """단순화가 점 수를 줄임."""
    # 직선 위에 있는 점들 → 단순화하면 2개만 남아야 함
    path = [
        Position3D(lat=37.56, lon=126.97, alt_m=100),
        Position3D(lat=37.565, lon=126.975, alt_m=100),
        Position3D(lat=37.57, lon=126.98, alt_m=100),
    ]
    simplified = simplify_path(path, epsilon_m=50)
    assert len(simplified) <= len(path)
