"""OpenWeatherMap API client for real-time weather data.

Provides current weather conditions at a given location for flight
safety assessment.  Falls back to a mock response when no API key is
configured, enabling development/testing without external services.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from config import Settings

_SETTINGS = Settings()

# ── data model ──────────────────────────────────────────────────────


@dataclass
class WeatherData:
    """Parsed weather observation relevant to drone flight."""

    lat: float
    lon: float
    timestamp: float  # Unix epoch

    # Wind
    wind_speed_ms: float = 0.0  # m/s
    wind_deg: float = 0.0  # meteorological degrees (0=N, 90=E)
    wind_gust_ms: float = 0.0

    # Precipitation & visibility
    rain_1h_mm: float = 0.0  # mm in last 1 h
    snow_1h_mm: float = 0.0
    visibility_m: float = 10_000.0  # metres

    # Atmosphere
    temperature_c: float = 20.0
    humidity_pct: float = 50.0
    pressure_hpa: float = 1013.25

    # Condition summary
    condition: str = "Clear"
    description: str = "clear sky"


def _parse_owm_response(data: dict[str, Any]) -> WeatherData:
    """Convert raw OpenWeatherMap JSON to :class:`WeatherData`."""
    coord = data.get("coord", {})
    wind = data.get("wind", {})
    rain = data.get("rain", {})
    snow = data.get("snow", {})
    main = data.get("main", {})
    weather_list = data.get("weather", [{}])

    return WeatherData(
        lat=coord.get("lat", 0),
        lon=coord.get("lon", 0),
        timestamp=data.get("dt", time.time()),
        wind_speed_ms=wind.get("speed", 0),
        wind_deg=wind.get("deg", 0),
        wind_gust_ms=wind.get("gust", wind.get("speed", 0)),
        rain_1h_mm=rain.get("1h", 0),
        snow_1h_mm=snow.get("1h", 0),
        visibility_m=data.get("visibility", 10_000),
        temperature_c=main.get("temp", 20),
        humidity_pct=main.get("humidity", 50),
        pressure_hpa=main.get("pressure", 1013.25),
        condition=weather_list[0].get("main", "Clear"),
        description=weather_list[0].get("description", "clear sky"),
    )


# ── mock data ───────────────────────────────────────────────────────

_MOCK_CLEAR = {
    "coord": {"lat": 37.5665, "lon": 126.978},
    "weather": [{"main": "Clear", "description": "clear sky"}],
    "main": {"temp": 18, "humidity": 45, "pressure": 1015},
    "wind": {"speed": 3.5, "deg": 220, "gust": 5.0},
    "visibility": 10000,
    "rain": {},
    "snow": {},
    "dt": int(time.time()),
}


def _mock_weather(lat: float, lon: float) -> WeatherData:
    """Return a plausible clear-weather observation for testing."""
    mock = dict(_MOCK_CLEAR)
    mock["coord"] = {"lat": lat, "lon": lon}
    mock["dt"] = int(time.time())
    return _parse_owm_response(mock)


# ── fetcher ─────────────────────────────────────────────────────────


class WeatherFetcher:
    """Fetch weather from OpenWeatherMap Current Weather API.

    Parameters
    ----------
    api_key : str | None
        OWM API key.  If *None*, reads ``OPENWEATHER_API_KEY`` from
        settings.  An empty key triggers mock mode.
    cache_ttl_sec : float
        How long a cached observation stays valid.
    """

    BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

    def __init__(
        self,
        api_key: str | None = None,
        cache_ttl_sec: float = 300.0,
    ) -> None:
        self._api_key = api_key if api_key is not None else _SETTINGS.OPENWEATHER_API_KEY
        self._cache_ttl = cache_ttl_sec
        self._cache: dict[str, tuple[float, WeatherData]] = {}

    @property
    def is_mock(self) -> bool:
        return not self._api_key

    def _cache_key(self, lat: float, lon: float) -> str:
        return f"{lat:.2f},{lon:.2f}"

    def get_weather(self, lat: float, lon: float) -> WeatherData:
        """Return current weather at *(lat, lon)*.

        Uses cache to avoid redundant API calls.  Returns mock data
        when no API key is available.
        """
        if self.is_mock:
            return _mock_weather(lat, lon)

        key = self._cache_key(lat, lon)
        now = time.time()
        if key in self._cache:
            ts, data = self._cache[key]
            if now - ts < self._cache_ttl:
                return data

        data = self._fetch(lat, lon)
        self._cache[key] = (now, data)
        return data

    def _fetch(self, lat: float, lon: float) -> WeatherData:
        params = {
            "lat": lat,
            "lon": lon,
            "appid": self._api_key,
            "units": "metric",
        }
        try:
            resp = httpx.get(self.BASE_URL, params=params, timeout=10.0)
            resp.raise_for_status()
            return _parse_owm_response(resp.json())
        except (httpx.HTTPError, KeyError, ValueError):
            return _mock_weather(lat, lon)

    def clear_cache(self) -> None:
        self._cache.clear()
