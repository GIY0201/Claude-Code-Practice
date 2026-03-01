"""고도 레이어 시스템.

방향별 고도 분리:
- 동→서 (heading 180°~360°): 짝수 레이어 (60m, 80m, 100m, ...)
- 서→동 (heading 0°~180°): 홀수 레이어 (70m, 90m, 110m, ...)
"""

import math

from models.common import Position3D


# 고도 레이어 설정
ALTITUDE_MIN_M = 30.0
ALTITUDE_MAX_M = 400.0
LAYER_STEP_M = 10.0


def get_heading(start: Position3D, end: Position3D) -> float:
    """두 좌표 간 방위각 계산 (degrees, 0=북, 시계 방향).

    Args:
        start: 출발 좌표.
        end: 도착 좌표.

    Returns:
        방위각 (0 ~ 360).
    """
    lat1 = math.radians(start.lat)
    lat2 = math.radians(end.lat)
    dlon = math.radians(end.lon - start.lon)

    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

    bearing = math.degrees(math.atan2(x, y))
    return bearing % 360


def is_eastbound(heading: float) -> bool:
    """동향 비행 여부 (heading 0°~180°)."""
    return 0 <= heading < 180


def get_available_altitudes(heading: float) -> list[float]:
    """비행 방향에 따른 사용 가능 고도 레이어 목록.

    동향(0°~180°): 홀수 레이어 (70m, 90m, 110m, ...)
    서향(180°~360°): 짝수 레이어 (60m, 80m, 100m, ...)

    Returns:
        고도 리스트 (미터).
    """
    altitudes = []
    alt = ALTITUDE_MIN_M

    while alt <= ALTITUDE_MAX_M:
        layer_index = round((alt - ALTITUDE_MIN_M) / LAYER_STEP_M)
        if is_eastbound(heading):
            # 홀수 레이어
            if layer_index % 2 == 1:
                altitudes.append(alt)
        else:
            # 짝수 레이어
            if layer_index % 2 == 0:
                altitudes.append(alt)
        alt += LAYER_STEP_M

    return altitudes


def assign_altitude(
    heading: float,
    preferred_altitude_m: float | None = None,
) -> float:
    """비행 방향에 따른 적정 고도 배정.

    Args:
        heading: 비행 방위각 (degrees).
        preferred_altitude_m: 선호 고도 (있으면 가장 가까운 유효 레이어 선택).

    Returns:
        배정된 고도 (미터).
    """
    available = get_available_altitudes(heading)
    if not available:
        return ALTITUDE_MIN_M

    if preferred_altitude_m is None:
        # 기본: 중간 고도
        return available[len(available) // 2]

    # 선호 고도에 가장 가까운 유효 레이어
    return min(available, key=lambda a: abs(a - preferred_altitude_m))


def validate_altitude(heading: float, altitude_m: float) -> bool:
    """주어진 방향과 고도가 레이어 규칙을 준수하는지 검증."""
    available = get_available_altitudes(heading)
    return altitude_m in available
