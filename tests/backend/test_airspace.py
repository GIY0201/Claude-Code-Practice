"""공역 관리 모듈 테스트."""

import pytest
from models.common import Position3D, ZoneType
from models.airspace import AirspaceZone
from core.airspace import (
    AirspaceManager,
    create_seoul_default_zones,
    get_heading,
    is_eastbound,
    get_available_altitudes,
    assign_altitude,
    validate_altitude,
)


# --- AirspaceManager 테스트 ---

class TestAirspaceManager:

    def _make_manager_with_zone(self) -> AirspaceManager:
        mgr = AirspaceManager()
        zone = AirspaceZone(
            zone_id="TEST-001",
            name="테스트 금지구역",
            zone_type=ZoneType.RESTRICTED,
            geometry={
                "type": "Polygon",
                "coordinates": [[
                    [126.97, 37.55], [126.99, 37.55],
                    [126.99, 37.57], [126.97, 37.57],
                    [126.97, 37.55],
                ]],
            },
            floor_altitude_m=0,
            ceiling_altitude_m=300,
        )
        mgr.add_zone(zone)
        return mgr

    def test_add_and_list_zones(self):
        mgr = self._make_manager_with_zone()
        zones = mgr.list_zones()
        assert len(zones) == 1
        assert zones[0].zone_id == "TEST-001"

    def test_is_flyable_inside_restricted(self):
        """금지구역 내부에서는 비행 불가."""
        mgr = self._make_manager_with_zone()
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        assert mgr.is_flyable(pos) is False

    def test_is_flyable_outside_restricted(self):
        """금지구역 외부에서는 비행 가능."""
        mgr = self._make_manager_with_zone()
        pos = Position3D(lat=37.50, lon=126.90, alt_m=100)
        assert mgr.is_flyable(pos) is True

    def test_is_flyable_above_ceiling(self):
        """금지구역 상한 고도 위는 비행 가능."""
        mgr = self._make_manager_with_zone()
        pos = Position3D(lat=37.56, lon=126.98, alt_m=350)
        assert mgr.is_flyable(pos) is True

    def test_get_zone_type_restricted(self):
        mgr = self._make_manager_with_zone()
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        assert mgr.get_zone_type_at(pos) == ZoneType.RESTRICTED

    def test_get_zone_type_free_default(self):
        mgr = self._make_manager_with_zone()
        pos = Position3D(lat=37.40, lon=126.80, alt_m=100)
        assert mgr.get_zone_type_at(pos) == ZoneType.FREE

    def test_remove_zone(self):
        mgr = self._make_manager_with_zone()
        assert mgr.remove_zone("TEST-001") is True
        assert mgr.list_zones() == []

    def test_default_seoul_zones(self):
        zones = create_seoul_default_zones()
        assert len(zones) >= 3  # 최소 금지구역 2개 + 관제구역 1개


# --- 고도 레이어 테스트 ---

class TestAltitudeLayer:

    def test_heading_east(self):
        """서→동 방향은 약 90°."""
        start = Position3D(lat=37.56, lon=126.97, alt_m=0)
        end = Position3D(lat=37.56, lon=127.00, alt_m=0)
        heading = get_heading(start, end)
        assert 80 < heading < 100

    def test_heading_west(self):
        """동→서 방향은 약 270°."""
        start = Position3D(lat=37.56, lon=127.00, alt_m=0)
        end = Position3D(lat=37.56, lon=126.97, alt_m=0)
        heading = get_heading(start, end)
        assert 260 < heading < 280

    def test_eastbound_gets_odd_layers(self):
        """동향 비행은 홀수 레이어."""
        altitudes = get_available_altitudes(90)  # 동쪽
        for alt in altitudes:
            layer_idx = round((alt - 30) / 10)
            assert layer_idx % 2 == 1

    def test_westbound_gets_even_layers(self):
        """서향 비행은 짝수 레이어."""
        altitudes = get_available_altitudes(270)  # 서쪽
        for alt in altitudes:
            layer_idx = round((alt - 30) / 10)
            assert layer_idx % 2 == 0

    def test_assign_altitude_preferred(self):
        """선호 고도에 가장 가까운 유효 레이어 배정."""
        alt = assign_altitude(heading=90, preferred_altitude_m=100)
        assert alt in get_available_altitudes(90)

    def test_validate_altitude_correct(self):
        """올바른 방향-고도 조합은 유효."""
        altitudes = get_available_altitudes(90)
        if altitudes:
            assert validate_altitude(90, altitudes[0]) is True

    def test_validate_altitude_wrong_layer(self):
        """잘못된 방향-고도 조합은 무효."""
        even_alts = get_available_altitudes(270)
        if even_alts:
            # 짝수 레이어를 동향에 사용하면 무효
            assert validate_altitude(90, even_alts[0]) is False
