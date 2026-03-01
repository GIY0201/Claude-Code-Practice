"""WebSocket 텔레메트리 스트리밍 테스트."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from main import app

client = TestClient(app)

# 서울(37.5665, 126.978) → 50m 북쪽 지점 (빠르게 도착 가능한 짧은 경로)
SHORT_WAYPOINTS = [
    {"lat": 37.5665, "lon": 126.978, "alt_m": 100},
    {"lat": 37.5670, "lon": 126.978, "alt_m": 100},
]


class TestWebSocketTelemetry:
    def test_connect_and_receive_status(self):
        """WebSocket 연결이 성공한다."""
        with client.websocket_connect("/ws/telemetry") as ws:
            ws.send_json({"action": "unknown_action"})
            resp = ws.receive_json()
            assert resp["event"] == "error"

    def test_invalid_json(self):
        """잘못된 JSON 전송 시 에러 응답."""
        with client.websocket_connect("/ws/telemetry") as ws:
            ws.send_text("not json")
            resp = ws.receive_json()
            assert resp["event"] == "error"
            assert "Invalid JSON" in resp["message"]

    def test_start_missing_waypoints(self):
        """waypoints 없이 start 시 에러."""
        with client.websocket_connect("/ws/telemetry") as ws:
            ws.send_json({"action": "start", "drone_id": "D1"})
            resp = ws.receive_json()
            assert resp["event"] == "error"

    def test_start_too_few_waypoints(self):
        """waypoints가 1개면 에러."""
        with client.websocket_connect("/ws/telemetry") as ws:
            ws.send_json({
                "action": "start",
                "drone_id": "D1",
                "waypoints": [{"lat": 37.5665, "lon": 126.978}],
            })
            resp = ws.receive_json()
            assert resp["event"] == "error"

    def test_start_simulation_streams_telemetry(self):
        """시뮬레이션 시작 시 텔레메트리 이벤트를 수신한다."""
        with client.websocket_connect("/ws/telemetry") as ws:
            ws.send_json({
                "action": "start",
                "drone_id": "D1",
                "waypoints": SHORT_WAYPOINTS,
                "speed_ms": 50.0,
            })
            # 첫 번째 텔레메트리 수신
            resp = ws.receive_json()
            assert resp["event"] == "telemetry"
            data = resp["data"]
            assert data["drone_id"] == "D1"
            assert "position" in data
            assert "velocity" in data
            assert "heading" in data
            assert "battery_percent" in data

    def test_simulation_completes(self):
        """짧은 경로에서 시뮬레이션이 완료되면 completed 이벤트를 받는다."""
        with client.websocket_connect("/ws/telemetry") as ws:
            ws.send_json({
                "action": "start",
                "drone_id": "D1",
                "waypoints": SHORT_WAYPOINTS,
                "speed_ms": 500.0,  # 빠른 속도로 빨리 도착
            })

            events = []
            for _ in range(200):  # 최대 200개 메시지
                resp = ws.receive_json()
                events.append(resp["event"])
                if resp["event"] == "completed":
                    break

            assert "telemetry" in events
            assert events[-1] == "completed"

    def test_stop_simulation(self):
        """stop 명령으로 시뮬레이션을 중지할 수 있다."""
        with client.websocket_connect("/ws/telemetry") as ws:
            # 긴 경로로 시작 (서울→강남, 약 8.7km)
            ws.send_json({
                "action": "start",
                "drone_id": "D1",
                "waypoints": [
                    {"lat": 37.5665, "lon": 126.978, "alt_m": 100},
                    {"lat": 37.4979, "lon": 127.0276, "alt_m": 100},
                ],
                "speed_ms": 10.0,
            })
            # 텔레메트리 1개 수신
            resp = ws.receive_json()
            assert resp["event"] == "telemetry"

            # 중지
            ws.send_json({"action": "stop"})
            resp = ws.receive_json()
            # stop 응답 전에 추가 텔레메트리가 올 수 있으므로 stopped까지 소비
            while resp["event"] == "telemetry":
                resp = ws.receive_json()
            assert resp["event"] == "stopped"

    def test_telemetry_position_changes(self):
        """텔레메트리 위치가 틱마다 변한다."""
        with client.websocket_connect("/ws/telemetry") as ws:
            ws.send_json({
                "action": "start",
                "drone_id": "D1",
                "waypoints": [
                    {"lat": 37.5665, "lon": 126.978, "alt_m": 100},
                    {"lat": 37.4979, "lon": 127.0276, "alt_m": 100},
                ],
                "speed_ms": 50.0,
            })
            t1 = ws.receive_json()["data"]
            t2 = ws.receive_json()["data"]
            # 위치가 변해야 함
            assert (
                t1["position"]["lat"] != t2["position"]["lat"]
                or t1["position"]["lon"] != t2["position"]["lon"]
            )
