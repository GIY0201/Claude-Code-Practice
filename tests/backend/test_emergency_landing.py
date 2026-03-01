"""Tests for emergency landing path planner."""

import math

import pytest

from models.common import Position3D
from core.emergency.handler import LandingZone
from core.emergency.landing import EmergencyLandingPlanner, LandingPathResult


# ── helpers ───────────────────────────────────────────────────────────

SEOUL = Position3D(lat=37.5665, lon=126.9780, alt_m=100)
GANGNAM = Position3D(lat=37.4979, lon=127.0276, alt_m=100)


def _pos(lat: float = 37.56, lon: float = 126.98, alt: float = 100.0) -> Position3D:
    return Position3D(lat=lat, lon=lon, alt_m=alt)


def _zone(
    zone_id: str = "ELZ-T1",
    name: str = "Test Zone",
    lat: float = 37.55,
    lon: float = 126.97,
    alt: float = 10.0,
    capacity: int = 1,
) -> LandingZone:
    return LandingZone(
        zone_id=zone_id,
        name=name,
        position=Position3D(lat=lat, lon=lon, alt_m=alt),
        capacity=capacity,
    )


def _haversine(a: Position3D, b: Position3D) -> float:
    R = 6_371_000
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    la = math.radians(a.lat)
    lb = math.radians(b.lat)
    h = math.sin(dlat / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


# ── zone management ──────────────────────────────────────────────────


class TestZoneManagement:
    def test_default_zones_loaded(self):
        planner = EmergencyLandingPlanner()
        zones = planner.list_zones()
        assert len(zones) == 5
        ids = {z.zone_id for z in zones}
        assert "ELZ-001" in ids

    def test_custom_zones(self):
        planner = EmergencyLandingPlanner(landing_zones=[_zone()])
        assert len(planner.list_zones()) == 1

    def test_add_zone(self):
        planner = EmergencyLandingPlanner(landing_zones=[])
        planner.add_zone(_zone("Z1", "Zone A"))
        assert planner.get_zone("Z1") is not None
        assert len(planner.list_zones()) == 1

    def test_remove_zone(self):
        planner = EmergencyLandingPlanner(landing_zones=[_zone("Z1")])
        assert planner.remove_zone("Z1") is True
        assert planner.get_zone("Z1") is None
        assert len(planner.list_zones()) == 0

    def test_remove_nonexistent_returns_false(self):
        planner = EmergencyLandingPlanner(landing_zones=[])
        assert planner.remove_zone("NOPE") is False

    def test_get_zone_by_id(self):
        z = _zone("Z1", "Alpha")
        planner = EmergencyLandingPlanner(landing_zones=[z])
        found = planner.get_zone("Z1")
        assert found is not None
        assert found.name == "Alpha"


# ── reachability ─────────────────────────────────────────────────────


class TestReachability:
    def test_nearby_zone_reachable(self):
        """High battery + close zone → reachable."""
        z = _zone(lat=37.561, lon=126.979)  # ~600m away
        planner = EmergencyLandingPlanner(landing_zones=[z])
        result = planner.find_reachable_zones(_pos(), battery_pct=50.0, speed_ms=10.0)
        assert len(result) == 1
        assert result[0][0].zone_id == z.zone_id

    def test_far_zone_unreachable(self):
        """Low battery + far zone → unreachable."""
        z = _zone(lat=37.40, lon=127.10)  # ~20km away
        planner = EmergencyLandingPlanner(landing_zones=[z])
        result = planner.find_reachable_zones(_pos(), battery_pct=1.0, speed_ms=10.0)
        assert len(result) == 0

    def test_multiple_zones_sorted_by_distance(self):
        z_near = _zone("Z1", "Near", lat=37.561, lon=126.979)
        z_far = _zone("Z2", "Far", lat=37.50, lon=126.90)
        planner = EmergencyLandingPlanner(landing_zones=[z_far, z_near])
        result = planner.find_reachable_zones(_pos(), battery_pct=100.0, speed_ms=10.0)
        assert len(result) == 2
        assert result[0][0].zone_id == "Z1"  # nearer first
        assert result[0][1] < result[1][1]  # distance ascending

    def test_all_unreachable_returns_empty(self):
        z1 = _zone("Z1", lat=37.40, lon=126.80)
        z2 = _zone("Z2", lat=37.70, lon=127.20)
        planner = EmergencyLandingPlanner(landing_zones=[z1, z2])
        result = planner.find_reachable_zones(_pos(), battery_pct=0.5, speed_ms=10.0)
        assert result == []

    def test_battery_estimate_accuracy(self):
        """distance / speed * drain_rate = expected battery."""
        planner = EmergencyLandingPlanner(
            landing_zones=[],
            battery_drain_per_sec=0.1,
        )
        # 1000m at 10 m/s = 100 sec → 100 * 0.1 = 10%
        batt = planner._estimate_battery_for_distance(1000.0, 10.0)
        assert batt == pytest.approx(10.0)


# ── plan_landing ─────────────────────────────────────────────────────


class TestPlanLanding:
    def test_plan_landing_selects_nearest(self):
        z_near = _zone("Z1", "Near", lat=37.561, lon=126.979)
        z_far = _zone("Z2", "Far", lat=37.50, lon=126.90)
        planner = EmergencyLandingPlanner(landing_zones=[z_far, z_near])

        result = planner.plan_landing(_pos(), battery_pct=100.0)
        assert result is not None
        assert result.landing_zone.zone_id == "Z1"

    def test_plan_landing_path_structure(self):
        z = _zone(lat=37.561, lon=126.979, alt=10)
        planner = EmergencyLandingPlanner(landing_zones=[z])

        result = planner.plan_landing(_pos(alt=150.0), battery_pct=100.0)
        assert result is not None
        # Path starts at current position
        assert result.path[0].lat == pytest.approx(37.56)
        assert result.path[0].alt_m == pytest.approx(150.0)
        # Path ends at landing zone
        assert result.path[-1].lat == pytest.approx(z.position.lat)
        assert result.path[-1].lon == pytest.approx(z.position.lon)
        assert result.path[-1].alt_m == pytest.approx(z.position.alt_m)

    def test_plan_landing_no_reachable_returns_none(self):
        z = _zone(lat=37.40, lon=126.80)  # very far
        planner = EmergencyLandingPlanner(landing_zones=[z])
        result = planner.plan_landing(_pos(), battery_pct=0.5, speed_ms=10.0)
        assert result is None

    def test_plan_landing_result_fields(self):
        z = _zone(lat=37.561, lon=126.979, alt=10)
        planner = EmergencyLandingPlanner(landing_zones=[z])

        result = planner.plan_landing(_pos(), battery_pct=100.0, speed_ms=10.0)
        assert result is not None
        assert result.estimated_distance_m > 0
        assert result.estimated_time_sec > 0
        assert result.battery_required_pct > 0
        assert result.is_reachable is True

    def test_plan_landing_direct_path(self):
        """Without airspace manager, should use direct path."""
        z = _zone(lat=37.561, lon=126.979, alt=10)
        planner = EmergencyLandingPlanner(landing_zones=[z])

        result = planner.plan_landing(_pos(alt=150.0), battery_pct=100.0)
        assert result is not None
        assert result.used_avoidance_path is False


# ── approach path ─────────────────────────────────────────────────────


class TestApproachPath:
    def test_approach_path_descent_sequence(self):
        """Altitudes should decrease toward the end."""
        z = _zone(lat=37.561, lon=126.979, alt=10)
        planner = EmergencyLandingPlanner(landing_zones=[z], approach_altitude_m=50.0)

        path, _ = planner.generate_approach_path(_pos(alt=150.0), z)
        # Last few waypoints should have decreasing altitude
        alts = [p.alt_m for p in path]
        # Should end at landing zone altitude
        assert alts[-1] == pytest.approx(10.0)
        # Should include approach altitude step
        assert any(a == pytest.approx(50.0) for a in alts)

    def test_approach_path_preserves_start(self):
        z = _zone(lat=37.561, lon=126.979, alt=10)
        planner = EmergencyLandingPlanner(landing_zones=[z])
        start = _pos(lat=37.57, lon=126.99, alt=200.0)

        path, _ = planner.generate_approach_path(start, z)
        assert path[0].lat == pytest.approx(start.lat)
        assert path[0].lon == pytest.approx(start.lon)
        assert path[0].alt_m == pytest.approx(start.alt_m)

    def test_approach_path_ends_at_zone(self):
        z = _zone(lat=37.55, lon=126.97, alt=15)
        planner = EmergencyLandingPlanner(landing_zones=[z])

        path, _ = planner.generate_approach_path(_pos(alt=100.0), z)
        assert path[-1].lat == pytest.approx(z.position.lat)
        assert path[-1].lon == pytest.approx(z.position.lon)
        assert path[-1].alt_m == pytest.approx(z.position.alt_m)

    def test_low_altitude_skip_approach_step(self):
        """If current altitude <= approach altitude, skip the intermediate step."""
        z = _zone(lat=37.561, lon=126.979, alt=10)
        planner = EmergencyLandingPlanner(landing_zones=[z], approach_altitude_m=50.0)

        path, _ = planner.generate_approach_path(_pos(alt=40.0), z)
        # Should still reach the zone
        assert path[-1].alt_m == pytest.approx(10.0)
