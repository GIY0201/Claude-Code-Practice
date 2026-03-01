"""Tests for drone routing RL environment."""

import math

import numpy as np
import pytest

from models.common import Position3D, Velocity3D
from core.weather.fetcher import WeatherData
from ai.rl.environment import DroneRoutingEnv, DroneEnvConfig


# ── helpers ───────────────────────────────────────────────────────────

SEOUL = Position3D(lat=37.5665, lon=126.9780, alt_m=100)


def _config(**kwargs) -> DroneEnvConfig:
    defaults = dict(
        start_position=Position3D(lat=37.56, lon=126.95, alt_m=100),
        goal_position=Position3D(lat=37.57, lon=127.01, alt_m=100),
    )
    defaults.update(kwargs)
    return DroneEnvConfig(**defaults)


def _weather(wind_speed: float = 5.0, wind_deg: float = 90.0, rain: float = 0.0) -> WeatherData:
    return WeatherData(
        lat=37.5665, lon=126.9780, timestamp=1700000000,
        wind_speed_ms=wind_speed, wind_deg=wind_deg, rain_1h_mm=rain,
    )


def _make_env(**kwargs) -> DroneRoutingEnv:
    return DroneRoutingEnv(config=_config(**kwargs))


# ── environment creation ─────────────────────────────────────────────


class TestEnvCreation:
    def test_default_config_creates_env(self):
        env = DroneRoutingEnv()
        assert env is not None
        assert env.cfg is not None

    def test_custom_config(self):
        env = _make_env(max_steps=100, dt_sec=0.5)
        assert env.cfg.max_steps == 100
        assert env.cfg.dt_sec == 0.5

    def test_observation_space_shape(self):
        env = DroneRoutingEnv()
        assert env.observation_space.shape == (24,)

    def test_action_space_shape(self):
        env = DroneRoutingEnv()
        assert env.action_space.shape == (3,)

    def test_action_space_bounds(self):
        env = DroneRoutingEnv()
        np.testing.assert_array_equal(env.action_space.low, [-30, -5, -10])
        np.testing.assert_array_equal(env.action_space.high, [30, 5, 10])


# ── reset ─────────────────────────────────────────────────────────────


class TestReset:
    def test_reset_returns_observation(self):
        env = _make_env()
        obs, info = env.reset()
        assert obs.shape == (24,)
        assert obs.dtype == np.float32

    def test_reset_returns_info_dict(self):
        env = _make_env()
        obs, info = env.reset()
        assert "position" in info
        assert "battery_pct" in info
        assert "distance_to_goal" in info

    def test_reset_position_at_start(self):
        start = Position3D(lat=37.555, lon=126.970, alt_m=150)
        env = _make_env(start_position=start)
        _, info = env.reset()
        pos = info["position"]
        assert pos.lat == pytest.approx(start.lat)
        assert pos.lon == pytest.approx(start.lon)
        assert pos.alt_m == pytest.approx(start.alt_m)

    def test_reset_with_seed_deterministic(self):
        env = _make_env()
        obs1, _ = env.reset(seed=42)
        obs2, _ = env.reset(seed=42)
        np.testing.assert_array_equal(obs1, obs2)

    def test_reset_clears_step_count(self):
        env = _make_env()
        env.reset()
        env.step(np.array([0, 0, 0], dtype=np.float32))
        _, info = env.reset()
        assert info["step"] == 0


# ── step ──────────────────────────────────────────────────────────────


class TestStep:
    def test_step_returns_five_tuple(self):
        env = _make_env()
        env.reset()
        result = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert len(result) == 5
        obs, reward, terminated, truncated, info = result
        assert isinstance(obs, np.ndarray)
        assert isinstance(reward, float)
        assert isinstance(terminated, bool)
        assert isinstance(truncated, bool)
        assert isinstance(info, dict)

    def test_step_observation_shape(self):
        env = _make_env()
        env.reset()
        obs, *_ = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert obs.shape == (24,)

    def test_zero_action_moves_forward(self):
        """Zero deltas → drone continues on current heading."""
        env = _make_env(initial_heading_deg=90.0, initial_speed_ms=10.0, dt_sec=1.0)
        env.reset()
        _, info_before = env.reset()
        pos_before = info_before["position"]

        _, _, _, _, info_after = env.step(np.array([0, 0, 0], dtype=np.float32))
        pos_after = info_after["position"]

        # Heading 90° = East → lon should increase
        assert pos_after.lon > pos_before.lon
        assert pos_after.lat == pytest.approx(pos_before.lat, abs=0.0001)

    def test_heading_change(self):
        env = _make_env(initial_heading_deg=0.0, initial_speed_ms=10.0)
        env.reset()

        # Turn 90° east
        _, _, _, _, info = env.step(np.array([90, 0, 0], dtype=np.float32))
        assert info["heading_deg"] == pytest.approx(90.0)

    def test_speed_clamped_to_max(self):
        env = _make_env(max_speed_ms=20.0, initial_speed_ms=18.0)
        env.reset()
        _, _, _, _, info = env.step(np.array([0, 10, 0], dtype=np.float32))
        assert info["speed_ms"] == pytest.approx(20.0)

    def test_speed_clamped_to_min(self):
        env = _make_env(min_speed_ms=1.0, initial_speed_ms=3.0)
        env.reset()
        _, _, _, _, info = env.step(np.array([0, -10, 0], dtype=np.float32))
        assert info["speed_ms"] == pytest.approx(1.0)

    def test_altitude_clamped_to_max(self):
        env = _make_env(altitude_max_m=400.0)
        cfg = env.cfg
        env = DroneRoutingEnv(
            config=DroneEnvConfig(
                start_position=Position3D(lat=37.56, lon=126.95, alt_m=395),
                goal_position=cfg.goal_position,
                altitude_max_m=400.0,
            )
        )
        env.reset()
        _, _, _, _, info = env.step(np.array([0, 0, 10], dtype=np.float32))
        assert info["position"].alt_m == pytest.approx(400.0)

    def test_altitude_clamped_to_min(self):
        env = DroneRoutingEnv(
            config=DroneEnvConfig(
                start_position=Position3D(lat=37.56, lon=126.95, alt_m=35),
                goal_position=Position3D(lat=37.57, lon=127.01, alt_m=100),
                altitude_min_m=30.0,
            )
        )
        env.reset()
        _, _, _, _, info = env.step(np.array([0, 0, -10], dtype=np.float32))
        assert info["position"].alt_m == pytest.approx(30.0)


# ── reward ────────────────────────────────────────────────────────────


class TestReward:
    def test_approach_positive_reward(self):
        """Moving toward goal yields positive approach reward."""
        # Goal is east → heading 90° moves toward it
        env = _make_env(initial_heading_deg=90.0)
        env.reset()
        _, reward, _, _, info = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert info["reward_breakdown"]["approach"] > 0

    def test_moving_away_negative_approach(self):
        """Moving away from goal yields negative approach reward."""
        # Goal is east → heading 270° (west) moves away
        env = _make_env(initial_heading_deg=270.0)
        env.reset()
        _, reward, _, _, info = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert info["reward_breakdown"]["approach"] < 0

    def test_arrival_bonus(self):
        """Arriving at goal gives large bonus."""
        goal = Position3D(lat=37.56, lon=126.9501, alt_m=100)
        env = DroneRoutingEnv(
            config=DroneEnvConfig(
                start_position=Position3D(lat=37.56, lon=126.95, alt_m=100),
                goal_position=goal,
                initial_heading_deg=90.0,
                initial_speed_ms=10.0,
                arrival_threshold_m=50.0,
            )
        )
        env.reset()
        # Move toward goal (very close)
        _, _, terminated, _, info = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert info["reward_breakdown"]["arrival"] == pytest.approx(100.0)
        assert terminated is True

    def test_separation_violation_penalty(self):
        """Nearby drone within separation → penalty."""
        nearby_pos = Position3D(lat=37.56, lon=126.9501, alt_m=100)
        env = _make_env(initial_heading_deg=90.0)
        env.set_nearby_drones([(nearby_pos, Velocity3D())])
        env.reset()
        _, _, _, _, info = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert info["reward_breakdown"]["separation_violation"] < 0

    def test_time_penalty_applied(self):
        env = _make_env()
        env.reset()
        _, _, _, _, info = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert info["reward_breakdown"]["time"] == pytest.approx(-0.1)


# ── termination ───────────────────────────────────────────────────────


class TestTermination:
    def test_terminated_on_arrival(self):
        goal = Position3D(lat=37.56, lon=126.9501, alt_m=100)
        env = DroneRoutingEnv(
            config=DroneEnvConfig(
                start_position=Position3D(lat=37.56, lon=126.95, alt_m=100),
                goal_position=goal,
                initial_heading_deg=90.0,
                initial_speed_ms=10.0,
                arrival_threshold_m=50.0,
            )
        )
        env.reset()
        _, _, terminated, _, _ = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert terminated is True

    def test_terminated_on_battery_depleted(self):
        env = DroneRoutingEnv(
            config=DroneEnvConfig(
                start_position=Position3D(lat=37.56, lon=126.95, alt_m=100),
                goal_position=Position3D(lat=37.70, lon=127.10, alt_m=100),
                initial_battery_pct=0.05,
                battery_drain_per_sec=0.1,
                dt_sec=1.0,
            )
        )
        env.reset()
        _, _, terminated, _, info = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert info["battery_pct"] == pytest.approx(0.0)
        assert terminated is True

    def test_truncated_on_max_steps(self):
        env = _make_env(max_steps=2)
        env.reset()
        env.step(np.array([0, 0, 0], dtype=np.float32))
        _, _, terminated, truncated, _ = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert truncated is True

    def test_not_terminated_mid_flight(self):
        env = _make_env()
        env.reset()
        _, _, terminated, truncated, _ = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert terminated is False
        assert truncated is False


# ── weather observation ───────────────────────────────────────────────


class TestWeatherObservation:
    def test_weather_reflected_in_obs(self):
        env = _make_env()
        env.set_weather(_weather(wind_speed=15.0, wind_deg=180.0, rain=10.0))
        obs, _ = env.reset()
        # obs[16] = wind_speed/30, obs[17] = wind_deg/360, obs[18] = rain/20
        assert obs[16] == pytest.approx(15.0 / 30.0)
        assert obs[17] == pytest.approx(180.0 / 360.0)
        assert obs[18] == pytest.approx(10.0 / 20.0)

    def test_no_weather_zeros(self):
        env = _make_env()
        obs, _ = env.reset()
        assert obs[16] == pytest.approx(0.0)
        assert obs[17] == pytest.approx(0.0)
        assert obs[18] == pytest.approx(0.0)


# ── battery observation ───────────────────────────────────────────────


class TestBatteryObservation:
    def test_battery_drains_over_steps(self):
        env = _make_env(initial_battery_pct=100.0, battery_drain_per_sec=1.0, dt_sec=1.0)
        env.reset()
        _, _, _, _, info = env.step(np.array([0, 0, 0], dtype=np.float32))
        assert info["battery_pct"] == pytest.approx(99.0)
