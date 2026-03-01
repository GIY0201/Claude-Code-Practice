"""Tests for LLM ATC controller."""

import pytest

from ai.llm.controller import ATCController
from ai.llm.briefing import SystemState
from models.chat import ChatIntent, ChatRequest


class TestATCController:
    """ATC 컨트롤러 mock 모드 테스트."""

    def setup_method(self):
        self.ctrl = ATCController(api_key="")

    def test_controller_is_mock(self):
        assert self.ctrl.is_mock is True

    def test_flight_plan_intent(self):
        """비행계획 생성 명령."""
        req = ChatRequest(message="홍대에서 강남역까지 드론 배송")
        resp = self.ctrl.process(req)
        assert resp.intent == ChatIntent.FLIGHT_PLAN
        assert resp.flight_plan is not None
        assert resp.requires_confirmation is True
        assert "비행계획" in resp.message

    def test_altitude_change_intent(self):
        """고도 변경 명령."""
        req = ChatRequest(message="드론 3번 고도 올려")
        resp = self.ctrl.process(req)
        assert resp.intent == ChatIntent.ALTITUDE_CHANGE
        assert resp.action is not None
        assert resp.action["drone_id"] == "D3"
        assert resp.requires_confirmation is True

    def test_speed_change_intent(self):
        """속도 변경 명령."""
        req = ChatRequest(message="드론 5번 속도 줄여")
        resp = self.ctrl.process(req)
        assert resp.intent == ChatIntent.SPEED_CHANGE
        assert resp.action["drone_id"] == "D5"

    def test_hold_intent(self):
        """홀딩 명령."""
        req = ChatRequest(message="전체 드론 홀딩")
        resp = self.ctrl.process(req)
        assert resp.intent == ChatIntent.HOLD
        assert resp.action["drone_id"] == "ALL"

    def test_return_to_base_intent(self):
        """귀환 명령."""
        req = ChatRequest(message="드론 2번 귀환시켜")
        resp = self.ctrl.process(req)
        assert resp.intent == ChatIntent.RETURN_TO_BASE
        assert resp.action["drone_id"] == "D2"

    def test_notam_intent(self):
        """NOTAM 설정 명령."""
        req = ChatRequest(message="A구역 비행금지 설정, 30분")
        resp = self.ctrl.process(req)
        assert resp.intent == ChatIntent.SET_NOTAM
        assert resp.action is not None
        assert "NOTAM" in resp.message
        assert resp.requires_confirmation is True

    def test_briefing_intent(self):
        """브리핑 요청."""
        self.ctrl.set_system_state(SystemState(active_drones=5, holding_drones=2))
        req = ChatRequest(message="현재 상황 브리핑해줘")
        resp = self.ctrl.process(req)
        assert resp.intent == ChatIntent.BRIEFING
        assert "총 7대" in resp.message

    def test_general_query_intent(self):
        """일반 질의."""
        req = ChatRequest(message="안녕하세요")
        resp = self.ctrl.process(req)
        assert resp.intent == ChatIntent.GENERAL_QUERY

    def test_session_id_auto_generated(self):
        """세션 ID 자동 생성."""
        req = ChatRequest(message="브리핑")
        resp = self.ctrl.process(req)
        assert resp.session_id is not None
        assert len(resp.session_id) > 0

    def test_session_id_preserved(self):
        """세션 ID 유지."""
        req = ChatRequest(message="브리핑", session_id="test-session")
        resp = self.ctrl.process(req)
        assert resp.session_id == "test-session"

    def test_sky_callsign_recognition(self):
        """SKY-NNN 호출부호 인식."""
        req = ChatRequest(message="SKY-007 고도 올려")
        resp = self.ctrl.process(req)
        assert resp.action["drone_id"] == "SKY-007"


class TestCommandHistory:
    """대화 이력 관리 테스트."""

    def setup_method(self):
        self.ctrl = ATCController(api_key="")

    def test_history_recorded(self):
        """대화 이력이 기록됨."""
        req = ChatRequest(message="브리핑", session_id="hist-1")
        self.ctrl.process(req)
        history = self.ctrl.get_history("hist-1")
        assert len(history) == 2  # user + assistant
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    def test_history_multiple_messages(self):
        """여러 메시지 이력."""
        for msg in ["브리핑", "드론 1번 고도 올려", "전체 홀딩"]:
            self.ctrl.process(ChatRequest(message=msg, session_id="hist-2"))
        history = self.ctrl.get_history("hist-2")
        assert len(history) == 6  # 3 user + 3 assistant

    def test_history_separate_sessions(self):
        """세션별 이력 분리."""
        self.ctrl.process(ChatRequest(message="브리핑", session_id="s1"))
        self.ctrl.process(ChatRequest(message="홀딩", session_id="s2"))
        assert len(self.ctrl.get_history("s1")) == 2
        assert len(self.ctrl.get_history("s2")) == 2

    def test_history_empty_session(self):
        """존재하지 않는 세션 이력."""
        history = self.ctrl.get_history("nonexistent")
        assert history == []

    def test_history_content(self):
        """이력 내용 확인."""
        self.ctrl.process(ChatRequest(message="브리핑", session_id="hist-3"))
        history = self.ctrl.get_history("hist-3")
        assert history[0].content == "브리핑"
        assert len(history[1].content) > 0  # assistant 응답 있음
