"""Tests for chat API endpoints."""

import pytest
from fastapi.testclient import TestClient

from main import app
from api.routes.chat import _controller, get_controller
from ai.llm.controller import ATCController
from ai.llm.briefing import SystemState


@pytest.fixture
def client():
    """테스트용 FastAPI 클라이언트 (mock LLM)."""
    # mock 컨트롤러를 사용하도록 교체
    mock_ctrl = ATCController(api_key="")
    import api.routes.chat as chat_module
    original = chat_module._controller
    chat_module._controller = mock_ctrl
    yield TestClient(app)
    chat_module._controller = original


class TestChatMessageEndpoint:
    """POST /api/chat/message 테스트."""

    def test_flight_plan_message(self, client):
        """비행계획 생성 요청."""
        resp = client.post("/api/chat/message", json={
            "message": "홍대에서 강남역까지 드론 배송",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "FLIGHT_PLAN"
        assert data["flight_plan"] is not None
        assert data["requires_confirmation"] is True
        assert "session_id" in data

    def test_altitude_change_message(self, client):
        """고도 변경 요청."""
        resp = client.post("/api/chat/message", json={
            "message": "드론 3번 고도 올려",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "ALTITUDE_CHANGE"
        assert data["action"]["drone_id"] == "D3"

    def test_briefing_message(self, client):
        """브리핑 요청."""
        resp = client.post("/api/chat/message", json={
            "message": "현재 상황 브리핑해줘",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "BRIEFING"
        assert len(data["message"]) > 10

    def test_hold_message(self, client):
        """홀딩 명령."""
        resp = client.post("/api/chat/message", json={
            "message": "전체 드론 홀딩",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "HOLD"

    def test_notam_message(self, client):
        """NOTAM 설정 명령."""
        resp = client.post("/api/chat/message", json={
            "message": "A구역 비행금지 설정, 30분",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "SET_NOTAM"
        assert data["requires_confirmation"] is True

    def test_session_id_preserved(self, client):
        """세션 ID 유지."""
        resp = client.post("/api/chat/message", json={
            "message": "브리핑",
            "session_id": "test-api-session",
        })
        assert resp.status_code == 200
        assert resp.json()["session_id"] == "test-api-session"

    def test_empty_message_rejected(self, client):
        """빈 메시지 거부."""
        resp = client.post("/api/chat/message", json={
            "message": "",
        })
        assert resp.status_code == 422  # Validation error


class TestBriefingEndpoint:
    """POST /api/chat/briefing 테스트."""

    def test_briefing_default(self, client):
        """기본 브리핑."""
        resp = client.post("/api/chat/briefing")
        assert resp.status_code == 200
        data = resp.json()
        assert "briefing" in data
        assert len(data["briefing"]) > 10

    def test_briefing_with_params(self, client):
        """파라미터 포함 브리핑."""
        resp = client.post("/api/chat/briefing?active_drones=8&holding_drones=3")
        assert resp.status_code == 200
        data = resp.json()
        assert "총 11대" in data["briefing"]


class TestHistoryEndpoint:
    """GET /api/chat/history 테스트."""

    def test_history_empty(self, client):
        """빈 이력."""
        resp = client.get("/api/chat/history/empty-session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "empty-session"
        assert data["messages"] == []

    def test_history_after_message(self, client):
        """메시지 후 이력."""
        # 먼저 메시지 전송
        client.post("/api/chat/message", json={
            "message": "브리핑",
            "session_id": "hist-api-1",
        })
        # 이력 조회
        resp = client.get("/api/chat/history/hist-api-1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][1]["role"] == "assistant"
