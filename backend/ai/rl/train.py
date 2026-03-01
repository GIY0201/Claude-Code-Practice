"""Training pipeline for drone routing RL agent.

Provides :class:`TrainingRunner` to orchestrate end-to-end training with
curriculum reward shaping and periodic evaluation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ai.rl.agent import DroneAgent
from ai.rl.environment import DroneEnvConfig, DroneRoutingEnv
from ai.rl.reward import CurriculumRewardShaper


# ── callback ──────────────────────────────────────────────────────────


class CurriculumCallback:
    """Stable-Baselines3-compatible callback for curriculum reward shaping.

    Updates the environment's reward weights according to the
    :class:`CurriculumRewardShaper` schedule on every rollout step.
    """

    def __init__(self, shaper: CurriculumRewardShaper) -> None:
        from stable_baselines3.common.callbacks import BaseCallback

        self._shaper = shaper
        self._base_cls = BaseCallback
        # We wrap ourselves as an SB3 callback dynamically
        self._inner: BaseCallback | None = None

    def as_sb3_callback(self) -> object:
        """Return a proper SB3 BaseCallback instance."""
        from stable_baselines3.common.callbacks import BaseCallback

        shaper = self._shaper

        class _Callback(BaseCallback):
            def __init__(self) -> None:
                super().__init__(verbose=0)
                self.shaper = shaper
                self.current_phase = 1

            def _on_step(self) -> bool:
                self.current_phase = self.shaper.current_phase
                # Update internal tracking step
                self.shaper.get_weights(self.num_timesteps)
                return True

        cb = _Callback()
        self._inner = cb
        return cb

    @property
    def current_phase(self) -> int:
        if self._inner is not None and hasattr(self._inner, "current_phase"):
            return self._inner.current_phase
        return self._shaper.current_phase


# ── training runner ───────────────────────────────────────────────────


class TrainingRunner:
    """Orchestrate the full training pipeline.

    Parameters
    ----------
    output_dir :
        Directory for model checkpoints and logs.
    total_timesteps :
        Total environment steps for training.
    eval_freq :
        Evaluate every *eval_freq* timesteps.
    eval_episodes :
        Number of episodes per evaluation.
    env_config :
        Environment configuration.
    """

    def __init__(
        self,
        output_dir: str = "training_output",
        total_timesteps: int = 100_000,
        eval_freq: int = 10_000,
        eval_episodes: int = 5,
        env_config: DroneEnvConfig | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.total_timesteps = total_timesteps
        self.eval_freq = eval_freq
        self.eval_episodes = eval_episodes
        self.env_config = env_config or DroneEnvConfig()
        self._agent: DroneAgent | None = None
        self._shaper: CurriculumRewardShaper | None = None

    def _setup_agent(self) -> DroneAgent:
        return DroneAgent(env_config=self.env_config)

    def _setup_callbacks(self) -> list:
        """Build SB3 callback list."""
        self._shaper = CurriculumRewardShaper(self.total_timesteps)
        curriculum_cb = CurriculumCallback(self._shaper)

        callbacks = [curriculum_cb.as_sb3_callback()]

        # Add eval callback if eval_freq > 0
        if self.eval_freq > 0:
            from stable_baselines3.common.callbacks import EvalCallback

            eval_env = DroneRoutingEnv(config=self.env_config)
            eval_cb = EvalCallback(
                eval_env,
                best_model_save_path=os.path.join(self.output_dir, "best"),
                log_path=os.path.join(self.output_dir, "logs"),
                eval_freq=self.eval_freq,
                n_eval_episodes=self.eval_episodes,
                deterministic=True,
                verbose=0,
            )
            callbacks.append(eval_cb)

        return callbacks

    def run(self) -> dict:
        """Execute the full training pipeline.

        Returns
        -------
        dict with: final_eval (evaluation metrics), model_path, total_timesteps
        """
        os.makedirs(self.output_dir, exist_ok=True)

        self._agent = self._setup_agent()
        callbacks = self._setup_callbacks()

        self._agent.train(
            total_timesteps=self.total_timesteps,
            callback=callbacks,
        )

        # Save final model
        model_path = os.path.join(self.output_dir, "final_model")
        self._agent.save(model_path)

        # Final evaluation
        eval_result = self._agent.evaluate(n_episodes=self.eval_episodes)

        return {
            "final_eval": eval_result,
            "model_path": model_path,
            "total_timesteps": self.total_timesteps,
        }

    @property
    def agent(self) -> DroneAgent | None:
        return self._agent

    @property
    def shaper(self) -> CurriculumRewardShaper | None:
        return self._shaper
