"""DAA 회피 기동 전략.

CPA 위반이 감지되면 우선순위에 따라 회피 기동을 결정한다.
회피 전략 우선순위: 속도 조절 → 고도 변경 → 수평 우회 → 일시정지(hold).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from models.common import Position3D, Velocity3D, Priority
from core.deconfliction.cpa import CPAResult


class ManeuverType(str, Enum):
    """회피 기동 유형."""
    SPEED_CHANGE = "SPEED_CHANGE"
    ALTITUDE_CHANGE = "ALTITUDE_CHANGE"
    LATERAL_OFFSET = "LATERAL_OFFSET"
    HOLD = "HOLD"


@dataclass
class AvoidanceCommand:
    """회피 기동 명령."""
    drone_id: str
    maneuver_type: ManeuverType
    target_speed_ms: float | None = None
    target_alt_m: float | None = None
    heading_offset_deg: float | None = None
    reason: str = ""


# 우선순위 서열 (높을수록 우선)
_PRIORITY_RANK: dict[Priority, int] = {
    Priority.LOW: 0,
    Priority.NORMAL: 1,
    Priority.HIGH: 2,
    Priority.EMERGENCY: 3,
}


@dataclass
class DroneState:
    """회피 판단에 필요한 드론 상태."""
    drone_id: str
    position: Position3D
    velocity: Velocity3D
    speed_ms: float
    heading: float
    priority: Priority = Priority.NORMAL


def _yielding_drone(a: DroneState, b: DroneState) -> tuple[DroneState, DroneState]:
    """양보해야 할 드론(yielder)과 유지할 드론(keeper)을 결정한다.

    낮은 우선순위 드론이 양보한다. 같으면 ID 기준 후순위가 양보.
    """
    rank_a = _PRIORITY_RANK[a.priority]
    rank_b = _PRIORITY_RANK[b.priority]
    if rank_a < rank_b:
        return a, b  # a가 양보
    if rank_b < rank_a:
        return b, a  # b가 양보
    # 동일 우선순위 → ID 사전순 후순위가 양보
    if a.drone_id > b.drone_id:
        return a, b
    return b, a


def resolve_conflict(
    cpa: CPAResult,
    state_a: DroneState,
    state_b: DroneState,
    *,
    speed_reduction_factor: float = 0.3,
    altitude_offset_m: float = 40.0,
    lateral_offset_deg: float = 15.0,
    min_speed_ms: float = 1.0,
) -> list[AvoidanceCommand]:
    """CPA 위반에 대해 회피 기동 명령을 생성한다.

    전략 우선순위:
    1. 속도 감속 — 양보 드론의 속도를 30%로 줄여 시간 분리
    2. 고도 변경 — 수직 이격이 부족하면 고도를 40m 변경
    3. 수평 우회 — 수평 이격이 부족하면 헤딩을 15° 오프셋
    4. 일시정지 — 위 방법 모두 불가 시 정지

    Args:
        cpa: CPA 계산 결과.
        state_a, state_b: 두 드론의 현재 상태.
        speed_reduction_factor: 감속 비율 (0.3 = 30%로 감속).
        altitude_offset_m: 고도 변경량 (m).
        lateral_offset_deg: 수평 우회 각도 (°).
        min_speed_ms: 최소 속도 (m/s).

    Returns:
        양보 드론에 대한 AvoidanceCommand 리스트 (보통 1개).
    """
    yielder, keeper = _yielding_drone(state_a, state_b)

    # 전략 1: 속도 감속 — t_cpa가 충분히 미래이면 감속으로 해결 가능
    if cpa.t_cpa_sec > 3.0:
        new_speed = max(min_speed_ms, yielder.speed_ms * speed_reduction_factor)
        return [AvoidanceCommand(
            drone_id=yielder.drone_id,
            maneuver_type=ManeuverType.SPEED_CHANGE,
            target_speed_ms=round(new_speed, 2),
            reason=f"Decelerate to avoid {keeper.drone_id} (CPA={cpa.d_cpa_m:.0f}m in {cpa.t_cpa_sec:.1f}s)",
        )]

    # 전략 2: 고도 변경 — 수직 이격 확보
    if cpa.vertical_sep_m < 30.0:
        # 양보 드론을 위 또는 아래로 이동 (위 우선)
        target_alt = yielder.position.alt_m + altitude_offset_m
        if target_alt > 400.0:
            target_alt = yielder.position.alt_m - altitude_offset_m
        target_alt = max(30.0, min(400.0, target_alt))

        return [AvoidanceCommand(
            drone_id=yielder.drone_id,
            maneuver_type=ManeuverType.ALTITUDE_CHANGE,
            target_alt_m=round(target_alt, 1),
            reason=f"Altitude change to avoid {keeper.drone_id} (v_sep={cpa.vertical_sep_m:.0f}m)",
        )]

    # 전략 3: 수평 우회 — 헤딩 오프셋
    if cpa.horizontal_sep_m < 100.0:
        # 오른쪽 회피 (국제 관례)
        offset = lateral_offset_deg
        return [AvoidanceCommand(
            drone_id=yielder.drone_id,
            maneuver_type=ManeuverType.LATERAL_OFFSET,
            heading_offset_deg=offset,
            reason=f"Lateral offset to avoid {keeper.drone_id} (h_sep={cpa.horizontal_sep_m:.0f}m)",
        )]

    # 전략 4: 일시정지 (최후 수단)
    return [AvoidanceCommand(
        drone_id=yielder.drone_id,
        maneuver_type=ManeuverType.HOLD,
        target_speed_ms=0.0,
        reason=f"Hold to avoid {keeper.drone_id} (d_cpa={cpa.d_cpa_m:.0f}m)",
    )]
