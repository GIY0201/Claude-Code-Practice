"""Enhanced emergency landing path planner.

Extends the basic landing logic in :mod:`handler` with:
- Battery-aware landing zone selection (reachability filter)
- Airspace-aware routing (avoid RESTRICTED zones on approach)
- Staged descent approach (cruise altitude → approach altitude → landing)
- Landing zone CRUD management
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from models.common import Position3D
from core.emergency.handler import LandingZone, _DEFAULT_ZONES


# ── helpers (local copies to avoid circular deps) ────────────────────

def _haversine(a: Position3D, b: Position3D) -> float:
    """Horizontal distance in metres (Haversine)."""
    R = 6_371_000
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    la = math.radians(a.lat)
    lb = math.radians(b.lat)
    h = math.sin(dlat / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _distance_3d(a: Position3D, b: Position3D) -> float:
    h = _haversine(a, b)
    dz = b.alt_m - a.alt_m
    return math.sqrt(h * h + dz * dz)


# ── result dataclass ─────────────────────────────────────────────────


@dataclass
class LandingPathResult:
    """Result of emergency landing path generation."""

    landing_zone: LandingZone
    path: list[Position3D]
    estimated_distance_m: float
    estimated_time_sec: float
    battery_required_pct: float
    is_reachable: bool
    used_avoidance_path: bool


# ── planner ──────────────────────────────────────────────────────────


class EmergencyLandingPlanner:
    """Plan emergency landing paths with airspace and battery awareness.

    Parameters
    ----------
    landing_zones :
        Available landing zones.  Defaults to Seoul presets from
        :mod:`handler`.
    descent_rate_ms :
        Vertical descent speed (m/s).
    approach_altitude_m :
        Altitude to reach before final descent.
    min_battery_margin_pct :
        Required safety margin above estimated consumption.
    battery_drain_per_sec :
        Battery consumption rate (%/sec).
    reference_lat :
        Reference latitude for coordinate conversions.
    """

    def __init__(
        self,
        landing_zones: list[LandingZone] | None = None,
        descent_rate_ms: float = 3.0,
        approach_altitude_m: float = 50.0,
        min_battery_margin_pct: float = 5.0,
        battery_drain_per_sec: float = 0.05,
        reference_lat: float = 37.5665,
    ) -> None:
        self._zones: dict[str, LandingZone] = {}
        for z in (landing_zones if landing_zones is not None else list(_DEFAULT_ZONES)):
            self._zones[z.zone_id] = z
        self.descent_rate_ms = descent_rate_ms
        self.approach_altitude_m = approach_altitude_m
        self.min_battery_margin_pct = min_battery_margin_pct
        self.battery_drain_per_sec = battery_drain_per_sec
        self.reference_lat = reference_lat

    # ── zone management ───────────────────────────────────────────────

    def add_zone(self, zone: LandingZone) -> None:
        self._zones[zone.zone_id] = zone

    def remove_zone(self, zone_id: str) -> bool:
        return self._zones.pop(zone_id, None) is not None

    def list_zones(self) -> list[LandingZone]:
        return list(self._zones.values())

    def get_zone(self, zone_id: str) -> LandingZone | None:
        return self._zones.get(zone_id)

    # ── battery estimation ────────────────────────────────────────────

    def _estimate_battery_for_distance(
        self, distance_m: float, speed_ms: float
    ) -> float:
        """Estimate battery % needed to cover *distance_m* at *speed_ms*."""
        if speed_ms <= 0:
            return float("inf")
        time_sec = distance_m / speed_ms
        return time_sec * self.battery_drain_per_sec

    # ── reachability ──────────────────────────────────────────────────

    def find_reachable_zones(
        self,
        position: Position3D,
        battery_pct: float,
        speed_ms: float = 10.0,
    ) -> list[tuple[LandingZone, float, float]]:
        """Return landing zones reachable with current battery.

        Returns
        -------
        list of (LandingZone, distance_m, battery_required_pct)
            Sorted by distance ascending, filtered to reachable-only.
        """
        candidates: list[tuple[LandingZone, float, float]] = []
        for zone in self._zones.values():
            dist = _distance_3d(position, zone.position)
            batt_needed = self._estimate_battery_for_distance(dist, speed_ms)
            total_needed = batt_needed + self.min_battery_margin_pct
            if total_needed <= battery_pct:
                candidates.append((zone, dist, batt_needed))
        candidates.sort(key=lambda t: t[1])
        return candidates

    # ── path checking ─────────────────────────────────────────────────

    @staticmethod
    def _check_direct_path_clear(
        start: Position3D,
        end: Position3D,
        airspace_manager: object,
        num_samples: int = 10,
    ) -> bool:
        """Sample points along the direct path and check flyability."""
        for i in range(num_samples + 1):
            t = i / num_samples
            lat = start.lat + t * (end.lat - start.lat)
            lon = start.lon + t * (end.lon - start.lon)
            alt = start.alt_m + t * (end.alt_m - start.alt_m)
            if not airspace_manager.is_flyable(Position3D(lat=lat, lon=lon, alt_m=alt)):  # type: ignore[union-attr]
                return False
        return True

    # ── approach path ─────────────────────────────────────────────────

    def generate_approach_path(
        self,
        current: Position3D,
        landing_zone: LandingZone,
        airspace_manager: object | None = None,
    ) -> list[Position3D]:
        """Generate a detailed approach path to a landing zone.

        Sequence:
        1. Level flight at current altitude toward zone
           (or avoidance path if direct crosses restricted airspace)
        2. Descend to approach altitude above the zone
        3. Final descent to landing zone altitude
        """
        target = landing_zone.position
        above_target = Position3D(
            lat=target.lat, lon=target.lon, alt_m=current.alt_m
        )

        # Build horizontal segment
        horizontal_path: list[Position3D]
        used_avoidance = False

        if airspace_manager is not None and not self._check_direct_path_clear(
            current, above_target, airspace_manager
        ):
            # Use A* pathfinder for avoidance
            horizontal_path = self._build_avoidance_path(
                current, above_target, airspace_manager
            )
            used_avoidance = True
        else:
            horizontal_path = [current, above_target]

        # Append descent stages
        approach_alt = max(
            self.approach_altitude_m, target.alt_m + 10
        )
        if current.alt_m > approach_alt:
            horizontal_path.append(
                Position3D(lat=target.lat, lon=target.lon, alt_m=approach_alt)
            )

        horizontal_path.append(target)
        return horizontal_path, used_avoidance  # type: ignore[return-value]

    def _build_avoidance_path(
        self,
        start: Position3D,
        end: Position3D,
        airspace_manager: object,
    ) -> list[Position3D]:
        """Use A* pathfinder to build an avoidance path."""
        from core.path_engine.astar import AStarPathfinder

        pf = AStarPathfinder(
            grid_resolution_m=100.0,
            reference_lat=self.reference_lat,
        )

        zones = airspace_manager.list_zones(active_only=True)  # type: ignore[union-attr]
        restricted = []
        for z in zones:
            if z.zone_type.value == "RESTRICTED":
                coords = z.geometry.get("coordinates", [[]])
                if coords and coords[0]:
                    lats = [c[1] for c in coords[0]]
                    lons = [c[0] for c in coords[0]]
                    clat = sum(lats) / len(lats)
                    clon = sum(lons) / len(lons)
                    max_dist = max(
                        _haversine(
                            Position3D(lat=clat, lon=clon, alt_m=0),
                            Position3D(lat=la, lon=lo, alt_m=0),
                        )
                        for la, lo in zip(lats, lons)
                    )
                    restricted.append({
                        "center_lat": clat,
                        "center_lon": clon,
                        "radius_m": max_dist,
                        "floor_m": z.floor_altitude_m,
                        "ceiling_m": z.ceiling_altitude_m,
                    })

        if restricted:
            pf.set_restricted_zones(restricted)

        path = pf.find_path(start, end)
        return path if path else [start, end]

    # ── main entry point ──────────────────────────────────────────────

    def plan_landing(
        self,
        position: Position3D,
        battery_pct: float,
        speed_ms: float = 10.0,
        airspace_manager: object | None = None,
    ) -> LandingPathResult | None:
        """Plan a complete emergency landing path.

        Selects the nearest reachable landing zone, generates a path
        that avoids restricted airspace, and includes approach/descent
        sequence.

        Returns ``None`` if no landing zone is reachable.
        """
        reachable = self.find_reachable_zones(position, battery_pct, speed_ms)
        if not reachable:
            return None

        zone, dist, batt_needed = reachable[0]  # nearest

        path, used_avoidance = self.generate_approach_path(
            position, zone, airspace_manager
        )

        # Compute total path distance
        total_dist = 0.0
        for i in range(len(path) - 1):
            total_dist += _distance_3d(path[i], path[i + 1])

        est_time = total_dist / speed_ms if speed_ms > 0 else float("inf")
        actual_batt = self._estimate_battery_for_distance(total_dist, speed_ms)

        return LandingPathResult(
            landing_zone=zone,
            path=path,
            estimated_distance_m=total_dist,
            estimated_time_sec=est_time,
            battery_required_pct=actual_batt,
            is_reachable=True,
            used_avoidance_path=used_avoidance,
        )
