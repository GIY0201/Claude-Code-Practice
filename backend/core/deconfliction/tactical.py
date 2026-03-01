"""Tactical DAA (Detect and Avoid) 엔진.

실시간으로 전체 드론의 CPA를 검사하고, 위반 감지 시 회피 기동을 결정한다.
MultiDroneSim의 매 틱에서 호출되어 회피 명령을 생성한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models.common import Position3D, Velocity3D, Priority
from core.deconfliction.cpa import compute_cpa, CPAResult
from core.deconfliction.avoidance import (
    AvoidanceCommand,
    DroneState,
    resolve_conflict,
)


@dataclass
class ConflictRecord:
    """충돌 위험 기록."""
    cpa: CPAResult
    commands: list[AvoidanceCommand]


@dataclass
class TacticalDAA:
    """Tactical DAA 엔진.

    매 틱마다 evaluate()를 호출하면, 모든 드론 쌍의 CPA를 검사하고
    위반 시 회피 기동 명령을 생성한다.

    Attributes:
        separation_h_m: 수평 최소 이격거리 (m).
        separation_v_m: 수직 최소 이격거리 (m).
        lookahead_sec: CPA 예측 시간 범위 (초).
        warning_sec: 경고 발생 시간 임계값 (초).
    """

    separation_h_m: float = 100.0
    separation_v_m: float = 30.0
    lookahead_sec: float = 120.0
    warning_sec: float = 60.0

    # 내부 상태: 현재 활성 충돌 목록
    _active_conflicts: list[ConflictRecord] = field(default_factory=list, init=False)

    @property
    def active_conflicts(self) -> list[ConflictRecord]:
        """현재 활성 충돌 목록."""
        return list(self._active_conflicts)

    @property
    def conflict_count(self) -> int:
        return len(self._active_conflicts)

    def evaluate(
        self,
        drones: dict[str, DroneState],
    ) -> list[AvoidanceCommand]:
        """전체 드론 쌍을 평가하고 회피 명령을 생성한다.

        Args:
            drones: {drone_id: DroneState} 딕셔너리.

        Returns:
            회피 기동 명령 리스트 (위반이 없으면 빈 리스트).
        """
        ids = list(drones.keys())
        self._active_conflicts = []
        all_commands: list[AvoidanceCommand] = []
        # 이미 회피 명령을 받은 드론 추적
        commanded_drones: set[str] = set()

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                sa = drones[ids[i]]
                sb = drones[ids[j]]

                cpa = compute_cpa(
                    sa.drone_id, sa.position, sa.velocity,
                    sb.drone_id, sb.position, sb.velocity,
                    self.separation_h_m, self.separation_v_m,
                )

                if not cpa.is_violation:
                    continue
                if cpa.t_cpa_sec > self.lookahead_sec:
                    continue

                # 충돌 위반 감지 — 회피 명령 생성
                commands = resolve_conflict(cpa, sa, sb)

                # 이미 명령받은 드론에게 중복 명령하지 않음
                commands = [
                    cmd for cmd in commands
                    if cmd.drone_id not in commanded_drones
                ]

                if commands:
                    for cmd in commands:
                        commanded_drones.add(cmd.drone_id)
                    all_commands.extend(commands)

                self._active_conflicts.append(
                    ConflictRecord(cpa=cpa, commands=commands)
                )

        return all_commands

    def evaluate_pair(
        self,
        state_a: DroneState,
        state_b: DroneState,
    ) -> tuple[CPAResult, list[AvoidanceCommand]]:
        """단일 드론 쌍의 CPA를 평가하고 회피 명령을 생성한다.

        Args:
            state_a, state_b: 드론 상태.

        Returns:
            (CPAResult, 회피 명령 리스트).
        """
        cpa = compute_cpa(
            state_a.drone_id, state_a.position, state_a.velocity,
            state_b.drone_id, state_b.position, state_b.velocity,
            self.separation_h_m, self.separation_v_m,
        )

        commands: list[AvoidanceCommand] = []
        if cpa.is_violation and cpa.t_cpa_sec <= self.lookahead_sec:
            commands = resolve_conflict(cpa, state_a, state_b)

        return cpa, commands

    def get_warnings(
        self,
        drones: dict[str, DroneState],
    ) -> list[CPAResult]:
        """경고 수준의 CPA만 반환한다 (위반은 아니지만 warning_sec 이내 접근).

        Args:
            drones: {drone_id: DroneState} 딕셔너리.

        Returns:
            경고 CPAResult 리스트.
        """
        ids = list(drones.keys())
        warnings: list[CPAResult] = []

        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                sa = drones[ids[i]]
                sb = drones[ids[j]]

                cpa = compute_cpa(
                    sa.drone_id, sa.position, sa.velocity,
                    sb.drone_id, sb.position, sb.velocity,
                    self.separation_h_m, self.separation_v_m,
                )

                if cpa.is_violation:
                    continue  # 위반은 evaluate()에서 처리
                if cpa.t_cpa_sec > self.warning_sec:
                    continue
                # 거리가 이격거리의 2배 이내면 경고
                if cpa.d_cpa_m < self.separation_h_m * 2:
                    warnings.append(cpa)

        return warnings
