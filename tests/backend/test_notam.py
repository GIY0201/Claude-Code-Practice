"""Tests for NOTAM parser."""

import math
import pytest

from core.airspace.notam import NOTAMParser, _generate_circle_polygon, KNOWN_LOCATIONS
from models.common import ZoneType


class TestCirclePolygon:
    """원형 GeoJSON 폴리곤 생성 테스트."""

    def test_polygon_structure(self):
        poly = _generate_circle_polygon(37.5665, 126.9780, 500)
        assert poly["type"] == "Polygon"
        assert len(poly["coordinates"]) == 1  # 외곽 링 1개
        coords = poly["coordinates"][0]
        assert len(coords) == 33  # 32점 + 폐합 1점

    def test_polygon_closed(self):
        """폴리곤이 폐합(시작=끝)인지 확인."""
        poly = _generate_circle_polygon(37.5665, 126.9780, 1000)
        coords = poly["coordinates"][0]
        assert coords[0] == coords[-1]

    def test_polygon_radius_approximate(self):
        """생성된 점들이 대략 지정 반경에 위치하는지 확인."""
        center_lat, center_lon = 37.5665, 126.9780
        radius_m = 1000.0
        poly = _generate_circle_polygon(center_lat, center_lon, radius_m)
        coords = poly["coordinates"][0]

        for lon, lat in coords[:-1]:
            dlat = (lat - center_lat) * 111320
            dlon = (lon - center_lon) * 111320 * math.cos(math.radians(center_lat))
            dist = math.sqrt(dlat ** 2 + dlon ** 2)
            assert dist == pytest.approx(radius_m, rel=0.05)  # 5% 허용


class TestNOTAMParser:
    """NOTAM 파서 테스트."""

    def setup_method(self):
        self.parser = NOTAMParser()

    def test_parse_simple_notam(self):
        """간단한 비행금지 NOTAM 파싱."""
        zone = self.parser.parse_text("A구역 비행금지 설정, 30분")
        assert zone.zone_type == ZoneType.RESTRICTED
        assert zone.name == "NOTAM-A구역"
        assert any("30분" in r or "만료" in r for r in zone.restrictions)

    def test_parse_with_location(self):
        """장소명 기반 NOTAM."""
        zone = self.parser.parse_text("서울역 반경 500m 비행금지, 1시간")
        assert zone.name == "NOTAM-서울역"
        assert zone.zone_type == ZoneType.RESTRICTED
        # geometry가 서울역 좌표 중심인지 확인
        coords = zone.geometry["coordinates"][0]
        center_lon = sum(c[0] for c in coords[:-1]) / (len(coords) - 1)
        center_lat = sum(c[1] for c in coords[:-1]) / (len(coords) - 1)
        assert center_lat == pytest.approx(37.5547, abs=0.01)

    def test_parse_with_coordinates(self):
        """좌표 직접 지정 NOTAM."""
        zone = self.parser.parse_text("37.5000,127.0000 반경 1km 제한구역")
        assert zone.zone_type == ZoneType.CONTROLLED
        coords = zone.geometry["coordinates"][0]
        center_lat = sum(c[1] for c in coords[:-1]) / (len(coords) - 1)
        assert center_lat == pytest.approx(37.5, abs=0.01)

    def test_parse_controlled_zone(self):
        """통제구역 파싱."""
        zone = self.parser.parse_text("여의도 통제구역 설정")
        assert zone.zone_type == ZoneType.CONTROLLED

    def test_parse_emergency_zone(self):
        """비상구역 파싱."""
        zone = self.parser.parse_text("잠실 비상구역 설정")
        assert zone.zone_type == ZoneType.EMERGENCY_ONLY

    def test_parse_radius_km(self):
        """킬로미터 반경 파싱."""
        zone = self.parser.parse_text("홍대 반경 2km 비행금지")
        # 2km = 2000m 반경의 polygon
        coords = zone.geometry["coordinates"][0]
        center_lat, center_lon = 37.5563, 126.9237
        # 첫 번째 점까지 거리가 약 2000m인지 확인
        lon, lat = coords[0]
        dlat = (lat - center_lat) * 111320
        dlon = (lon - center_lon) * 111320 * math.cos(math.radians(center_lat))
        dist = math.sqrt(dlat ** 2 + dlon ** 2)
        assert dist == pytest.approx(2000, rel=0.1)

    def test_parse_duration_hours(self):
        """시간 단위 제한시간 파싱."""
        zone = self.parser.parse_text("광화문 비행금지 2시간")
        assert any("만료" in r for r in zone.restrictions)

    def test_parse_default_radius(self):
        """반경 미지정 시 기본값 500m."""
        zone = self.parser.parse_text("서울역 비행금지")
        coords = zone.geometry["coordinates"][0]
        center_lat, center_lon = 37.5547, 126.9707
        lon, lat = coords[0]
        dlat = (lat - center_lat) * 111320
        dlon = (lon - center_lon) * 111320 * math.cos(math.radians(center_lat))
        dist = math.sqrt(dlat ** 2 + dlon ** 2)
        assert dist == pytest.approx(500, rel=0.1)

    def test_parse_natural_language(self):
        """자연어 NOTAM 파싱 (규칙 기반 fallback)."""
        zone = self.parser.parse_natural_language("용산 지역 30분간 비행금지")
        assert zone.zone_type == ZoneType.RESTRICTED
        assert "NOTAM" in zone.name

    def test_geometry_is_valid_geojson(self):
        """생성된 geometry가 유효한 GeoJSON인지 확인."""
        zone = self.parser.parse_text("강남 비행금지")
        assert zone.geometry["type"] == "Polygon"
        assert isinstance(zone.geometry["coordinates"], list)
        assert len(zone.geometry["coordinates"][0]) > 3
