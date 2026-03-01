"""Curriculum reward shaping for drone routing RL training.

Implements a 3-phase curriculum that gradually increases task complexity:
  Phase 1 (0–30%):  Reach the goal (approach + arrival only)
  Phase 2 (30–70%): + Obstacle/drone avoidance
  Phase 3 (70–100%): + Energy efficiency + smooth flight
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RewardWeights:
    """Per-component reward weights applied during training."""

    approach: float = 1.0
    arrival: float = 100.0
    airspace_violation: float = -50.0
    separation_violation: float = -30.0
    energy: float = -0.01
    time: float = -0.1
    smoothness: float = -0.05


# ── phase definitions ─────────────────────────────────────────────────

_PHASE_1 = RewardWeights(
    approach=1.0,
    arrival=100.0,
    airspace_violation=0.0,
    separation_violation=0.0,
    energy=0.0,
    time=-0.05,
    smoothness=0.0,
)

_PHASE_2 = RewardWeights(
    approach=1.0,
    arrival=100.0,
    airspace_violation=-50.0,
    separation_violation=-30.0,
    energy=0.0,
    time=-0.1,
    smoothness=0.0,
)

_PHASE_3 = RewardWeights(
    approach=1.0,
    arrival=100.0,
    airspace_violation=-50.0,
    separation_violation=-30.0,
    energy=-0.01,
    time=-0.1,
    smoothness=-0.05,
)


def _lerp_weights(a: RewardWeights, b: RewardWeights, t: float) -> RewardWeights:
    """Linearly interpolate between two weight sets (t in [0, 1])."""
    t = max(0.0, min(1.0, t))
    return RewardWeights(
        approach=a.approach + (b.approach - a.approach) * t,
        arrival=a.arrival + (b.arrival - a.arrival) * t,
        airspace_violation=a.airspace_violation + (b.airspace_violation - a.airspace_violation) * t,
        separation_violation=a.separation_violation + (b.separation_violation - a.separation_violation) * t,
        energy=a.energy + (b.energy - a.energy) * t,
        time=a.time + (b.time - a.time) * t,
        smoothness=a.smoothness + (b.smoothness - a.smoothness) * t,
    )


# ── curriculum shaper ─────────────────────────────────────────────────


class CurriculumRewardShaper:
    """Manage reward weights across a 3-phase curriculum.

    Parameters
    ----------
    total_timesteps :
        Total training timesteps (used to compute phase boundaries).
    phase1_frac :
        Fraction of training for Phase 1. Default 0.3.
    phase2_frac :
        Fraction of training for Phase 2. Default 0.4 (Phase 3 gets the rest).
    """

    def __init__(
        self,
        total_timesteps: int,
        phase1_frac: float = 0.3,
        phase2_frac: float = 0.4,
    ) -> None:
        if total_timesteps <= 0:
            raise ValueError("total_timesteps must be positive")
        self.total_timesteps = total_timesteps
        self._phase1_end = int(total_timesteps * phase1_frac)
        self._phase2_end = int(total_timesteps * (phase1_frac + phase2_frac))
        self._current_step = 0

    # ── public API ────────────────────────────────────────────────────

    @property
    def current_phase(self) -> int:
        """Return the current curriculum phase (1, 2, or 3)."""
        if self._current_step < self._phase1_end:
            return 1
        if self._current_step < self._phase2_end:
            return 2
        return 3

    def get_weights(self, current_step: int) -> RewardWeights:
        """Return interpolated reward weights for a given training step."""
        self._current_step = current_step

        if current_step < self._phase1_end:
            # Within Phase 1 — interpolate from start to full Phase 1
            t = current_step / max(self._phase1_end, 1)
            return _lerp_weights(_PHASE_1, _PHASE_1, t)  # constant in P1

        if current_step < self._phase2_end:
            # Transition from Phase 1 → Phase 2
            t = (current_step - self._phase1_end) / max(
                self._phase2_end - self._phase1_end, 1
            )
            return _lerp_weights(_PHASE_1, _PHASE_2, t)

        # Transition from Phase 2 → Phase 3
        remaining = self.total_timesteps - self._phase2_end
        t = (current_step - self._phase2_end) / max(remaining, 1)
        return _lerp_weights(_PHASE_2, _PHASE_3, t)

    def shape_reward(self, reward_breakdown: dict, current_step: int) -> float:
        """Apply curriculum weights to a reward breakdown dict.

        The breakdown keys match :class:`RewardWeights` field names.
        Unknown keys are passed through at face value.
        """
        w = self.get_weights(current_step)
        total = 0.0

        # Map breakdown keys → weight multipliers
        weight_map = {
            "approach": w.approach / _PHASE_3.approach if _PHASE_3.approach else 1.0,
            "arrival": w.arrival / _PHASE_3.arrival if _PHASE_3.arrival else 1.0,
            "airspace_violation": (
                w.airspace_violation / _PHASE_3.airspace_violation
                if _PHASE_3.airspace_violation
                else 0.0
            ),
            "separation_violation": (
                w.separation_violation / _PHASE_3.separation_violation
                if _PHASE_3.separation_violation
                else 0.0
            ),
            "energy": (
                w.energy / _PHASE_3.energy if _PHASE_3.energy else 0.0
            ),
            "time": w.time / _PHASE_3.time if _PHASE_3.time else 1.0,
        }

        for key, value in reward_breakdown.items():
            scale = weight_map.get(key, 1.0)
            total += value * scale

        return total
