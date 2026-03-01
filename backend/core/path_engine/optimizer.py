"""경로 최적화 (스무딩, 단축)."""

import math
from models.common import Position3D


def smooth_path(
    path: list[Position3D],
    weight_smooth: float = 0.3,
    weight_data: float = 0.5,
    tolerance: float = 0.00001,
    max_iterations: int = 100,
) -> list[Position3D]:
    """Gradient descent 기반 경로 스무딩.

    시작점과 끝점은 고정하고, 중간 경유점들을 스무딩한다.

    Args:
        path: 원본 경로 (Position3D 리스트).
        weight_smooth: 스무딩 가중치 (높을수록 부드러움).
        weight_data: 원본 경로 유지 가중치 (높을수록 원본에 가까움).
        tolerance: 수렴 판단 임계값.
        max_iterations: 최대 반복 횟수.

    Returns:
        스무딩된 경로.
    """
    if len(path) <= 2:
        return list(path)

    # 좌표를 리스트로 변환 (수정 가능)
    coords = [[p.lat, p.lon, p.alt_m] for p in path]
    smoothed = [c[:] for c in coords]

    for _ in range(max_iterations):
        change = 0.0
        for i in range(1, len(smoothed) - 1):
            for j in range(3):  # lat, lon, alt
                old = smoothed[i][j]
                smoothed[i][j] += weight_data * (coords[i][j] - smoothed[i][j])
                smoothed[i][j] += weight_smooth * (
                    smoothed[i - 1][j] + smoothed[i + 1][j] - 2.0 * smoothed[i][j]
                )
                change += abs(old - smoothed[i][j])
        if change < tolerance:
            break

    return [
        Position3D(lat=c[0], lon=c[1], alt_m=c[2])
        for c in smoothed
    ]


def simplify_path(path: list[Position3D], epsilon_m: float = 10.0) -> list[Position3D]:
    """Douglas-Peucker 알고리즘으로 경로 단순화.

    Args:
        path: 원본 경로.
        epsilon_m: 최대 허용 오차 (미터).

    Returns:
        단순화된 경로.
    """
    if len(path) <= 2:
        return list(path)

    # 가장 먼 점 찾기
    max_dist = 0.0
    max_idx = 0
    start, end = path[0], path[-1]

    for i in range(1, len(path) - 1):
        dist = _point_to_line_distance(path[i], start, end)
        if dist > max_dist:
            max_dist = dist
            max_idx = i

    if max_dist > epsilon_m:
        left = simplify_path(path[: max_idx + 1], epsilon_m)
        right = simplify_path(path[max_idx:], epsilon_m)
        return left[:-1] + right
    else:
        return [path[0], path[-1]]


def _point_to_line_distance(
    point: Position3D, line_start: Position3D, line_end: Position3D
) -> float:
    """점에서 두 점을 잇는 직선까지의 근사 거리 (미터)."""
    # 간단한 좌표 기반 근사 (소규모 영역)
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(point.lat))

    px = (point.lon - line_start.lon) * m_per_deg_lon
    py = (point.lat - line_start.lat) * m_per_deg_lat
    pz = point.alt_m - line_start.alt_m

    lx = (line_end.lon - line_start.lon) * m_per_deg_lon
    ly = (line_end.lat - line_start.lat) * m_per_deg_lat
    lz = line_end.alt_m - line_start.alt_m

    line_len_sq = lx * lx + ly * ly + lz * lz
    if line_len_sq == 0:
        return math.sqrt(px * px + py * py + pz * pz)

    t = max(0, min(1, (px * lx + py * ly + pz * lz) / line_len_sq))
    proj_x = t * lx
    proj_y = t * ly
    proj_z = t * lz

    return math.sqrt(
        (px - proj_x) ** 2 + (py - proj_y) ** 2 + (pz - proj_z) ** 2
    )
