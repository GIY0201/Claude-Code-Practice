"""PPO agent wrapper for drone routing.

Wraps Stable-Baselines3 PPO with convenience methods for training,
evaluation, saving, and loading drone routing policies.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from ai.rl.environment import DroneEnvConfig, DroneRoutingEnv


class DroneAgent:
    """Stable-Baselines3 PPO agent for drone routing.

    Parameters
    ----------
    env_config :
        Environment configuration.  ``None`` uses defaults.
    policy :
        SB3 policy class name.
    learning_rate :
        PPO learning rate.
    n_steps :
        Rollout buffer length per update.
    batch_size :
        Mini-batch size for PPO updates.
    n_epochs :
        Number of optimisation passes per update.
    gamma :
        Discount factor.
    device :
        Torch device (``"auto"``, ``"cpu"``, ``"cuda"``).
    """

    def __init__(
        self,
        env_config: DroneEnvConfig | None = None,
        policy: str = "MlpPolicy",
        learning_rate: float = 3e-4,
        n_steps: int = 2048,
        batch_size: int = 64,
        n_epochs: int = 10,
        gamma: float = 0.99,
        device: str = "auto",
    ) -> None:
        from stable_baselines3 import PPO

        self.env_config = env_config or DroneEnvConfig()
        self._env = DroneRoutingEnv(config=self.env_config)
        self.model = PPO(
            policy,
            self._env,
            learning_rate=learning_rate,
            n_steps=n_steps,
            batch_size=batch_size,
            n_epochs=n_epochs,
            gamma=gamma,
            device=device,
            verbose=0,
        )

    # ── training ──────────────────────────────────────────────────────

    def train(
        self,
        total_timesteps: int,
        callback: object | None = None,
        progress_bar: bool = False,
    ) -> None:
        """Train the agent for *total_timesteps*."""
        self.model.learn(
            total_timesteps=total_timesteps,
            callback=callback,
            progress_bar=progress_bar,
        )

    # ── inference ─────────────────────────────────────────────────────

    def predict(
        self, obs: np.ndarray, deterministic: bool = True
    ) -> np.ndarray:
        """Return an action for the given observation."""
        action, _states = self.model.predict(obs, deterministic=deterministic)
        return action

    # ── persistence ───────────────────────────────────────────────────

    def save(self, path: str) -> None:
        """Save model weights to *path*."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.model.save(path)

    @classmethod
    def load(
        cls,
        path: str,
        env_config: DroneEnvConfig | None = None,
    ) -> "DroneAgent":
        """Load a saved model."""
        from stable_baselines3 import PPO

        config = env_config or DroneEnvConfig()
        env = DroneRoutingEnv(config=config)
        agent = cls.__new__(cls)
        agent.env_config = config
        agent._env = env
        agent.model = PPO.load(path, env=env)
        return agent

    # ── evaluation ────────────────────────────────────────────────────

    def evaluate(self, n_episodes: int = 10) -> dict:
        """Run *n_episodes* and return aggregated statistics.

        Returns
        -------
        dict with keys: mean_reward, std_reward, mean_steps,
            success_rate, mean_battery_remaining
        """
        rewards: list[float] = []
        steps: list[int] = []
        successes: int = 0
        batteries: list[float] = []

        for _ in range(n_episodes):
            obs, info = self._env.reset()
            ep_reward = 0.0
            ep_steps = 0
            terminated = truncated = False

            while not (terminated or truncated):
                action = self.predict(obs, deterministic=True)
                obs, reward, terminated, truncated, info = self._env.step(action)
                ep_reward += reward
                ep_steps += 1

            rewards.append(ep_reward)
            steps.append(ep_steps)
            batteries.append(info.get("battery_pct", 0.0))
            if terminated and info.get("distance_to_goal", float("inf")) < self._env.cfg.arrival_threshold_m:
                successes += 1

        return {
            "mean_reward": float(np.mean(rewards)),
            "std_reward": float(np.std(rewards)),
            "mean_steps": float(np.mean(steps)),
            "success_rate": successes / max(n_episodes, 1),
            "mean_battery_remaining": float(np.mean(batteries)),
        }
