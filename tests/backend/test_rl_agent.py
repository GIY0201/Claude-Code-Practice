"""Tests for PPO agent, curriculum reward shaping, and training runner."""

import os
import tempfile

import numpy as np
import pytest

from ai.rl.reward import CurriculumRewardShaper, RewardWeights, _PHASE_1, _PHASE_2, _PHASE_3
from ai.rl.agent import DroneAgent
from ai.rl.environment import DroneEnvConfig, DroneRoutingEnv
from ai.rl.train import CurriculumCallback, TrainingRunner


# ── RewardWeights ─────────────────────────────────────────────────────


class TestRewardWeights:
    def test_default_values(self):
        w = RewardWeights()
        assert w.approach == 1.0
        assert w.arrival == 100.0
        assert w.smoothness == -0.05

    def test_custom_values(self):
        w = RewardWeights(approach=2.0, arrival=200.0)
        assert w.approach == 2.0
        assert w.arrival == 200.0

    def test_phase1_no_avoidance(self):
        """Phase 1 weights disable avoidance penalties."""
        assert _PHASE_1.airspace_violation == 0.0
        assert _PHASE_1.separation_violation == 0.0
        assert _PHASE_1.energy == 0.0

    def test_phase3_all_active(self):
        """Phase 3 enables all reward components."""
        assert _PHASE_3.airspace_violation < 0
        assert _PHASE_3.separation_violation < 0
        assert _PHASE_3.energy < 0
        assert _PHASE_3.smoothness < 0


# ── CurriculumRewardShaper ────────────────────────────────────────────


class TestCurriculumPhases:
    def test_phase1_at_start(self):
        shaper = CurriculumRewardShaper(total_timesteps=100_000)
        shaper.get_weights(0)
        assert shaper.current_phase == 1

    def test_phase2_at_middle(self):
        shaper = CurriculumRewardShaper(total_timesteps=100_000)
        shaper.get_weights(50_000)
        assert shaper.current_phase == 2

    def test_phase3_at_end(self):
        shaper = CurriculumRewardShaper(total_timesteps=100_000)
        shaper.get_weights(80_000)
        assert shaper.current_phase == 3

    def test_weights_interpolation_phase1_to_phase2(self):
        """At Phase 1→2 boundary, avoidance penalties start increasing."""
        shaper = CurriculumRewardShaper(total_timesteps=100_000)
        w_early = shaper.get_weights(29_000)  # still Phase 1
        w_mid = shaper.get_weights(50_000)    # Phase 2 midpoint
        # Phase 1: no avoidance, Phase 2: partial avoidance
        assert w_early.airspace_violation == pytest.approx(0.0)
        assert w_mid.airspace_violation < 0

    def test_weights_interpolation_phase2_to_phase3(self):
        """At Phase 2→3 boundary, energy/smoothness penalties appear."""
        shaper = CurriculumRewardShaper(total_timesteps=100_000)
        w_phase2_end = shaper.get_weights(69_000)  # Phase 2 end
        w_phase3_mid = shaper.get_weights(85_000)   # Phase 3 mid
        # Energy should increase in magnitude from Phase 2 → 3
        assert abs(w_phase3_mid.energy) >= abs(w_phase2_end.energy)

    def test_invalid_total_timesteps(self):
        with pytest.raises(ValueError):
            CurriculumRewardShaper(total_timesteps=0)

    def test_shape_reward_phase1_ignores_avoidance(self):
        shaper = CurriculumRewardShaper(total_timesteps=100_000)
        breakdown = {
            "approach": 5.0,
            "arrival": 0.0,
            "airspace_violation": -50.0,
            "separation_violation": -30.0,
            "energy": -0.005,
            "time": -0.1,
        }
        shaped = shaper.shape_reward(breakdown, current_step=0)
        # In Phase 1, avoidance scale is 0.0, so those components vanish
        assert shaped == pytest.approx(5.0 + 0.0 + 0.0 + 0.0 + 0.0 + (-0.1 * 0.5), abs=0.5)

    def test_shape_reward_phase3_full(self):
        shaper = CurriculumRewardShaper(total_timesteps=100_000)
        breakdown = {
            "approach": 5.0,
            "arrival": 0.0,
            "airspace_violation": -50.0,
            "separation_violation": -30.0,
            "energy": -0.005,
            "time": -0.1,
        }
        shaped = shaper.shape_reward(breakdown, current_step=100_000)
        # At the end, all components at full weight
        expected = 5.0 + 0.0 + (-50.0) + (-30.0) + (-0.005) + (-0.1)
        assert shaped == pytest.approx(expected, abs=0.1)


# ── DroneAgent ────────────────────────────────────────────────────────


class TestDroneAgent:
    def test_creation(self):
        agent = DroneAgent()
        assert agent.model is not None
        assert agent.env_config is not None

    def test_custom_config(self):
        cfg = DroneEnvConfig(max_steps=50)
        agent = DroneAgent(env_config=cfg)
        assert agent.env_config.max_steps == 50

    def test_predict_shape(self):
        agent = DroneAgent()
        obs, _ = agent._env.reset()
        action = agent.predict(obs)
        assert action.shape == (3,)

    def test_predict_within_bounds(self):
        agent = DroneAgent()
        obs, _ = agent._env.reset()
        action = agent.predict(obs)
        low = agent._env.action_space.low
        high = agent._env.action_space.high
        assert np.all(action >= low) and np.all(action <= high)

    def test_train_short(self):
        """Train for a minimal number of steps without error."""
        cfg = DroneEnvConfig(max_steps=32)
        agent = DroneAgent(env_config=cfg, n_steps=32, batch_size=32, device="cpu")
        agent.train(total_timesteps=64)

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test_model")
            agent = DroneAgent(device="cpu")
            obs, _ = agent._env.reset()
            action_before = agent.predict(obs, deterministic=True)

            agent.save(path)
            loaded = DroneAgent.load(path)
            action_after = loaded.predict(obs, deterministic=True)
            np.testing.assert_array_almost_equal(action_before, action_after, decimal=4)

    def test_evaluate_returns_metrics(self):
        cfg = DroneEnvConfig(max_steps=10)
        agent = DroneAgent(env_config=cfg, device="cpu")
        result = agent.evaluate(n_episodes=2)
        assert "mean_reward" in result
        assert "std_reward" in result
        assert "mean_steps" in result
        assert "success_rate" in result
        assert "mean_battery_remaining" in result
        assert 0 <= result["success_rate"] <= 1.0


# ── CurriculumCallback ───────────────────────────────────────────────


class TestCurriculumCallback:
    def test_callback_creation(self):
        shaper = CurriculumRewardShaper(total_timesteps=1000)
        cb = CurriculumCallback(shaper)
        sb3_cb = cb.as_sb3_callback()
        assert sb3_cb is not None

    def test_callback_phase_tracking(self):
        shaper = CurriculumRewardShaper(total_timesteps=1000)
        cb = CurriculumCallback(shaper)
        assert cb.current_phase == 1
        shaper.get_weights(500)
        assert cb.current_phase == 2


# ── TrainingRunner ────────────────────────────────────────────────────


class TestTrainingRunner:
    def test_default_setup(self):
        runner = TrainingRunner()
        assert runner.total_timesteps == 100_000
        assert runner.eval_freq == 10_000

    def test_custom_config(self):
        cfg = DroneEnvConfig(max_steps=20)
        runner = TrainingRunner(
            total_timesteps=100,
            eval_freq=0,
            env_config=cfg,
        )
        assert runner.env_config.max_steps == 20

    def test_short_run(self):
        """Run a minimal training loop to verify the pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = DroneEnvConfig(max_steps=32)
            runner = TrainingRunner(
                output_dir=tmpdir,
                total_timesteps=64,
                eval_freq=0,  # disable eval callback for speed
                eval_episodes=1,
                env_config=cfg,
            )
            result = runner.run()
            assert "final_eval" in result
            assert "model_path" in result
            assert os.path.exists(result["model_path"] + ".zip")
            assert runner.agent is not None
            assert runner.shaper is not None
