"""Tests for weather fetcher and analyzer."""

import time
import pytest

from core.weather.fetcher import WeatherData, WeatherFetcher, _parse_owm_response
from core.weather.analyzer import (
    FlightRestriction,
    WeatherAnalyzer,
    WeatherAssessment,
)


# ── WeatherData parsing ────────────────────────────────────────────


class TestParseOWM:
    def test_parse_full_response(self):
        raw = {
            "coord": {"lat": 37.57, "lon": 126.98},
            "weather": [{"main": "Rain", "description": "light rain"}],
            "main": {"temp": 12, "humidity": 80, "pressure": 1010},
            "wind": {"speed": 8.5, "deg": 180, "gust": 12.0},
            "visibility": 5000,
            "rain": {"1h": 3.2},
            "snow": {},
            "dt": 1700000000,
        }
        wd = _parse_owm_response(raw)
        assert wd.lat == 37.57
        assert wd.lon == 126.98
        assert wd.wind_speed_ms == 8.5
        assert wd.wind_gust_ms == 12.0
        assert wd.rain_1h_mm == 3.2
        assert wd.visibility_m == 5000
        assert wd.condition == "Rain"

    def test_parse_minimal_response(self):
        raw = {"coord": {}, "weather": [{}], "main": {}, "wind": {}}
        wd = _parse_owm_response(raw)
        assert wd.wind_speed_ms == 0
        assert wd.visibility_m == 10_000

    def test_parse_snow(self):
        raw = {
            "coord": {"lat": 37.0, "lon": 127.0},
            "weather": [{"main": "Snow", "description": "heavy snow"}],
            "main": {"temp": -2},
            "wind": {"speed": 5},
            "snow": {"1h": 8.0},
        }
        wd = _parse_owm_response(raw)
        assert wd.snow_1h_mm == 8.0
        assert wd.condition == "Snow"


# ── WeatherFetcher mock mode ───────────────────────────────────────


class TestWeatherFetcher:
    def test_mock_mode_no_key(self):
        f = WeatherFetcher(api_key="")
        assert f.is_mock

    def test_mock_returns_clear(self):
        f = WeatherFetcher(api_key="")
        wd = f.get_weather(37.5665, 126.978)
        assert isinstance(wd, WeatherData)
        assert wd.condition == "Clear"
        assert wd.wind_speed_ms > 0

    def test_mock_uses_coordinates(self):
        f = WeatherFetcher(api_key="")
        wd = f.get_weather(35.0, 128.0)
        assert wd.lat == 35.0
        assert wd.lon == 128.0

    def test_cache_returns_same(self):
        f = WeatherFetcher(api_key="", cache_ttl_sec=60)
        # Even mock mode should be consistent per call
        wd1 = f.get_weather(37.5665, 126.978)
        wd2 = f.get_weather(37.5665, 126.978)
        assert wd1.condition == wd2.condition

    def test_clear_cache(self):
        f = WeatherFetcher(api_key="")
        f.get_weather(37.0, 127.0)
        f.clear_cache()
        assert len(f._cache) == 0


# ── WeatherAnalyzer ─────────────────────────────────────────────────


def _make_weather(**kwargs) -> WeatherData:
    defaults = dict(
        lat=37.57,
        lon=126.98,
        timestamp=time.time(),
        wind_speed_ms=3.0,
        wind_deg=0,
        wind_gust_ms=3.0,
        rain_1h_mm=0,
        snow_1h_mm=0,
        visibility_m=10_000,
        temperature_c=20,
        humidity_pct=50,
        pressure_hpa=1013,
        condition="Clear",
        description="clear sky",
    )
    defaults.update(kwargs)
    return WeatherData(**defaults)


class TestAnalyzerClear:
    def test_clear_weather_no_restriction(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather())
        assert result.restriction == FlightRestriction.NONE
        assert result.is_flyable
        assert result.max_allowed_speed_ms is None
        assert result.separation_multiplier == 1.0

    def test_clear_no_reasons(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather())
        assert result.reasons == []


class TestAnalyzerWind:
    def test_moderate_wind_altitude_adjust(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(wind_speed_ms=12))
        assert result.restriction == FlightRestriction.ALTITUDE_ADJUST
        assert result.is_flyable
        assert result.recommended_altitude_m is not None

    def test_strong_wind_reroute(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(wind_speed_ms=16))
        assert result.restriction == FlightRestriction.REROUTE
        assert result.is_flyable

    def test_extreme_wind_grounded(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(wind_speed_ms=22))
        assert result.restriction == FlightRestriction.GROUNDED
        assert not result.is_flyable

    def test_gust_triggers_restriction(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(wind_speed_ms=8, wind_gust_ms=21))
        assert result.restriction == FlightRestriction.GROUNDED


class TestAnalyzerPrecipitation:
    def test_light_rain_speed_limit(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(rain_1h_mm=7))
        assert result.restriction == FlightRestriction.SPEED_LIMIT
        assert result.max_allowed_speed_ms is not None
        assert result.max_allowed_speed_ms < 15.0

    def test_heavy_rain_grounded(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(rain_1h_mm=16))
        assert result.restriction == FlightRestriction.GROUNDED

    def test_snow_counts_as_precipitation(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(snow_1h_mm=6))
        assert result.restriction == FlightRestriction.SPEED_LIMIT

    def test_combined_rain_snow(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(rain_1h_mm=8, snow_1h_mm=8))
        assert result.restriction == FlightRestriction.GROUNDED


class TestAnalyzerVisibility:
    def test_reduced_visibility_speed_limit(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(visibility_m=800))
        assert result.restriction == FlightRestriction.SPEED_LIMIT
        assert result.separation_multiplier == 2.0

    def test_very_low_visibility_grounded(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(visibility_m=400))
        assert result.restriction == FlightRestriction.GROUNDED

    def test_good_visibility_no_restriction(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(visibility_m=5000))
        assert result.restriction == FlightRestriction.NONE


class TestAnalyzerCombined:
    def test_wind_plus_rain(self):
        a = WeatherAnalyzer()
        result = a.assess(_make_weather(wind_speed_ms=16, rain_1h_mm=6))
        # Reroute (wind) > speed_limit (rain) → reroute wins
        assert result.restriction == FlightRestriction.REROUTE

    def test_grounded_overrides_all(self):
        a = WeatherAnalyzer()
        result = a.assess(
            _make_weather(wind_speed_ms=25, rain_1h_mm=20, visibility_m=200)
        )
        assert result.restriction == FlightRestriction.GROUNDED
        assert len(result.reasons) >= 2
