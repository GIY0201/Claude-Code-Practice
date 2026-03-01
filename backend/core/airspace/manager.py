"""공역 구역 관리."""

import math

from models.common import Position3D, ZoneType
from models.airspace import AirspaceZone


class AirspaceManager:
    """공역 구역 관리자.

    GeoJSON Polygon 기반으로 공역 구역을 관리하고,
    특정 좌표가 어떤 구역에 속하는지 판정한다.
    """

    def __init__(self) -> None:
        self._zones: dict[str, AirspaceZone] = {}

    def add_zone(self, zone: AirspaceZone) -> None:
        """공역 구역 추가."""
        self._zones[zone.zone_id] = zone

    def remove_zone(self, zone_id: str) -> bool:
        """공역 구역 제거. 성공 시 True."""
        return self._zones.pop(zone_id, None) is not None

    def get_zone(self, zone_id: str) -> AirspaceZone | None:
        """구역 ID로 조회."""
        return self._zones.get(zone_id)

    def list_zones(self, active_only: bool = True) -> list[AirspaceZone]:
        """모든 구역 조회."""
        zones = list(self._zones.values())
        if active_only:
            zones = [z for z in zones if z.active]
        return zones

    def get_zone_at(self, position: Position3D) -> list[AirspaceZone]:
        """특정 좌표가 속하는 모든 공역 구역 반환."""
        result = []
        for zone in self._zones.values():
            if not zone.active:
                continue
            if not (zone.floor_altitude_m <= position.alt_m <= zone.ceiling_altitude_m):
                continue
            if self._point_in_polygon(position.lat, position.lon, zone.geometry):
                result.append(zone)
        return result

    def is_flyable(self, position: Position3D) -> bool:
        """해당 좌표에서 비행 가능 여부 판정.

        RESTRICTED 구역 내부이면 비행 불가.
        """
        zones = self.get_zone_at(position)
        for zone in zones:
            if zone.zone_type == ZoneType.RESTRICTED:
                return False
        return True

    def requires_clearance(self, position: Position3D) -> bool:
        """해당 좌표에서 비행 승인이 필요한지 판정."""
        zones = self.get_zone_at(position)
        for zone in zones:
            if zone.zone_type == ZoneType.CONTROLLED:
                return True
        return False

    def get_zone_type_at(self, position: Position3D) -> ZoneType:
        """해당 좌표의 가장 제한적인 공역 등급 반환.

        우선순위: RESTRICTED > EMERGENCY_ONLY > CONTROLLED > FREE
        """
        zones = self.get_zone_at(position)
        if not zones:
            return ZoneType.FREE

        priority = {
            ZoneType.RESTRICTED: 0,
            ZoneType.EMERGENCY_ONLY: 1,
            ZoneType.CONTROLLED: 2,
            ZoneType.FREE: 3,
        }
        return min(zones, key=lambda z: priority[z.zone_type]).zone_type

    @staticmethod
    def _point_in_polygon(lat: float, lon: float, geometry: dict) -> bool:
        """Ray casting 알고리즘으로 점이 GeoJSON Polygon 내부인지 판정.

        Args:
            lat: 위도.
            lon: 경도.
            geometry: GeoJSON geometry 객체 {"type": "Polygon", "coordinates": [[[lon, lat], ...]]}.

        Returns:
            내부이면 True.
        """
        if geometry.get("type") != "Polygon":
            return False

        coordinates = geometry.get("coordinates", [])
        if not coordinates:
            return False

        # GeoJSON은 [longitude, latitude] 순서
        ring = coordinates[0]  # 외곽 링만 사용
        n = len(ring)
        inside = False

        j = n - 1
        for i in range(n):
            xi, yi = ring[i][0], ring[i][1]  # lon, lat
            xj, yj = ring[j][0], ring[j][1]

            if ((yi > lat) != (yj > lat)) and (
                lon < (xj - xi) * (lat - yi) / (yj - yi) + xi
            ):
                inside = not inside
            j = i

        return inside


def create_seoul_default_zones() -> list[AirspaceZone]:
    """서울 수도권 기본 공역 구역 생성 (테스트/개발용).

    Returns:
        기본 공역 구역 리스트.
    """
    zones = [
        # 김포공항 주변 — 비행 금지
        AirspaceZone(
            zone_id="RESTRICT-001",
            name="김포공항 비행금지구역",
            zone_type=ZoneType.RESTRICTED,
            geometry={
                "type": "Polygon",
                "coordinates": [[
                    [126.78, 37.57], [126.82, 37.57],
                    [126.82, 37.59], [126.78, 37.59],
                    [126.78, 37.57],
                ]],
            },
            floor_altitude_m=0,
            ceiling_altitude_m=400,
        ),
        # 용산 대통령실 주변 — 비행 금지
        AirspaceZone(
            zone_id="RESTRICT-002",
            name="용산 비행금지구역",
            zone_type=ZoneType.RESTRICTED,
            geometry={
                "type": "Polygon",
                "coordinates": [[
                    [126.97, 37.53], [126.99, 37.53],
                    [126.99, 37.54], [126.97, 37.54],
                    [126.97, 37.53],
                ]],
            },
            floor_altitude_m=0,
            ceiling_altitude_m=400,
        ),
        # 서울 도심 — 허가 필요
        AirspaceZone(
            zone_id="CTRL-001",
            name="서울 도심 관제구역",
            zone_type=ZoneType.CONTROLLED,
            geometry={
                "type": "Polygon",
                "coordinates": [[
                    [126.95, 37.54], [127.01, 37.54],
                    [127.01, 37.58], [126.95, 37.58],
                    [126.95, 37.54],
                ]],
            },
            floor_altitude_m=0,
            ceiling_altitude_m=200,
        ),
        # 한강 상공 — 자유 비행
        AirspaceZone(
            zone_id="FREE-001",
            name="한강 자유비행구역",
            zone_type=ZoneType.FREE,
            geometry={
                "type": "Polygon",
                "coordinates": [[
                    [126.89, 37.51], [127.10, 37.51],
                    [127.10, 37.53], [126.89, 37.53],
                    [126.89, 37.51],
                ]],
            },
            floor_altitude_m=30,
            ceiling_altitude_m=150,
        ),
    ]
    return zones
