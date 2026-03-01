"""Weather impact analysis for drone flight safety.

Evaluates weather conditions against flight restriction thresholds
defined in the project spec and produces actionable decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.weather.fetcher import WeatherData


class FlightRestriction(str, Enum):
    """Restriction level imposed by weather conditions."""

    NONE = "NONE"  # Clear for flight
    SPEED_LIMIT = "SPEED_LIMIT"  # Reduce speed
    ALTITUDE_ADJUST = "ALTITUDE_ADJUST"  # Change altitude
    REROUTE = "REROUTE"  # Must reroute around weather
    GROUNDED = "GROUNDED"  # Cannot fly


@dataclass
class WeatherAssessment:
    """Result of weather impact analysis for a location."""

    restriction: FlightRestriction
    max_allowed_speed_ms: float | None = None  # None = no limit
    recommended_altitude_m: float | None = None
    separation_multiplier: float = 1.0  # 1.0 = normal, 2.0 = doubled
    reasons: list[str] | None = None

    def __post_init__(self) -> None:
        if self.reasons is None:
            self.reasons = []

    @property
    def is_flyable(self) -> bool:
        return self.restriction != FlightRestriction.GROUNDED


# ── thresholds (from SKYMIND_PROJECT.md) ────────────────────────────

_WIND_ALTITUDE_ADJUST_MS = 10.0
_WIND_REROUTE_MS = 15.0
_WIND_GROUNDED_MS = 20.0

_RAIN_SPEED_LIMIT_MM = 5.0
_RAIN_GROUNDED_MM = 15.0

_VIS_SPEED_LIMIT_M = 1000.0
_VIS_GROUNDED_M = 500.0

_SPEED_LIMIT_FACTOR = 0.5  # reduce to 50%
_DEFAULT_MAX_SPEED = 15.0  # m/s reference when applying factor


# ── analyser ────────────────────────────────────────────────────────


class WeatherAnalyzer:
    """Evaluate weather impact on drone flight operations.

    Thresholds follow the spec in ``SKYMIND_PROJECT.md``.
    """

    def __init__(
        self,
        wind_grounded_ms: float = _WIND_GROUNDED_MS,
        wind_reroute_ms: float = _WIND_REROUTE_MS,
        wind_altitude_adjust_ms: float = _WIND_ALTITUDE_ADJUST_MS,
        rain_grounded_mm: float = _RAIN_GROUNDED_MM,
        rain_speed_limit_mm: float = _RAIN_SPEED_LIMIT_MM,
        vis_grounded_m: float = _VIS_GROUNDED_M,
        vis_speed_limit_m: float = _VIS_SPEED_LIMIT_M,
    ) -> None:
        self.wind_grounded = wind_grounded_ms
        self.wind_reroute = wind_reroute_ms
        self.wind_altitude = wind_altitude_adjust_ms
        self.rain_grounded = rain_grounded_mm
        self.rain_speed_limit = rain_speed_limit_mm
        self.vis_grounded = vis_grounded_m
        self.vis_speed_limit = vis_speed_limit_m

    def assess(
        self,
        weather: WeatherData,
        cruise_speed_ms: float = _DEFAULT_MAX_SPEED,
    ) -> WeatherAssessment:
        """Return a :class:`WeatherAssessment` for the given conditions.

        The most restrictive condition wins.
        """
        restriction = FlightRestriction.NONE
        reasons: list[str] = []
        max_speed: float | None = None
        rec_alt: float | None = None
        sep_mult = 1.0

        # ── wind assessment ─────────────────────────────────────────
        wind = max(weather.wind_speed_ms, weather.wind_gust_ms)

        if wind >= self.wind_grounded:
            restriction = FlightRestriction.GROUNDED
            reasons.append(f"Wind {wind:.1f} m/s >= {self.wind_grounded} m/s limit")
        elif wind >= self.wind_reroute:
            restriction = _max_restriction(restriction, FlightRestriction.REROUTE)
            reasons.append(f"Wind {wind:.1f} m/s — reroute perpendicular to wind")
        elif wind >= self.wind_altitude:
            restriction = _max_restriction(restriction, FlightRestriction.ALTITUDE_ADJUST)
            reasons.append(f"Wind {wind:.1f} m/s — lower altitude recommended")
            rec_alt = 60.0  # low-altitude for wind

        # ── precipitation ───────────────────────────────────────────
        precip = weather.rain_1h_mm + weather.snow_1h_mm

        if precip >= self.rain_grounded:
            restriction = _max_restriction(restriction, FlightRestriction.GROUNDED)
            reasons.append(
                f"Precipitation {precip:.1f} mm/h >= {self.rain_grounded} mm/h limit"
            )
        elif precip >= self.rain_speed_limit:
            restriction = _max_restriction(restriction, FlightRestriction.SPEED_LIMIT)
            max_speed = cruise_speed_ms * _SPEED_LIMIT_FACTOR
            reasons.append(
                f"Precipitation {precip:.1f} mm/h — speed limited to {max_speed:.1f} m/s"
            )

        # ── visibility ──────────────────────────────────────────────
        vis = weather.visibility_m

        if vis < self.vis_grounded:
            restriction = _max_restriction(restriction, FlightRestriction.GROUNDED)
            reasons.append(f"Visibility {vis:.0f} m < {self.vis_grounded} m limit")
        elif vis < self.vis_speed_limit:
            restriction = _max_restriction(restriction, FlightRestriction.SPEED_LIMIT)
            if max_speed is None:
                max_speed = cruise_speed_ms * _SPEED_LIMIT_FACTOR
            sep_mult = 2.0
            reasons.append(
                f"Visibility {vis:.0f} m — speed limited, separation doubled"
            )

        return WeatherAssessment(
            restriction=restriction,
            max_allowed_speed_ms=max_speed,
            recommended_altitude_m=rec_alt,
            separation_multiplier=sep_mult,
            reasons=reasons,
        )


# ── helpers ─────────────────────────────────────────────────────────

_RESTRICTION_RANK = {
    FlightRestriction.NONE: 0,
    FlightRestriction.SPEED_LIMIT: 1,
    FlightRestriction.ALTITUDE_ADJUST: 2,
    FlightRestriction.REROUTE: 3,
    FlightRestriction.GROUNDED: 4,
}


def _max_restriction(a: FlightRestriction, b: FlightRestriction) -> FlightRestriction:
    return a if _RESTRICTION_RANK[a] >= _RESTRICTION_RANK[b] else b
