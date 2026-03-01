"""Tests for LLM flight plan parser."""

import pytest
from unittest.mock import patch, MagicMock

from ai.llm.parser import FlightPlanParser, SEOUL_LANDMARKS
from ai.llm.client import LLMClient
from ai.llm.prompts.flight_plan import (
    FLIGHT_PLAN_SYSTEM_PROMPT,
    FLIGHT_PLAN_TOOL,
    build_flight_plan_user_prompt,
)
from models.common import Priority, MissionType


# ── FlightPlanParser (mock 모드) ─────────────────────────


class TestFlightPlanParser:
    """비행계획 파서 mock 모드 테스트."""

    def setup_method(self):
        self.parser = FlightPlanParser(api_key="")  # mock 모드

    def test_parser_is_mock(self):
        assert self.parser.is_mock is True

    def test_parse_basic_delivery(self):
        """기본 배송 비행계획 파싱."""
        plan = self.parser.parse("홍대에서 강남역까지 드론 배송")
        assert plan.departure_position.lat == pytest.approx(37.5563, abs=0.01)
        assert plan.destination_position.lat == pytest.approx(37.4979, abs=0.01)
        assert plan.mission_type == MissionType.DELIVERY
        assert plan.priority == Priority.NORMAL

    def test_parse_with_altitude(self):
        """고도 지정 파싱."""
        plan = self.parser.parse("서울역에서 여의도까지 고도 150m 배송")
        assert plan.cruise_altitude_m == 150.0

    def test_parse_with_speed(self):
        """속도 지정 파싱."""
        plan = self.parser.parse("홍대에서 잠실까지 속도 15 배송")
        assert plan.cruise_speed_ms == 15.0

    def test_parse_surveillance_mission(self):
        """감시 미션 유형 파싱."""
        plan = self.parser.parse("여의도에서 광화문까지 감시 비행")
        assert plan.mission_type == MissionType.SURVEILLANCE

    def test_parse_inspection_mission(self):
        """점검 미션 유형 파싱."""
        plan = self.parser.parse("서울역에서 용산까지 점검 드론")
        assert plan.mission_type == MissionType.INSPECTION

    def test_parse_emergency_mission(self):
        """비상 미션 + 우선순위 파싱."""
        plan = self.parser.parse("홍대에서 강남역까지 긴급 배송")
        assert plan.mission_type == MissionType.EMERGENCY_RESPONSE
        assert plan.priority == Priority.EMERGENCY

    def test_parse_altitude_clamping_low(self):
        """고도 하한 클램핑 (30m)."""
        plan = self.parser.parse("서울역에서 강남역까지 고도 10m 배송")
        assert plan.cruise_altitude_m >= 30.0

    def test_parse_altitude_clamping_high(self):
        """고도 상한 클램핑 (400m)."""
        plan = self.parser.parse("서울역에서 강남역까지 고도 500m 배송")
        assert plan.cruise_altitude_m <= 400.0

    def test_parse_default_values(self):
        """기본값 사용 확인."""
        plan = self.parser.parse("드론 보내줘")
        assert plan.cruise_altitude_m == 100.0
        assert plan.cruise_speed_ms == 10.0
        assert plan.priority == Priority.NORMAL
        assert plan.mission_type == MissionType.DELIVERY

    def test_parse_custom_drone_id(self):
        """커스텀 드론 ID 지정."""
        plan = self.parser.parse("홍대에서 강남까지", drone_id="SKY-001")
        assert plan.drone_id == "SKY-001"

    def test_parse_auto_drone_id(self):
        """자동 드론 ID 생성."""
        plan = self.parser.parse("홍대에서 강남역까지 배송")
        assert plan.drone_id.startswith("D-")

    def test_parse_departure_time(self):
        """출발 시각이 미래로 설정됨."""
        from datetime import datetime, timezone
        plan = self.parser.parse("홍대에서 강남역까지 배송")
        assert plan.departure_time > datetime.now(timezone.utc)


# ── Geocoding ─────────────────────────────────────────────


class TestGeocoding:
    """지오코딩 테스트."""

    def setup_method(self):
        self.parser = FlightPlanParser(api_key="")

    def test_landmark_cache_hit(self):
        """캐시된 랜드마크 좌표 반환."""
        pos = self.parser._geocode("서울역")
        assert pos.lat == pytest.approx(37.5547, abs=0.001)
        assert pos.lon == pytest.approx(126.9707, abs=0.001)

    def test_landmark_cache_gangnam(self):
        """강남역 캐시 확인."""
        pos = self.parser._geocode("강남역")
        assert pos.lat == pytest.approx(37.4979, abs=0.001)

    def test_unknown_place_fallback(self):
        """알 수 없는 장소명 → geopy 시도 후 fallback."""
        with patch("geopy.geocoders.Nominatim") as mock_nom:
            mock_nom.return_value.geocode.return_value = None
            pos = self.parser._geocode("알수없는장소XYZ")
            assert pos.lat == pytest.approx(37.5665, abs=0.01)
            assert pos.lon == pytest.approx(126.9780, abs=0.01)

    def test_geocode_exception_fallback(self):
        """지오코딩 예외 시 fallback."""
        with patch("geopy.geocoders.Nominatim") as mock_nom:
            mock_nom.return_value.geocode.side_effect = Exception("network error")
            pos = self.parser._geocode("에러장소")
            assert pos.lat == pytest.approx(37.5665, abs=0.01)

    def test_seoul_landmarks_count(self):
        """랜드마크 캐시에 충분한 항목."""
        assert len(SEOUL_LANDMARKS) >= 10


# ── Prompt Templates ──────────────────────────────────────


class TestPromptTemplates:
    """프롬프트 템플릿 빌드 테스트."""

    def test_system_prompt_not_empty(self):
        assert len(FLIGHT_PLAN_SYSTEM_PROMPT) > 100

    def test_tool_schema_has_required_fields(self):
        schema = FLIGHT_PLAN_TOOL["input_schema"]
        assert "departure" in schema["properties"]
        assert "destination" in schema["properties"]
        assert "cruise_altitude_m" in schema["properties"]
        assert schema["required"] == ["departure", "destination"]

    def test_build_user_prompt(self):
        prompt = build_flight_plan_user_prompt("홍대에서 강남까지 배송")
        assert "홍대에서 강남까지 배송" in prompt
        assert "extract_flight_plan" in prompt


# ── LLMClient mock 동작 ──────────────────────────────────


class TestLLMClientMock:
    """LLMClient mock 모드 단위 테스트."""

    def setup_method(self):
        self.client = LLMClient(api_key="")

    def test_client_is_mock(self):
        assert self.client.is_mock is True

    def test_mock_flight_plan_extraction(self):
        result = self.client._mock_flight_plan_extraction("홍대에서 강남역까지 배송")
        assert result["type"] == "tool_use"
        assert result["name"] == "extract_flight_plan"
        assert result["input"]["departure"] == "홍대"
        assert result["input"]["destination"] == "강남역"

    def test_mock_command_classification(self):
        result = self.client._mock_command_classification("드론 3번 고도 올려")
        assert result["type"] == "tool_use"
        assert result["input"]["intent"] == "ALTITUDE_CHANGE"
        assert result["input"]["drone_id"] == "D3"

    def test_mock_briefing(self):
        result = self.client._mock_briefing_text("브리핑")
        assert result["type"] == "text"
        assert "브리핑" in result["text"]
