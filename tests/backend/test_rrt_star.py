"""Tests for RRT* 3D path planner."""

import math
import pytest

from models.common import Position3D
from core.path_engine.rrt_star import (
    RRTStarPathfinder,
    _bspline_smooth,
    _dist3,
    _pos_to_metres,
    _metres_to_pos,
    _segment_collides,
    _Sphere,
)


# ── helpers ─────────────────────────────────────────────────────────

def _haversine(a: Position3D, b: Position3D) -> float:
    """Simple haversine distance (metres)."""
    R = 6_371_000
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    lat1 = math.radians(a.lat)
    lat2 = math.radians(b.lat)
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * R * math.asin(math.sqrt(h))


# ── coordinate conversion ──────────────────────────────────────────

class TestCoordinateConversion:
    def test_roundtrip(self):
        p = Position3D(lat=37.5665, lon=126.978, alt_m=100)
        mx, my, mz = _pos_to_metres(p, ref_lat=37.5665)
        back = _metres_to_pos(mx, my, mz, ref_lat=37.5665)
        assert abs(back.lat - p.lat) < 1e-6
        assert abs(back.lon - p.lon) < 1e-6
        assert back.alt_m == p.alt_m

    def test_altitude_preserved(self):
        p = Position3D(lat=37.0, lon=127.0, alt_m=250)
        mx, my, mz = _pos_to_metres(p, 37.0)
        assert mz == 250


# ── collision detection ─────────────────────────────────────────────

class TestSegmentCollision:
    def test_no_obstacles(self):
        assert not _segment_collides((0, 0, 100), (1000, 1000, 100), [])

    def test_collides_through_zone(self):
        obs = _Sphere(cx=500, cy=500, floor=0, ceiling=200, radius=200)
        assert _segment_collides((0, 0, 100), (1000, 1000, 100), [obs])

    def test_avoids_above(self):
        obs = _Sphere(cx=500, cy=500, floor=0, ceiling=50, radius=200)
        assert not _segment_collides((0, 0, 100), (1000, 1000, 100), [obs])

    def test_avoids_below(self):
        obs = _Sphere(cx=500, cy=500, floor=200, ceiling=400, radius=200)
        assert not _segment_collides((0, 0, 100), (1000, 1000, 100), [obs])


# ── B-spline smoother ──────────────────────────────────────────────

class TestBSpline:
    def test_two_points_unchanged(self):
        pts = [(0, 0, 0), (100, 100, 100)]
        result = _bspline_smooth(pts)
        assert result[0] == pts[0]
        assert result[-1] == pts[-1]

    def test_preserves_endpoints(self):
        pts = [(0, 0, 0), (50, 50, 50), (100, 0, 100)]
        result = _bspline_smooth(pts, num_output=20)
        assert result[0] == pts[0]
        assert result[-1] == pts[-1]

    def test_output_count(self):
        pts = [(0, 0, 0), (50, 50, 50), (100, 0, 100)]
        result = _bspline_smooth(pts, num_output=30)
        assert len(result) == 30

    def test_single_point_returns_single(self):
        pts = [(42, 42, 42)]
        result = _bspline_smooth(pts)
        assert len(result) == 1


# ── RRT* planner ────────────────────────────────────────────────────

class TestRRTStarBasic:
    def test_straight_line_no_obstacles(self):
        planner = RRTStarPathfinder(step_m=300, goal_threshold_m=300)
        start = Position3D(lat=37.56, lon=126.97, alt_m=100)
        goal = Position3D(lat=37.57, lon=126.98, alt_m=100)
        path = planner.find_path(start, goal, max_iterations=5000, seed=42)
        assert len(path) >= 2
        assert abs(path[0].lat - start.lat) < 1e-5
        assert abs(path[-1].lat - goal.lat) < 1e-5

    def test_path_starts_at_start(self):
        planner = RRTStarPathfinder(step_m=300, goal_threshold_m=300)
        start = Position3D(lat=37.55, lon=126.97, alt_m=80)
        goal = Position3D(lat=37.56, lon=126.98, alt_m=80)
        path = planner.find_path(start, goal, max_iterations=5000, seed=1)
        assert abs(path[0].lat - start.lat) < 1e-5
        assert abs(path[0].lon - start.lon) < 1e-5

    def test_path_ends_at_goal(self):
        planner = RRTStarPathfinder(step_m=300, goal_threshold_m=300)
        start = Position3D(lat=37.55, lon=126.97, alt_m=100)
        goal = Position3D(lat=37.56, lon=126.98, alt_m=120)
        path = planner.find_path(start, goal, max_iterations=5000, seed=2)
        assert abs(path[-1].lat - goal.lat) < 1e-5
        assert abs(path[-1].lon - goal.lon) < 1e-5
        assert abs(path[-1].alt_m - goal.alt_m) < 1e-3

    def test_deterministic_with_seed(self):
        planner = RRTStarPathfinder(step_m=300, goal_threshold_m=300)
        start = Position3D(lat=37.55, lon=126.97, alt_m=100)
        goal = Position3D(lat=37.56, lon=126.98, alt_m=100)
        path1 = planner.find_path(start, goal, max_iterations=3000, seed=99)
        path2 = planner.find_path(start, goal, max_iterations=3000, seed=99)
        assert len(path1) == len(path2)
        for a, b in zip(path1, path2):
            assert abs(a.lat - b.lat) < 1e-10
            assert abs(a.lon - b.lon) < 1e-10


class TestRRTStarObstacles:
    def test_avoids_restricted_zone(self):
        planner = RRTStarPathfinder(step_m=200, goal_threshold_m=250)
        # Place obstacle directly between start and goal
        planner.set_restricted_zones([
            {
                "center_lat": 37.565,
                "center_lon": 126.975,
                "radius_m": 600,
                "floor_m": 0,
                "ceiling_m": 400,
            }
        ])
        start = Position3D(lat=37.56, lon=126.97, alt_m=100)
        goal = Position3D(lat=37.57, lon=126.98, alt_m=100)
        path = planner.find_path(start, goal, max_iterations=8000, seed=42)
        assert len(path) >= 3  # Must go around

    def test_fails_when_blocked(self):
        planner = RRTStarPathfinder(step_m=100, goal_threshold_m=100)
        # Huge obstacle covering entire sampling area
        planner.set_restricted_zones([
            {
                "center_lat": 37.565,
                "center_lon": 126.975,
                "radius_m": 50000,
                "floor_m": 0,
                "ceiling_m": 500,
            }
        ])
        start = Position3D(lat=37.56, lon=126.97, alt_m=100)
        goal = Position3D(lat=37.57, lon=126.98, alt_m=100)
        with pytest.raises(ValueError, match="RRT\\* failed"):
            planner.find_path(start, goal, max_iterations=500, seed=1)


class TestRRTStarAltitude:
    def test_altitude_clamped(self):
        planner = RRTStarPathfinder(
            step_m=300, altitude_min_m=50, altitude_max_m=200, goal_threshold_m=300
        )
        start = Position3D(lat=37.56, lon=126.97, alt_m=50)
        goal = Position3D(lat=37.57, lon=126.98, alt_m=200)
        path = planner.find_path(start, goal, max_iterations=5000, seed=42)
        for wp in path:
            assert wp.alt_m >= 50 - 1
            assert wp.alt_m <= 200 + 1


class TestRRTStarSmooth:
    def test_smooth_path_basic(self):
        planner = RRTStarPathfinder(step_m=300, goal_threshold_m=300)
        start = Position3D(lat=37.55, lon=126.97, alt_m=100)
        goal = Position3D(lat=37.56, lon=126.98, alt_m=100)
        path = planner.find_smooth_path(
            start, goal, max_iterations=5000, seed=42, num_smooth_points=20
        )
        assert len(path) >= 2
        assert abs(path[0].lat - start.lat) < 1e-5
        assert abs(path[-1].lat - goal.lat) < 1e-5

    def test_smooth_preserves_endpoints(self):
        planner = RRTStarPathfinder(step_m=300, goal_threshold_m=300)
        start = Position3D(lat=37.55, lon=126.97, alt_m=80)
        goal = Position3D(lat=37.57, lon=126.99, alt_m=120)
        path = planner.find_smooth_path(start, goal, max_iterations=5000, seed=10)
        assert abs(path[0].lat - start.lat) < 1e-5
        assert abs(path[0].lon - start.lon) < 1e-5
        assert abs(path[-1].lat - goal.lat) < 1e-5
        assert abs(path[-1].lon - goal.lon) < 1e-5
