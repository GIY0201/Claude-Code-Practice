"""자연어 → 비행계획(FlightPlanCreate) 변환 파서.

사용자의 자연어 입력을 Claude API (또는 mock)로 분석하여
구조화된 FlightPlanCreate 객체로 변환한다.
지오코딩은 geopy Nominatim을 사용하며, 실패 시 서울 기본 좌표로 fallback.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from models.common import Position3D, Priority, MissionType
from models.flight_plan import FlightPlanCreate
from ai.llm.client import LLMClient
from ai.llm.prompts.flight_plan import (
    FLIGHT_PLAN_SYSTEM_PROMPT,
    FLIGHT_PLAN_TOOL,
    build_flight_plan_user_prompt,
)

logger = logging.getLogger(__name__)

# 서울 주요 지점 좌표 캐시 (지오코딩 fallback / 오프라인 테스트용)
SEOUL_LANDMARKS: dict[str, tuple[float, float]] = {
    "서울역": (37.5547, 126.9707),
    "강남역": (37.4979, 127.0276),
    "홍대": (37.5563, 126.9237),
    "홍대입구": (37.5563, 126.9237),
    "여의도": (37.5219, 126.9245),
    "잠실": (37.5133, 127.1001),
    "인천공항": (37.4602, 126.4407),
    "김포공항": (37.5586, 126.7906),
    "광화문": (37.5760, 126.9769),
    "이태원": (37.5345, 126.9946),
    "명동": (37.5636, 126.9869),
    "동대문": (37.5712, 127.0095),
    "신촌": (37.5550, 126.9366),
    "건대": (37.5404, 127.0696),
    "성수": (37.5445, 127.0557),
    "용산": (37.5299, 126.9648),
    "판교": (37.3948, 127.1112),
    "수원": (37.2636, 127.0286),
}


class FlightPlanParser:
    """자연어 비행계획 파서."""

    def __init__(self, api_key: str = "") -> None:
        self._llm = LLMClient(api_key)

    @property
    def is_mock(self) -> bool:
        return self._llm.is_mock

    def parse(self, text: str, drone_id: str = "AUTO") -> FlightPlanCreate:
        """자연어 텍스트를 FlightPlanCreate로 변환한다.

        Args:
            text: 사용자 자연어 입력 (예: "홍대에서 강남역까지 드론 배송, 고도 120m")
            drone_id: 드론 ID. "AUTO"이면 자동 생성.

        Returns:
            FlightPlanCreate 객체
        """
        # LLM으로 구조 추출
        extracted = self._extract_with_llm(text)

        # 지오코딩
        dep_name = extracted.get("departure", "서울역")
        dst_name = extracted.get("destination", "강남역")
        dep_pos = self._geocode(dep_name)
        dst_pos = self._geocode(dst_name)

        # 파라미터 조립
        altitude = extracted.get("cruise_altitude_m", 100.0)
        altitude = max(30.0, min(400.0, float(altitude)))

        speed = extracted.get("cruise_speed_ms", 10.0)
        speed = max(1.0, min(30.0, float(speed)))

        priority_str = extracted.get("priority", "NORMAL")
        try:
            priority = Priority(priority_str)
        except ValueError:
            priority = Priority.NORMAL

        mission_str = extracted.get("mission_type", "DELIVERY")
        try:
            mission = MissionType(mission_str)
        except ValueError:
            mission = MissionType.DELIVERY

        if drone_id == "AUTO":
            drone_id = f"D-{id(text) % 10000:04d}"

        return FlightPlanCreate(
            drone_id=drone_id,
            departure_position=dep_pos,
            destination_position=dst_pos,
            departure_time=datetime.now(timezone.utc) + timedelta(minutes=5),
            cruise_altitude_m=altitude,
            cruise_speed_ms=speed,
            priority=priority,
            mission_type=mission,
        )

    def _extract_with_llm(self, text: str) -> dict:
        """Claude API (또는 mock)로 자연어에서 비행계획 정보를 추출한다."""
        messages = [
            {"role": "user", "content": build_flight_plan_user_prompt(text)},
        ]
        result = self._llm.chat(
            messages=messages,
            tools=[FLIGHT_PLAN_TOOL],
            system=FLIGHT_PLAN_SYSTEM_PROMPT,
        )

        if result.get("type") == "tool_use" and result.get("name") == "extract_flight_plan":
            return result.get("input", {})

        # tool_use가 아닌 경우 기본값 반환
        logger.warning("LLM이 tool_use를 사용하지 않음 — 기본값 사용")
        return {"departure": "서울역", "destination": "강남역"}

    def _geocode(self, place_name: str) -> Position3D:
        """장소명을 Position3D 좌표로 변환한다.

        1. SEOUL_LANDMARKS 캐시 확인
        2. geopy Nominatim 호출
        3. 실패 시 서울 중심 fallback
        """
        # 캐시 확인
        if place_name in SEOUL_LANDMARKS:
            lat, lon = SEOUL_LANDMARKS[place_name]
            return Position3D(lat=lat, lon=lon, alt_m=0)

        # geopy Nominatim
        try:
            from geopy.geocoders import Nominatim
            geolocator = Nominatim(user_agent="skymind-utm", timeout=5)
            location = geolocator.geocode(place_name)
            if location:
                return Position3D(lat=location.latitude, lon=location.longitude, alt_m=0)
        except Exception as e:
            logger.warning("지오코딩 실패 (%s): %s", place_name, e)

        # fallback: 서울 중심
        logger.info("지오코딩 fallback — 서울 중심 좌표 사용: %s", place_name)
        return Position3D(lat=37.5665, lon=126.9780, alt_m=0)
