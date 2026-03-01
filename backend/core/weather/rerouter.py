"""Weather-based dynamic path rerouting.

Modifies flight paths based on weather assessment results:
- SPEED_LIMIT  → reduce speed constraint (path unchanged)
- ALTITUDE_ADJUST → shift intermediate waypoints to recommended altitude
- REROUTE → offset intermediate waypoints perpendicular to wind direction
- GROUNDED → return empty path (cannot fly)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from models.common import Position3D
from core.weather.analyzer import WeatherAssessment, FlightRestriction
from core.weather.fetcher import WeatherData


@dataclass
class RerouteResult:
    """Result of weather-based path modification."""

    waypoints: list[Position3D]
    speed_constraint_ms: float | None  # None = no limit
    restriction_applied: FlightRestriction
    modified: bool
    reason: str


class WeatherRerouter:
    """Modify flight paths based on weather assessment.

    Parameters
    ----------
    perpendicular_offset_m : float
        Distance to offset waypoints perpendicular to wind direction
        when REROUTE restriction is active.
    min_altitude_m : float
        Floor altitude for altitude adjustments.
    max_altitude_m : float
        Ceiling altitude for altitude adjustments.
    reference_lat : float
        Reference latitude for metre-to-degree conversions.
    """

    def __init__(
        self,
        perpendicular_offset_m: float = 500.0,
        min_altitude_m: float = 30.0,
        max_altitude_m: float = 400.0,
        reference_lat: float = 37.5665,
    ) -> None:
        self.perpendicular_offset_m = perpendicular_offset_m
        self.min_altitude_m = min_altitude_m
        self.max_altitude_m = max_altitude_m
        self.reference_lat = reference_lat

    def apply(
        self,
        waypoints: list[Position3D],
        assessment: WeatherAssessment,
        weather: WeatherData | None = None,
    ) -> RerouteResult:
        """Apply weather assessment to a flight path.

        Parameters
        ----------
        waypoints :
            Current planned waypoints.
        assessment :
            Output from ``WeatherAnalyzer.assess()``.
        weather :
            Raw weather data, required when ``assessment.restriction == REROUTE``
            to obtain wind direction.
        """
        if not waypoints or len(waypoints) < 2:
            return RerouteResult(
                waypoints=list(waypoints),
                speed_constraint_ms=None,
                restriction_applied=assessment.restriction,
                modified=False,
                reason="Path too short to modify",
            )

        r = assessment.restriction

        if r == FlightRestriction.NONE:
            return self._apply_none(waypoints)
        elif r == FlightRestriction.SPEED_LIMIT:
            return self._apply_speed_limit(waypoints, assessment)
        elif r == FlightRestriction.ALTITUDE_ADJUST:
            return self._apply_altitude_adjust(waypoints, assessment)
        elif r == FlightRestriction.REROUTE:
            if weather is None:
                raise ValueError(
                    "WeatherData is required for REROUTE restriction"
                )
            return self._apply_reroute(waypoints, assessment, weather)
        else:  # GROUNDED
            return self._apply_grounded(assessment)

    # ── restriction handlers ──────────────────────────────────────────

    def _apply_none(self, waypoints: list[Position3D]) -> RerouteResult:
        return RerouteResult(
            waypoints=list(waypoints),
            speed_constraint_ms=None,
            restriction_applied=FlightRestriction.NONE,
            modified=False,
            reason="No weather restriction",
        )

    def _apply_speed_limit(
        self, waypoints: list[Position3D], assessment: WeatherAssessment
    ) -> RerouteResult:
        return RerouteResult(
            waypoints=list(waypoints),
            speed_constraint_ms=assessment.max_allowed_speed_ms,
            restriction_applied=FlightRestriction.SPEED_LIMIT,
            modified=False,
            reason="Speed limited due to weather",
        )

    def _apply_altitude_adjust(
        self, waypoints: list[Position3D], assessment: WeatherAssessment
    ) -> RerouteResult:
        rec_alt = assessment.recommended_altitude_m
        if rec_alt is None:
            return self._apply_none(waypoints)

        target_alt = max(self.min_altitude_m, min(self.max_altitude_m, rec_alt))

        adjusted: list[Position3D] = [waypoints[0]]
        for wp in waypoints[1:-1]:
            adjusted.append(
                Position3D(lat=wp.lat, lon=wp.lon, alt_m=target_alt)
            )
        adjusted.append(waypoints[-1])

        return RerouteResult(
            waypoints=adjusted,
            speed_constraint_ms=assessment.max_allowed_speed_ms,
            restriction_applied=FlightRestriction.ALTITUDE_ADJUST,
            modified=True,
            reason=f"Altitude adjusted to {target_alt:.0f}m due to wind",
        )

    def _apply_reroute(
        self,
        waypoints: list[Position3D],
        assessment: WeatherAssessment,
        weather: WeatherData,
    ) -> RerouteResult:
        rerouted: list[Position3D] = [waypoints[0]]
        for wp in waypoints[1:-1]:
            rerouted.append(
                self._wind_perpendicular_offset(
                    wp,
                    weather.wind_deg,
                    self.perpendicular_offset_m,
                    self.reference_lat,
                )
            )
        rerouted.append(waypoints[-1])

        return RerouteResult(
            waypoints=rerouted,
            speed_constraint_ms=assessment.max_allowed_speed_ms,
            restriction_applied=FlightRestriction.REROUTE,
            modified=True,
            reason="Path rerouted perpendicular to wind direction",
        )

    def _apply_grounded(
        self, assessment: WeatherAssessment
    ) -> RerouteResult:
        reasons = "; ".join(assessment.reasons) if assessment.reasons else "Severe weather"
        return RerouteResult(
            waypoints=[],
            speed_constraint_ms=None,
            restriction_applied=FlightRestriction.GROUNDED,
            modified=True,
            reason=f"GROUNDED — {reasons}",
        )

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _wind_perpendicular_offset(
        position: Position3D,
        wind_deg: float,
        offset_m: float,
        reference_lat: float,
    ) -> Position3D:
        """Shift *position* perpendicular to the wind direction.

        ``wind_deg`` follows the meteorological convention: the direction
        the wind is coming *from* (0 = North, 90 = East).  The offset is
        applied 90° clockwise from the wind **travel** direction.
        """
        # Wind travel direction (opposite of "from")
        travel_deg = (wind_deg + 180.0) % 360.0
        # Perpendicular: 90° clockwise from travel direction
        perp_deg = (travel_deg + 90.0) % 360.0
        perp_rad = math.radians(perp_deg)

        dlat = offset_m * math.cos(perp_rad) / 111_320.0
        dlon = offset_m * math.sin(perp_rad) / (
            111_320.0 * math.cos(math.radians(reference_lat))
        )

        return Position3D(
            lat=position.lat + dlat,
            lon=position.lon + dlon,
            alt_m=position.alt_m,
        )
