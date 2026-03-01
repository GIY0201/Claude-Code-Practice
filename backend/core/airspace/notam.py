"""NOTAM(Notice to Airmen) 파서.

텍스트 NOTAM 또는 자연어 입력을 AirspaceZoneCreate 객체로 변환한다.
구조화된 NOTAM 형식과 자연어 NOTAM 모두 지원.
"""

from __future__ import annotations

import math
import re
import uuid
import logging
from datetime import datetime, timedelta, timezone

from models.common import ZoneType
from models.airspace import AirspaceZoneCreate

logger = logging.getLogger(__name__)

# 서울 주요 지점 좌표 (NOTAM 파싱용)
KNOWN_LOCATIONS: dict[str, tuple[float, float]] = {
    "서울역": (37.5547, 126.9707),
    "강남": (37.4979, 127.0276),
    "여의도": (37.5219, 126.9245),
    "잠실": (37.5133, 127.1001),
    "광화문": (37.5760, 126.9769),
    "용산": (37.5299, 126.9648),
    "홍대": (37.5563, 126.9237),
    "인천공항": (37.4602, 126.4407),
    "김포공항": (37.5586, 126.7906),
}


def _generate_circle_polygon(
    center_lat: float, center_lon: float, radius_m: float, num_points: int = 32,
) -> dict:
    """원형 GeoJSON Polygon을 생성한다.

    Args:
        center_lat: 중심 위도
        center_lon: 중심 경도
        radius_m: 반경 (미터)
        num_points: 폴리곤 꼭짓점 수

    Returns:
        GeoJSON Polygon dict
    """
    coords = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        # 위도 1도 ≈ 111320m
        dlat = (radius_m * math.cos(angle)) / 111320
        # 경도 1도 ≈ 111320 * cos(lat)
        dlon = (radius_m * math.sin(angle)) / (111320 * math.cos(math.radians(center_lat)))
        coords.append([center_lon + dlon, center_lat + dlat])

    # 폐합
    coords.append(coords[0])

    return {
        "type": "Polygon",
        "coordinates": [coords],
    }


class NOTAMParser:
    """NOTAM 텍스트 → AirspaceZoneCreate 변환."""

    def parse_text(self, text: str) -> AirspaceZoneCreate:
        """구조화된 NOTAM 텍스트 또는 자연어를 AirspaceZoneCreate로 변환한다.

        지원 형식:
        1. "A구역 비행금지 설정, 30분" (자연어)
        2. "서울역 반경 500m 비행금지, 1시간" (자연어)
        3. 좌표 직접 지정: "37.5547,126.9707 반경 1000m 제한구역"

        Args:
            text: NOTAM 텍스트

        Returns:
            AirspaceZoneCreate 객체
        """
        # 위치 추출
        center_lat, center_lon = self._extract_location(text)

        # 반경 추출 (기본 500m)
        radius_m = self._extract_radius(text)

        # 구역 타입 추출
        zone_type = self._extract_zone_type(text)

        # 제한시간 추출
        duration_minutes = self._extract_duration(text)

        # 구역 이름 추출
        name = self._extract_zone_name(text)

        # GeoJSON 생성
        geometry = _generate_circle_polygon(center_lat, center_lon, radius_m)

        # 제한 사항
        restrictions = [text.strip()]
        if duration_minutes:
            expire_time = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
            restrictions.append(f"만료: {expire_time.strftime('%Y-%m-%d %H:%M UTC')}")

        return AirspaceZoneCreate(
            name=name,
            zone_type=zone_type,
            geometry=geometry,
            floor_altitude_m=0.0,
            ceiling_altitude_m=400.0,
            restrictions=restrictions,
        )

    def parse_natural_language(self, text: str, llm_client=None) -> AirspaceZoneCreate:
        """LLM을 사용한 자연어 NOTAM 파싱.

        LLM이 없거나 mock 모드이면 규칙 기반 파싱으로 fallback.
        """
        # 현재는 규칙 기반 파싱으로 통일 (LLM 확장 가능)
        return self.parse_text(text)

    def _extract_location(self, text: str) -> tuple[float, float]:
        """텍스트에서 위치 좌표를 추출한다."""
        # 좌표 직접 지정: "37.5547,126.9707"
        coord_match = re.search(r"(\d+\.\d+)\s*[,\s]\s*(\d+\.\d+)", text)
        if coord_match:
            lat = float(coord_match.group(1))
            lon = float(coord_match.group(2))
            if 33 <= lat <= 44 and 124 <= lon <= 132:  # 한국 좌표 범위
                return lat, lon

        # 알려진 장소명 매칭
        for place, (lat, lon) in KNOWN_LOCATIONS.items():
            if place in text:
                return lat, lon

        # fallback: 서울 중심
        return 37.5665, 126.9780

    def _extract_radius(self, text: str) -> float:
        """텍스트에서 반경을 추출한다 (기본 500m)."""
        match = re.search(r"반경\s*(\d+(?:\.\d+)?)\s*(m|km|미터|킬로)", text)
        if match:
            value = float(match.group(1))
            unit = match.group(2)
            if unit in ("km", "킬로"):
                return value * 1000
            return value
        return 500.0

    def _extract_zone_type(self, text: str) -> ZoneType:
        """텍스트에서 구역 타입을 추출한다."""
        if any(kw in text for kw in ["비행금지", "금지"]):
            return ZoneType.RESTRICTED
        if any(kw in text for kw in ["통제", "제한"]):
            return ZoneType.CONTROLLED
        if any(kw in text for kw in ["비상", "긴급"]):
            return ZoneType.EMERGENCY_ONLY
        return ZoneType.RESTRICTED  # NOTAM 기본값

    def _extract_duration(self, text: str) -> float | None:
        """텍스트에서 제한 시간(분)을 추출한다."""
        # "N분" 패턴
        min_match = re.search(r"(\d+)\s*분", text)
        if min_match:
            return float(min_match.group(1))

        # "N시간" 패턴
        hr_match = re.search(r"(\d+)\s*시간", text)
        if hr_match:
            return float(hr_match.group(1)) * 60

        return None

    def _extract_zone_name(self, text: str) -> str:
        """텍스트에서 구역 이름을 추출한다."""
        # "X구역" 패턴
        zone_match = re.search(r"([A-Z가-힣]+구역)", text)
        if zone_match:
            return f"NOTAM-{zone_match.group(1)}"

        # 장소명 매칭
        for place in KNOWN_LOCATIONS:
            if place in text:
                return f"NOTAM-{place}"

        return f"NOTAM-{uuid.uuid4().hex[:6].upper()}"
