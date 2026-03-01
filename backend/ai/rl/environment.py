"""Gymnasium environment for single-drone routing.

Provides a continuous state/action space where an RL agent learns to
navigate a drone from start to goal while respecting airspace rules,
avoiding other drones, handling weather, and conserving battery.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import gymnasium
import numpy as np
from gymnasium import spaces

from models.common import Position3D, Velocity3D
from core.weather.fetcher import WeatherData


# ── configuration ────────────────────────────────────────────────────


@dataclass
class DroneEnvConfig:
    """Configuration for the drone RL environment."""

    # Drone initial state
    start_position: Position3D = field(
        default_factory=lambda: Position3D(lat=37.56, lon=126.95, alt_m=100)
    )
    goal_position: Position3D = field(
        default_factory=lambda: Position3D(lat=37.57, lon=127.01, alt_m=100)
    )
    initial_speed_ms: float = 10.0
    initial_heading_deg: float = 90.0
    initial_battery_pct: float = 100.0
    battery_drain_per_sec: float = 0.05

    # Environment limits
    max_steps: int = 500
    dt_sec: float = 1.0
    max_speed_ms: float = 20.0
    min_speed_ms: float = 1.0
    altitude_min_m: float = 30.0
    altitude_max_m: float = 400.0

    # Observation
    nearby_drones_k: int = 3
    observation_radius_m: float = 2000.0

    # Reward weights
    approach_reward_scale: float = 1.0
    arrival_bonus: float = 100.0
    airspace_violation_penalty: float = -50.0
    separation_violation_penalty: float = -30.0
    energy_penalty_scale: float = -0.01
    time_penalty: float = -0.1

    # Domain
    reference_lat: float = 37.5665
    lat_range: float = 0.1  # ±0.1° around reference (~±11 km)
    lon_range: float = 0.1
    separation_h_m: float = 100.0
    separation_v_m: float = 30.0
    arrival_threshold_m: float = 50.0


# ── helpers ──────────────────────────────────────────────────────────

_EARTH_R = 6_371_000.0


def _haversine(a: Position3D, b: Position3D) -> float:
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    la = math.radians(a.lat)
    lb = math.radians(b.lat)
    h = math.sin(dlat / 2) ** 2 + math.cos(la) * math.cos(lb) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_R * math.asin(math.sqrt(h))


def _distance_3d(a: Position3D, b: Position3D) -> float:
    h = _haversine(a, b)
    dz = b.alt_m - a.alt_m
    return math.sqrt(h * h + dz * dz)


# ── environment ──────────────────────────────────────────────────────


class DroneRoutingEnv(gymnasium.Env):
    """Gymnasium environment for single-drone routing.

    Observation space (Box, float32, shape=(24,)):
        [0:3]   drone position (lat, lon, alt) normalised to [0, 1]
        [3:6]   delta to goal (dx, dy, dz) in metres, normalised to [-1, 1]
        [6:15]  K nearest drone positions (normalised), zero-padded
        [15]    nearest restricted-zone distance (normalised)
        [16:19] weather (wind_speed/30, wind_deg/360, precipitation/20)
        [19]    battery fraction [0, 1]
        [20:23] velocity (vx, vy, vz) / max_speed
        [23]    heading / 360

    Action space (Box, float32, shape=(3,)):
        [0] delta_heading: [-30, +30] degrees
        [1] delta_speed:   [-5, +5] m/s
        [2] delta_altitude: [-10, +10] m
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        config: DroneEnvConfig | None = None,
        airspace_manager: object | None = None,
        weather_data: WeatherData | None = None,
        nearby_drones: list[tuple[Position3D, Velocity3D]] | None = None,
        render_mode: str | None = None,
    ) -> None:
        super().__init__()
        self.cfg = config or DroneEnvConfig()
        self.airspace_manager = airspace_manager
        self._weather = weather_data
        self._nearby_drones: list[tuple[Position3D, Velocity3D]] = nearby_drones or []
        self.render_mode = render_mode

        # Observation & action spaces
        obs_dim = 3 + 3 + self.cfg.nearby_drones_k * 3 + 1 + 3 + 1 + 3 + 1  # = 24
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(obs_dim,), dtype=np.float32
        )
        self.action_space = spaces.Box(
            low=np.array([-30.0, -5.0, -10.0], dtype=np.float32),
            high=np.array([30.0, 5.0, 10.0], dtype=np.float32),
            dtype=np.float32,
        )

        # State (set in reset)
        self._position = self.cfg.start_position
        self._speed_ms = self.cfg.initial_speed_ms
        self._heading_deg = self.cfg.initial_heading_deg
        self._battery_pct = self.cfg.initial_battery_pct
        self._velocity = Velocity3D()
        self._step_count = 0

    # ── public API ────────────────────────────────────────────────────

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        self._position = Position3D(
            lat=self.cfg.start_position.lat,
            lon=self.cfg.start_position.lon,
            alt_m=self.cfg.start_position.alt_m,
        )
        self._speed_ms = self.cfg.initial_speed_ms
        self._heading_deg = self.cfg.initial_heading_deg
        self._battery_pct = self.cfg.initial_battery_pct
        self._velocity = Velocity3D()
        self._step_count = 0

        obs = self._get_observation()
        info = self._build_info()
        return obs, info

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict]:
        prev_position = Position3D(
            lat=self._position.lat,
            lon=self._position.lon,
            alt_m=self._position.alt_m,
        )

        self._apply_action(action)
        self._step_count += 1

        reward, reward_info = self._compute_reward(prev_position, self._position)

        terminated = self._check_terminated()
        truncated = self._check_truncated()

        obs = self._get_observation()
        info = self._build_info()
        info["reward_breakdown"] = reward_info

        return obs, reward, terminated, truncated, info

    def set_nearby_drones(
        self, drones: list[tuple[Position3D, Velocity3D]]
    ) -> None:
        self._nearby_drones = drones

    def set_weather(self, weather: WeatherData) -> None:
        self._weather = weather

    # ── action application ────────────────────────────────────────────

    def _apply_action(self, action: np.ndarray) -> None:
        delta_heading = float(action[0])
        delta_speed = float(action[1])
        delta_altitude = float(action[2])

        # Update heading
        self._heading_deg = (self._heading_deg + delta_heading) % 360.0

        # Update speed (clamped)
        self._speed_ms = max(
            self.cfg.min_speed_ms,
            min(self.cfg.max_speed_ms, self._speed_ms + delta_speed),
        )

        # Move horizontally
        heading_rad = math.radians(self._heading_deg)
        move_m = self._speed_ms * self.cfg.dt_sec
        dlat = (move_m * math.cos(heading_rad)) / 111_320.0
        dlon = (move_m * math.sin(heading_rad)) / (
            111_320.0 * math.cos(math.radians(self._position.lat))
        )

        new_lat = self._position.lat + dlat
        new_lon = self._position.lon + dlon

        # Update altitude (clamped)
        new_alt = max(
            self.cfg.altitude_min_m,
            min(self.cfg.altitude_max_m, self._position.alt_m + delta_altitude),
        )

        # Velocity vector
        vx = self._speed_ms * math.sin(heading_rad)
        vy = self._speed_ms * math.cos(heading_rad)
        vz = delta_altitude / self.cfg.dt_sec if self.cfg.dt_sec > 0 else 0.0

        self._position = Position3D(lat=new_lat, lon=new_lon, alt_m=new_alt)
        self._velocity = Velocity3D(vx=round(vx, 4), vy=round(vy, 4), vz=round(vz, 4))

        # Drain battery
        self._battery_pct = max(
            0.0,
            self._battery_pct - self.cfg.battery_drain_per_sec * self.cfg.dt_sec,
        )

    # ── reward ────────────────────────────────────────────────────────

    def _compute_reward(
        self,
        prev_position: Position3D,
        new_position: Position3D,
    ) -> tuple[float, dict]:
        breakdown: dict[str, float] = {}
        reward = 0.0

        # 1. Approach reward
        prev_dist = _distance_3d(prev_position, self.cfg.goal_position)
        new_dist = _distance_3d(new_position, self.cfg.goal_position)
        approach = (prev_dist - new_dist) * self.cfg.approach_reward_scale
        reward += approach
        breakdown["approach"] = approach

        # 2. Arrival bonus
        if new_dist < self.cfg.arrival_threshold_m:
            reward += self.cfg.arrival_bonus
            breakdown["arrival"] = self.cfg.arrival_bonus
        else:
            breakdown["arrival"] = 0.0

        # 3. Airspace violation
        airspace_pen = 0.0
        if self.airspace_manager is not None:
            if not self.airspace_manager.is_flyable(new_position):  # type: ignore[union-attr]
                airspace_pen = self.cfg.airspace_violation_penalty
        reward += airspace_pen
        breakdown["airspace_violation"] = airspace_pen

        # 4. Separation violation
        sep_pen = 0.0
        for drone_pos, _ in self._nearby_drones:
            h_dist = _haversine(new_position, drone_pos)
            v_dist = abs(new_position.alt_m - drone_pos.alt_m)
            if h_dist < self.cfg.separation_h_m and v_dist < self.cfg.separation_v_m:
                sep_pen = self.cfg.separation_violation_penalty
                break
        reward += sep_pen
        breakdown["separation_violation"] = sep_pen

        # 5. Energy penalty
        energy = self.cfg.battery_drain_per_sec * self.cfg.dt_sec * self.cfg.energy_penalty_scale
        reward += energy
        breakdown["energy"] = energy

        # 6. Time penalty
        reward += self.cfg.time_penalty
        breakdown["time"] = self.cfg.time_penalty

        return reward, breakdown

    # ── termination ───────────────────────────────────────────────────

    def _check_terminated(self) -> bool:
        # Arrived at goal
        dist = _distance_3d(self._position, self.cfg.goal_position)
        if dist < self.cfg.arrival_threshold_m:
            return True
        # Battery depleted
        if self._battery_pct <= 0.0:
            return True
        return False

    def _check_truncated(self) -> bool:
        return self._step_count >= self.cfg.max_steps

    # ── observation ───────────────────────────────────────────────────

    def _get_observation(self) -> np.ndarray:
        obs = np.zeros(self.observation_space.shape[0], dtype=np.float32)

        # [0:3] drone position normalised
        obs[0] = self._normalize_lat(self._position.lat)
        obs[1] = self._normalize_lon(self._position.lon)
        obs[2] = self._normalize_alt(self._position.alt_m)

        # [3:6] goal delta (metres, normalised)
        max_dist = self.cfg.lat_range * 111_320.0 * 2  # ≈ 22 km
        dx_m = (self.cfg.goal_position.lon - self._position.lon) * (
            111_320.0 * math.cos(math.radians(self.cfg.reference_lat))
        )
        dy_m = (self.cfg.goal_position.lat - self._position.lat) * 111_320.0
        dz_m = self.cfg.goal_position.alt_m - self._position.alt_m
        obs[3] = np.clip(dx_m / max_dist, -1, 1)
        obs[4] = np.clip(dy_m / max_dist, -1, 1)
        obs[5] = np.clip(dz_m / self.cfg.altitude_max_m, -1, 1)

        # [6:15] K nearest drones
        base = 6
        sorted_drones = sorted(
            self._nearby_drones,
            key=lambda d: _distance_3d(self._position, d[0]),
        )
        for i, (dpos, _) in enumerate(sorted_drones[: self.cfg.nearby_drones_k]):
            obs[base + i * 3] = self._normalize_lat(dpos.lat)
            obs[base + i * 3 + 1] = self._normalize_lon(dpos.lon)
            obs[base + i * 3 + 2] = self._normalize_alt(dpos.alt_m)

        # [15] nearest restricted zone distance
        obs[15] = self._get_nearest_restricted_distance()

        # [16:19] weather
        if self._weather is not None:
            obs[16] = min(self._weather.wind_speed_ms / 30.0, 1.0)
            obs[17] = self._weather.wind_deg / 360.0
            obs[18] = min(
                (self._weather.rain_1h_mm + self._weather.snow_1h_mm) / 20.0, 1.0
            )

        # [19] battery
        obs[19] = self._battery_pct / 100.0

        # [20:23] velocity
        max_s = self.cfg.max_speed_ms if self.cfg.max_speed_ms > 0 else 1.0
        obs[20] = np.clip(self._velocity.vx / max_s, -1, 1)
        obs[21] = np.clip(self._velocity.vy / max_s, -1, 1)
        obs[22] = np.clip(self._velocity.vz / max_s, -1, 1)

        # [23] heading
        obs[23] = self._heading_deg / 360.0

        return obs

    # ── normalisation helpers ─────────────────────────────────────────

    def _normalize_lat(self, lat: float) -> float:
        center = self.cfg.reference_lat
        return float(np.clip((lat - center + self.cfg.lat_range) / (2 * self.cfg.lat_range), 0, 1))

    def _normalize_lon(self, lon: float) -> float:
        center = 126.9780  # Seoul centre lon
        return float(np.clip((lon - center + self.cfg.lon_range) / (2 * self.cfg.lon_range), 0, 1))

    def _normalize_alt(self, alt: float) -> float:
        return float(np.clip(alt / self.cfg.altitude_max_m, 0, 1))

    def _get_nearest_restricted_distance(self) -> float:
        if self.airspace_manager is None:
            return 1.0  # max distance (normalised)
        zones = self.airspace_manager.list_zones(active_only=True)  # type: ignore[union-attr]
        min_dist = self.cfg.observation_radius_m
        for z in zones:
            if z.zone_type.value == "RESTRICTED":
                coords = z.geometry.get("coordinates", [[]])
                if coords and coords[0]:
                    lats = [c[1] for c in coords[0]]
                    lons = [c[0] for c in coords[0]]
                    clat = sum(lats) / len(lats)
                    clon = sum(lons) / len(lons)
                    dist = _haversine(
                        self._position,
                        Position3D(lat=clat, lon=clon, alt_m=self._position.alt_m),
                    )
                    min_dist = min(min_dist, dist)
        return float(np.clip(min_dist / self.cfg.observation_radius_m, 0, 1))

    # ── info ──────────────────────────────────────────────────────────

    def _build_info(self) -> dict:
        return {
            "position": self._position,
            "speed_ms": self._speed_ms,
            "heading_deg": self._heading_deg,
            "battery_pct": self._battery_pct,
            "step": self._step_count,
            "distance_to_goal": _distance_3d(self._position, self.cfg.goal_position),
        }
