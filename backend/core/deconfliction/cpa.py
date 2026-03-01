"""CPA (Closest Point of Approach) 충돌 예측 엔진.

두 드론의 현재 위치/속도로부터 가장 근접하는 시점(t_cpa)과
그때의 거리(d_cpa)를 계산한다. 이격거리 위반 시 충돌 경고를 생성한다.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from models.common import Position3D, Velocity3D
from core.path_engine.astar import haversine_distance


@dataclass
class CPAResult:
    """CPA 계산 결과."""
    drone_id_a: str
    drone_id_b: str
    t_cpa_sec: float       # CPA까지 남은 시간 (초). 음수면 이미 지남.
    d_cpa_m: float          # CPA 시점의 예상 거리 (미터)
    current_distance_m: float  # 현재 거리 (미터)
    horizontal_sep_m: float    # CPA 시점 수평 거리 (미터)
    vertical_sep_m: float      # CPA 시점 수직 거리 (미터)
    is_violation: bool         # 이격거리 위반 여부


def _pos_to_meters(pos: Position3D, ref_lat: float = 37.5665) -> tuple[float, float, float]:
    """WGS84 좌표를 기준점 대비 미터 단위로 변환한다 (근사치)."""
    x = (pos.lon - 126.978) * 111_320.0 * math.cos(math.radians(ref_lat))
    y = (pos.lat - ref_lat) * 111_320.0
    z = pos.alt_m
    return x, y, z


def compute_cpa(
    id_a: str, pos_a: Position3D, vel_a: Velocity3D,
    id_b: str, pos_b: Position3D, vel_b: Velocity3D,
    separation_h_m: float = 100.0,
    separation_v_m: float = 30.0,
) -> CPAResult:
    """두 드론 간 CPA를 계산한다.

    CPA 공식:
        dr = pos_b - pos_a  (상대 위치)
        dv = vel_b - vel_a  (상대 속도)
        t_cpa = -dot(dr, dv) / dot(dv, dv)
        d_cpa = |dr + dv * t_cpa|

    Args:
        id_a, id_b: 드론 ID.
        pos_a, pos_b: 현재 위치.
        vel_a, vel_b: 현재 속도 (m/s).
        separation_h_m: 수평 최소 이격거리 (m).
        separation_v_m: 수직 최소 이격거리 (m).

    Returns:
        CPAResult.
    """
    # 위치를 미터로 변환
    xa, ya, za = _pos_to_meters(pos_a)
    xb, yb, zb = _pos_to_meters(pos_b)

    # 상대 위치/속도
    drx = xb - xa
    dry = yb - ya
    drz = zb - za

    dvx = vel_b.vx - vel_a.vx
    dvy = vel_b.vy - vel_a.vy
    dvz = vel_b.vz - vel_a.vz

    # dot products
    dv_dot = dvx * dvx + dvy * dvy + dvz * dvz
    dr_dot_dv = drx * dvx + dry * dvy + drz * dvz

    # 현재 거리
    current_h = math.sqrt(drx * drx + dry * dry)
    current_v = abs(drz)
    current_dist = math.sqrt(drx * drx + dry * dry + drz * drz)

    if dv_dot < 1e-10:
        # 상대 속도가 거의 0 — 거리 변하지 않음
        return CPAResult(
            drone_id_a=id_a, drone_id_b=id_b,
            t_cpa_sec=0.0, d_cpa_m=current_dist,
            current_distance_m=current_dist,
            horizontal_sep_m=current_h, vertical_sep_m=current_v,
            is_violation=current_h < separation_h_m and current_v < separation_v_m,
        )

    t_cpa = -dr_dot_dv / dv_dot
    # 미래만 관심 (과거 CPA는 0으로 클램프)
    t_cpa_clamped = max(0.0, t_cpa)

    # CPA 시점의 상대 위치
    cpa_x = drx + dvx * t_cpa_clamped
    cpa_y = dry + dvy * t_cpa_clamped
    cpa_z = drz + dvz * t_cpa_clamped

    d_cpa = math.sqrt(cpa_x * cpa_x + cpa_y * cpa_y + cpa_z * cpa_z)
    h_sep = math.sqrt(cpa_x * cpa_x + cpa_y * cpa_y)
    v_sep = abs(cpa_z)

    is_violation = h_sep < separation_h_m and v_sep < separation_v_m

    return CPAResult(
        drone_id_a=id_a, drone_id_b=id_b,
        t_cpa_sec=round(t_cpa_clamped, 3),
        d_cpa_m=round(d_cpa, 2),
        current_distance_m=round(current_dist, 2),
        horizontal_sep_m=round(h_sep, 2),
        vertical_sep_m=round(v_sep, 2),
        is_violation=is_violation,
    )


def check_all_pairs(
    drones: dict[str, tuple[Position3D, Velocity3D]],
    separation_h_m: float = 100.0,
    separation_v_m: float = 30.0,
    lookahead_sec: float = 120.0,
) -> list[CPAResult]:
    """전체 드론 쌍에 대해 CPA를 검사하고, 위험한 쌍만 반환한다.

    Args:
        drones: {drone_id: (position, velocity)} 딕셔너리.
        separation_h_m: 수평 최소 이격거리.
        separation_v_m: 수직 최소 이격거리.
        lookahead_sec: CPA 예측 시간 범위 (초). 이보다 먼 미래는 무시.

    Returns:
        이격거리를 위반하는 CPAResult 목록 (t_cpa <= lookahead_sec).
    """
    ids = list(drones.keys())
    violations: list[CPAResult] = []

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            pos_a, vel_a = drones[ids[i]]
            pos_b, vel_b = drones[ids[j]]
            result = compute_cpa(
                ids[i], pos_a, vel_a,
                ids[j], pos_b, vel_b,
                separation_h_m, separation_v_m,
            )
            if result.is_violation and result.t_cpa_sec <= lookahead_sec:
                violations.append(result)

    return violations
