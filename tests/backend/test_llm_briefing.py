"""Tests for LLM briefing generator."""

import pytest

from ai.llm.briefing import BriefingGenerator, SystemState
from ai.llm.prompts.briefing import BRIEFING_SYSTEM_PROMPT, build_briefing_user_prompt


# ── SystemState ──────────────────────────────────────────


class TestSystemState:
    """SystemState 데이터 구성 테스트."""

    def test_default_state(self):
        state = SystemState()
        assert state.active_drones == 0
        assert state.holding_drones == 0
        assert state.emergency_drones == []
        assert state.conflicts == []
        assert state.weather is None
        assert state.airspace_restrictions == []

    def test_to_dict(self):
        state = SystemState(
            active_drones=5,
            holding_drones=2,
            emergency_drones=["D1"],
            conflicts=[{"pair": "D2-D3", "distance_m": 80}],
            weather={"wind_speed_ms": 12, "rain_1h_mm": 3},
            airspace_restrictions=["A구역 비행금지"],
        )
        d = state.to_dict()
        assert d["active_drones"] == 5
        assert d["emergency_drones"] == ["D1"]
        assert len(d["conflicts"]) == 1
        assert d["weather"]["wind_speed_ms"] == 12

    def test_to_dict_empty(self):
        d = SystemState().to_dict()
        assert d["active_drones"] == 0
        assert d["weather"] is None


# ── BriefingGenerator ────────────────────────────────────


class TestBriefingGenerator:
    """브리핑 생성기 mock 모드 테스트."""

    def setup_method(self):
        self.gen = BriefingGenerator(api_key="")

    def test_generator_is_mock(self):
        assert self.gen.is_mock is True

    def test_normal_briefing(self):
        """정상 운항 브리핑."""
        state = SystemState(active_drones=8, holding_drones=2)
        briefing = self.gen.generate(state)
        assert "총 10대" in briefing
        assert "비행 중: 8대" in briefing
        assert "홀딩 대기: 2대" in briefing
        assert "비상 상황: 없음" in briefing
        assert "정상 운항" in briefing

    def test_emergency_briefing(self):
        """비상 드론 포함 브리핑."""
        state = SystemState(
            active_drones=5,
            emergency_drones=["SKY-007", "SKY-012"],
        )
        briefing = self.gen.generate(state)
        assert "비상 상황: 2건" in briefing
        assert "SKY-007" in briefing
        assert "SKY-012" in briefing
        assert "비상 드론 우선 처리" in briefing

    def test_conflict_briefing(self):
        """충돌 위험 포함 브리핑."""
        state = SystemState(
            active_drones=10,
            conflicts=[
                {"pair": "D1-D2", "distance_m": 75},
                {"pair": "D3-D5", "distance_m": 90},
            ],
        )
        briefing = self.gen.generate(state)
        assert "충돌 위험: 2건" in briefing
        assert "D1-D2" in briefing
        assert "모니터링 강화" in briefing

    def test_weather_briefing(self):
        """기상 데이터 포함 브리핑."""
        state = SystemState(
            active_drones=3,
            weather={"wind_speed_ms": 18, "rain_1h_mm": 8, "visibility_m": 800},
        )
        briefing = self.gen.generate(state)
        assert "풍속 18" in briefing
        assert "강수 8" in briefing
        assert "시정 800" in briefing
        assert "강풍 경고" in briefing
        assert "강수 경고" in briefing
        assert "시정 불량" in briefing

    def test_severe_weather_recommendation(self):
        """강풍 비행 중지 권고."""
        state = SystemState(
            active_drones=3,
            weather={"wind_speed_ms": 22},
        )
        briefing = self.gen.generate(state)
        assert "비행 중지 검토" in briefing

    def test_airspace_restrictions(self):
        """공역 제한 포함 브리핑."""
        state = SystemState(
            active_drones=5,
            airspace_restrictions=["A구역 비행금지 (30분)", "B구역 통제"],
        )
        briefing = self.gen.generate(state)
        assert "공역 제한: 2건" in briefing
        assert "A구역 비행금지" in briefing
        assert "B구역 통제" in briefing

    def test_no_weather_data(self):
        """기상 데이터 없는 경우."""
        state = SystemState(active_drones=1)
        briefing = self.gen.generate(state)
        assert "기상: 데이터 없음" in briefing

    def test_complex_scenario(self):
        """복합 시나리오 (비상 + 충돌 + 기상 + 공역제한)."""
        state = SystemState(
            active_drones=12,
            holding_drones=3,
            emergency_drones=["SKY-007"],
            conflicts=[{"pair": "D2-D4", "distance_m": 60}],
            weather={"wind_speed_ms": 16, "rain_1h_mm": 2, "visibility_m": 3000},
            airspace_restrictions=["A구역 NOTAM"],
        )
        briefing = self.gen.generate(state)
        assert "총 15대" in briefing
        assert "비상 상황: 1건" in briefing
        assert "충돌 위험: 1건" in briefing
        assert "강풍 경고" in briefing
        assert "A구역 NOTAM" in briefing


# ── Prompts ──────────────────────────────────────────────


class TestBriefingPrompts:
    """브리핑 프롬프트 테스트."""

    def test_system_prompt_not_empty(self):
        assert len(BRIEFING_SYSTEM_PROMPT) > 50

    def test_build_user_prompt_normal(self):
        state = {"active_drones": 5, "holding_drones": 0, "emergency_drones": []}
        prompt = build_briefing_user_prompt(state)
        assert "활성 드론: 5대" in prompt
        assert "비상 드론: 없음" in prompt

    def test_build_user_prompt_with_weather(self):
        state = {
            "active_drones": 3,
            "weather": {"wind_speed_ms": 10, "rain_1h_mm": 2, "visibility_m": 5000},
        }
        prompt = build_briefing_user_prompt(state)
        assert "풍속 10" in prompt
