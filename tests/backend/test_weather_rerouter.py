"""Tests for weather-based dynamic rerouting."""

import math

import pytest

from models.common import Position3D
from core.weather.analyzer import WeatherAssessment, FlightRestriction
from core.weather.fetcher import WeatherData
from core.weather.rerouter import WeatherRerouter, RerouteResult


# ── helpers ───────────────────────────────────────────────────────────

SEOUL = Position3D(lat=37.5665, lon=126.9780, alt_m=100)


def _assessment(
    restriction: FlightRestriction = FlightRestriction.NONE,
    max_speed: float | None = None,
    rec_alt: float | None = None,
    sep_mult: float = 1.0,
    reasons: list[str] | None = None,
) -> WeatherAssessment:
    return WeatherAssessment(
        restriction=restriction,
        max_allowed_speed_ms=max_speed,
        recommended_altitude_m=rec_alt,
        separation_multiplier=sep_mult,
        reasons=reasons,
    )


def _weather(wind_deg: float = 0.0, wind_speed: float = 0.0) -> WeatherData:
    return WeatherData(
        lat=37.5665,
        lon=126.9780,
        timestamp=1700000000,
        wind_speed_ms=wind_speed,
        wind_deg=wind_deg,
    )


def _path(n: int = 5) -> list[Position3D]:
    """Generate a west-to-east straight path across Seoul."""
    lons = [126.95 + i * 0.01 for i in range(n)]
    return [Position3D(lat=37.5665, lon=lon, alt_m=100) for lon in lons]


def _haversine(a: Position3D, b: Position3D) -> float:
    R = 6_371_000
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    la = math.radians(a.lat)
    lb = math.radians(b.lat)
    h = math.sin(dlat / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


# ── NONE restriction ─────────────────────────────────────────────────


class TestNoneRestriction:
    def test_no_restriction_returns_unchanged(self):
        rr = WeatherRerouter()
        path = _path()
        result = rr.apply(path, _assessment())
        assert result.waypoints == path
        assert result.modified is False

    def test_no_restriction_no_speed_constraint(self):
        rr = WeatherRerouter()
        result = rr.apply(_path(), _assessment())
        assert result.speed_constraint_ms is None

    def test_empty_path_returns_unchanged(self):
        rr = WeatherRerouter()
        result = rr.apply([], _assessment(FlightRestriction.REROUTE))
        assert result.waypoints == []
        assert result.modified is False

    def test_single_waypoint_returns_unchanged(self):
        rr = WeatherRerouter()
        single = [SEOUL]
        result = rr.apply(single, _assessment(FlightRestriction.ALTITUDE_ADJUST, rec_alt=60))
        assert result.waypoints == single
        assert result.modified is False

    def test_restriction_applied_field(self):
        rr = WeatherRerouter()
        result = rr.apply(_path(), _assessment())
        assert result.restriction_applied == FlightRestriction.NONE


# ── SPEED_LIMIT restriction ──────────────────────────────────────────


class TestSpeedLimit:
    def test_speed_limit_preserves_path(self):
        rr = WeatherRerouter()
        path = _path()
        result = rr.apply(path, _assessment(FlightRestriction.SPEED_LIMIT, max_speed=7.5))
        assert result.waypoints == path

    def test_speed_limit_sets_constraint(self):
        rr = WeatherRerouter()
        result = rr.apply(_path(), _assessment(FlightRestriction.SPEED_LIMIT, max_speed=7.5))
        assert result.speed_constraint_ms == 7.5

    def test_speed_limit_not_modified(self):
        rr = WeatherRerouter()
        result = rr.apply(_path(), _assessment(FlightRestriction.SPEED_LIMIT, max_speed=7.5))
        assert result.modified is False
        assert result.restriction_applied == FlightRestriction.SPEED_LIMIT


# ── ALTITUDE_ADJUST restriction ──────────────────────────────────────


class TestAltitudeAdjust:
    def test_altitude_adjusted_to_recommendation(self):
        rr = WeatherRerouter()
        path = _path()
        result = rr.apply(path, _assessment(FlightRestriction.ALTITUDE_ADJUST, rec_alt=60))
        # Intermediate waypoints adjusted, start/end preserved
        for wp in result.waypoints[1:-1]:
            assert wp.alt_m == 60.0

    def test_start_end_preserved(self):
        rr = WeatherRerouter()
        path = _path()
        result = rr.apply(path, _assessment(FlightRestriction.ALTITUDE_ADJUST, rec_alt=60))
        assert result.waypoints[0].alt_m == path[0].alt_m
        assert result.waypoints[-1].alt_m == path[-1].alt_m
        assert result.waypoints[0].lat == path[0].lat
        assert result.waypoints[-1].lat == path[-1].lat

    def test_altitude_clamped_to_min(self):
        rr = WeatherRerouter(min_altitude_m=30.0)
        result = rr.apply(_path(), _assessment(FlightRestriction.ALTITUDE_ADJUST, rec_alt=10))
        for wp in result.waypoints[1:-1]:
            assert wp.alt_m == 30.0

    def test_altitude_clamped_to_max(self):
        rr = WeatherRerouter(max_altitude_m=400.0)
        result = rr.apply(_path(), _assessment(FlightRestriction.ALTITUDE_ADJUST, rec_alt=500))
        for wp in result.waypoints[1:-1]:
            assert wp.alt_m == 400.0

    def test_altitude_adjust_modified_true(self):
        rr = WeatherRerouter()
        result = rr.apply(_path(), _assessment(FlightRestriction.ALTITUDE_ADJUST, rec_alt=60))
        assert result.modified is True
        assert result.restriction_applied == FlightRestriction.ALTITUDE_ADJUST

    def test_no_recommended_altitude_returns_unchanged(self):
        rr = WeatherRerouter()
        path = _path()
        result = rr.apply(path, _assessment(FlightRestriction.ALTITUDE_ADJUST, rec_alt=None))
        assert result.waypoints == path
        assert result.modified is False


# ── REROUTE restriction ──────────────────────────────────────────────


class TestReroute:
    def test_wind_from_north_offsets_west(self):
        """Wind from North (0°): travel South (180°), perp +90° = West (270°)."""
        rr = WeatherRerouter(perpendicular_offset_m=500.0)
        path = _path(3)
        result = rr.apply(path, _assessment(FlightRestriction.REROUTE), _weather(wind_deg=0))

        mid_orig = path[1]
        mid_new = result.waypoints[1]
        # Offset moves westward (lon decreases)
        assert mid_new.lon < mid_orig.lon
        # Lat should be approximately same (pure west offset)
        assert mid_new.lat == pytest.approx(mid_orig.lat, abs=0.001)

    def test_wind_from_east_offsets_north(self):
        """Wind from East (90°): travel West (270°), perp +90° = North (0°)."""
        rr = WeatherRerouter(perpendicular_offset_m=500.0)
        path = _path(3)
        result = rr.apply(path, _assessment(FlightRestriction.REROUTE), _weather(wind_deg=90))

        mid_orig = path[1]
        mid_new = result.waypoints[1]
        # Offset moves northward (lat increases)
        assert mid_new.lat > mid_orig.lat
        # Lon should be approximately same
        assert mid_new.lon == pytest.approx(mid_orig.lon, abs=0.001)

    def test_start_end_preserved(self):
        rr = WeatherRerouter(perpendicular_offset_m=500.0)
        path = _path(5)
        result = rr.apply(path, _assessment(FlightRestriction.REROUTE), _weather(wind_deg=0))

        assert result.waypoints[0].lat == path[0].lat
        assert result.waypoints[0].lon == path[0].lon
        assert result.waypoints[-1].lat == path[-1].lat
        assert result.waypoints[-1].lon == path[-1].lon

    def test_offset_distance_approx(self):
        rr = WeatherRerouter(perpendicular_offset_m=500.0)
        path = _path(3)
        result = rr.apply(path, _assessment(FlightRestriction.REROUTE), _weather(wind_deg=0))

        mid_orig = path[1]
        mid_new = result.waypoints[1]
        dist = _haversine(mid_orig, mid_new)
        assert dist == pytest.approx(500.0, abs=10)

    def test_requires_weather_data(self):
        rr = WeatherRerouter()
        with pytest.raises(ValueError, match="WeatherData is required"):
            rr.apply(_path(), _assessment(FlightRestriction.REROUTE), weather=None)

    def test_reroute_modified_true(self):
        rr = WeatherRerouter()
        result = rr.apply(_path(3), _assessment(FlightRestriction.REROUTE), _weather(wind_deg=45))
        assert result.modified is True
        assert result.restriction_applied == FlightRestriction.REROUTE

    def test_altitude_preserved_during_reroute(self):
        rr = WeatherRerouter()
        path = _path(3)
        result = rr.apply(path, _assessment(FlightRestriction.REROUTE), _weather(wind_deg=0))
        for orig, new in zip(path, result.waypoints):
            assert new.alt_m == orig.alt_m


# ── GROUNDED restriction ─────────────────────────────────────────────


class TestGrounded:
    def test_grounded_returns_empty(self):
        rr = WeatherRerouter()
        result = rr.apply(
            _path(),
            _assessment(FlightRestriction.GROUNDED, reasons=["Wind > 20 m/s"]),
        )
        assert result.waypoints == []

    def test_grounded_modified_true(self):
        rr = WeatherRerouter()
        result = rr.apply(
            _path(),
            _assessment(FlightRestriction.GROUNDED, reasons=["Severe weather"]),
        )
        assert result.modified is True
        assert result.restriction_applied == FlightRestriction.GROUNDED
        assert "GROUNDED" in result.reason
