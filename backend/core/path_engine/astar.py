"""A* 3D 경로탐색 엔진."""

import heapq
import math
from dataclasses import dataclass, field

from models.common import Position3D


# 지구 반지름 (미터)
EARTH_RADIUS_M = 6_371_000


def haversine_distance(a: Position3D, b: Position3D) -> float:
    """두 WGS84 좌표 간 수평 거리 (미터)."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = math.radians(b.lat - a.lat)
    dlon = math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def distance_3d(a: Position3D, b: Position3D) -> float:
    """두 좌표 간 3D 거리 (미터)."""
    horiz = haversine_distance(a, b)
    vert = abs(a.alt_m - b.alt_m)
    return math.sqrt(horiz ** 2 + vert ** 2)


@dataclass(order=True)
class _Node:
    """A* 탐색 노드."""
    f_cost: float
    g_cost: float = field(compare=False)
    position: Position3D = field(compare=False)
    parent: "_Node | None" = field(default=None, compare=False)


class AStarPathfinder:
    """3D A* 경로탐색기.

    Args:
        grid_resolution_m: 수평 그리드 해상도 (미터). 기본 100m.
        altitude_step_m: 수직 그리드 해상도 (미터). 기본 10m.
        altitude_min_m: 최소 비행 고도.
        altitude_max_m: 최대 비행 고도.
        altitude_change_penalty: 고도 변경 페널티 가중치.
        restricted_zones: 금지 구역 리스트. 각 구역은
            {"center": Position3D, "radius_m": float} 형태 (단순 원형) 또는
            {"polygon": list[tuple[float,float]], "floor_m": float, "ceiling_m": float} 형태.
    """

    def __init__(
        self,
        grid_resolution_m: float = 100.0,
        altitude_step_m: float = 10.0,
        altitude_min_m: float = 30.0,
        altitude_max_m: float = 400.0,
        altitude_change_penalty: float = 2.0,
        reference_lat: float = 37.5665,
    ):
        self.grid_res = grid_resolution_m
        self.alt_step = altitude_step_m
        self.alt_min = altitude_min_m
        self.alt_max = altitude_max_m
        self.alt_penalty = altitude_change_penalty
        self._restricted_zones: list[dict] = []
        # 고정 그리드 스텝 (기준 위도 기반) — 전체 탐색 영역에서 일관된 그리드 보장
        self._lat_step = self.grid_res / 111_320
        self._lon_step = self.grid_res / (111_320 * math.cos(math.radians(reference_lat)))

    def set_restricted_zones(self, zones: list[dict]) -> None:
        """금지 구역 설정.

        각 구역 포맷:
            {"center_lat": float, "center_lon": float, "radius_m": float,
             "floor_m": float, "ceiling_m": float}
        """
        self._restricted_zones = zones

    def is_restricted(self, pos: Position3D) -> bool:
        """좌표가 금지구역 내에 있는지 판정."""
        for zone in self._restricted_zones:
            center = Position3D(
                lat=zone["center_lat"],
                lon=zone["center_lon"],
                alt_m=0,
            )
            dist = haversine_distance(pos, center)
            floor_m = zone.get("floor_m", 0)
            ceiling_m = zone.get("ceiling_m", 999999)
            if dist <= zone["radius_m"] and floor_m <= pos.alt_m <= ceiling_m:
                return True
        return False

    def _heuristic(self, a: Position3D, b: Position3D) -> float:
        """A* 휴리스틱: 수평 Haversine + 고도차."""
        return haversine_distance(a, b) + abs(a.alt_m - b.alt_m) * self.alt_penalty

    def _snap_to_grid(self, pos: Position3D) -> Position3D:
        """좌표를 고정 그리드에 맞춤."""
        snapped_lat = round(pos.lat / self._lat_step) * self._lat_step
        snapped_lon = round(pos.lon / self._lon_step) * self._lon_step
        snapped_alt = round((pos.alt_m - self.alt_min) / self.alt_step) * self.alt_step + self.alt_min
        snapped_alt = max(self.alt_min, min(self.alt_max, snapped_alt))
        return Position3D(lat=snapped_lat, lon=snapped_lon, alt_m=snapped_alt)

    def _get_neighbors(self, pos: Position3D) -> list[Position3D]:
        """현재 노드의 이웃 노드 (26방향 3D)."""
        neighbors = []
        for dlat in (-self._lat_step, 0, self._lat_step):
            for dlon in (-self._lon_step, 0, self._lon_step):
                for dalt in (-self.alt_step, 0, self.alt_step):
                    if dlat == 0 and dlon == 0 and dalt == 0:
                        continue
                    new_alt = pos.alt_m + dalt
                    if new_alt < self.alt_min or new_alt > self.alt_max:
                        continue
                    neighbor = Position3D(
                        lat=pos.lat + dlat,
                        lon=pos.lon + dlon,
                        alt_m=new_alt,
                    )
                    if not self.is_restricted(neighbor):
                        neighbors.append(neighbor)
        return neighbors

    def _pos_key(self, pos: Position3D) -> tuple[float, float, float]:
        """Position3D를 해시 가능한 키로 변환."""
        return (round(pos.lat, 8), round(pos.lon, 8), round(pos.alt_m, 1))

    def find_path(
        self,
        start: Position3D,
        goal: Position3D,
        max_iterations: int = 50_000,
    ) -> list[Position3D]:
        """A* 경로 탐색.

        Args:
            start: 출발 좌표.
            goal: 도착 좌표.
            max_iterations: 최대 탐색 반복 횟수.

        Returns:
            시작→도착 Position3D 리스트. 경로를 찾지 못하면 빈 리스트.
        """
        # 시작/도착을 그리드에 맞춤
        start_snapped = self._snap_to_grid(start)
        goal_snapped = self._snap_to_grid(goal)

        if self.is_restricted(start_snapped) or self.is_restricted(goal_snapped):
            return []

        start_node = _Node(
            f_cost=self._heuristic(start_snapped, goal_snapped),
            g_cost=0.0,
            position=start_snapped,
        )

        open_heap: list[_Node] = [start_node]
        closed: set[tuple[float, float, float]] = set()
        g_costs: dict[tuple[float, float, float], float] = {
            self._pos_key(start_snapped): 0.0
        }

        goal_key = self._pos_key(goal_snapped)
        iterations = 0

        while open_heap and iterations < max_iterations:
            iterations += 1
            current = heapq.heappop(open_heap)
            current_key = self._pos_key(current.position)

            if current_key == goal_key:
                # 경로 복원
                path = []
                node: _Node | None = current
                while node is not None:
                    path.append(node.position)
                    node = node.parent
                path.reverse()
                # 원래 시작/도착 좌표로 교체
                path[0] = start
                path[-1] = goal
                return path

            if current_key in closed:
                continue
            closed.add(current_key)

            for neighbor_pos in self._get_neighbors(current.position):
                neighbor_key = self._pos_key(neighbor_pos)
                if neighbor_key in closed:
                    continue

                # 이동 비용: 3D 거리 + 고도 변화 페널티
                move_cost = distance_3d(current.position, neighbor_pos)
                alt_change = abs(neighbor_pos.alt_m - current.position.alt_m)
                g_new = current.g_cost + move_cost + alt_change * self.alt_penalty

                if g_new < g_costs.get(neighbor_key, float("inf")):
                    g_costs[neighbor_key] = g_new
                    f_new = g_new + self._heuristic(neighbor_pos, goal_snapped)
                    neighbor_node = _Node(
                        f_cost=f_new,
                        g_cost=g_new,
                        position=neighbor_pos,
                        parent=current,
                    )
                    heapq.heappush(open_heap, neighbor_node)

        return []  # 경로 없음
