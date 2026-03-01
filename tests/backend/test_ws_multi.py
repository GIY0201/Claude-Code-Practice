"""다중 드론 WebSocket 텔레메트리 테스트."""

import sys
from pathlib import Path

import pytest

backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from main import app


class TestMultiTelemetryWebSocket:
    def test_connect(self):
        """WebSocket 연결 성공."""
        client = TestClient(app)
        with client.websocket_connect("/ws/multi-telemetry") as ws:
            ws.send_json({"action": "stop"})
            data = ws.receive_json()
            assert data["event"] == "stopped"

    def test_invalid_json(self):
        """잘못된 JSON → 에러."""
        client = TestClient(app)
        with client.websocket_connect("/ws/multi-telemetry") as ws:
            ws.send_text("not-json")
            data = ws.receive_json()
            assert data["event"] == "error"

    def test_unknown_action(self):
        """알 수 없는 액션 → 에러."""
        client = TestClient(app)
        with client.websocket_connect("/ws/multi-telemetry") as ws:
            ws.send_json({"action": "unknown"})
            data = ws.receive_json()
            assert data["event"] == "error"

    def test_start_no_drones_error(self):
        """드론 없이 start → 에러."""
        client = TestClient(app)
        with client.websocket_connect("/ws/multi-telemetry") as ws:
            ws.send_json({"action": "start"})
            data = ws.receive_json()
            assert data["event"] == "error"

    def test_start_insufficient_waypoints(self):
        """경유점 부족 → 에러."""
        client = TestClient(app)
        with client.websocket_connect("/ws/multi-telemetry") as ws:
            ws.send_json({
                "action": "start",
                "drones": [
                    {"drone_id": "D1", "waypoints": [{"lat": 37.56, "lon": 126.97}]}
                ]
            })
            data = ws.receive_json()
            assert data["event"] == "error"

    def test_start_multi_drone_telemetry(self):
        """다중 드론 시뮬레이션 텔레메트리 수신."""
        client = TestClient(app)
        with client.websocket_connect("/ws/multi-telemetry") as ws:
            ws.send_json({
                "action": "start",
                "drones": [
                    {
                        "drone_id": "D1",
                        "waypoints": [
                            {"lat": 37.5665, "lon": 126.978, "alt_m": 100},
                            {"lat": 37.5666, "lon": 126.978, "alt_m": 100},
                        ],
                        "speed_ms": 100.0,
                    },
                    {
                        "drone_id": "D2",
                        "waypoints": [
                            {"lat": 37.56, "lon": 126.97, "alt_m": 100},
                            {"lat": 37.561, "lon": 126.97, "alt_m": 100},
                        ],
                        "speed_ms": 100.0,
                    },
                ]
            })
            data = ws.receive_json()
            assert data["event"] == "telemetry"
            assert "drones" in data
            assert len(data["drones"]) == 2
            assert "active_count" in data

    def test_multi_drone_completion(self):
        """모든 드론 완료 시 completed 이벤트."""
        client = TestClient(app)
        with client.websocket_connect("/ws/multi-telemetry") as ws:
            ws.send_json({
                "action": "start",
                "drones": [
                    {
                        "drone_id": "D1",
                        "waypoints": [
                            {"lat": 37.5665, "lon": 126.978, "alt_m": 100},
                            {"lat": 37.5666, "lon": 126.978, "alt_m": 100},
                        ],
                        "speed_ms": 500.0,
                    },
                ]
            })

            events = []
            for _ in range(100):
                data = ws.receive_json()
                events.append(data["event"])
                if data["event"] == "completed":
                    break

            assert "completed" in events

    def test_stop_multi_simulation(self):
        """stop 명령으로 다중 시뮬레이션 중지."""
        client = TestClient(app)
        with client.websocket_connect("/ws/multi-telemetry") as ws:
            ws.send_json({
                "action": "start",
                "drones": [
                    {
                        "drone_id": "D1",
                        "waypoints": [
                            {"lat": 37.56, "lon": 126.97, "alt_m": 100},
                            {"lat": 37.60, "lon": 126.97, "alt_m": 100},
                        ],
                        "speed_ms": 10.0,
                    },
                ]
            })
            # 첫 텔레메트리 수신 후 stop
            ws.receive_json()
            ws.send_json({"action": "stop"})
            data = ws.receive_json()
            assert data["event"] == "stopped"

    def test_conflict_event_on_collision_course(self):
        """정면 충돌 코스에서 conflict 이벤트 발생."""
        client = TestClient(app)
        with client.websocket_connect("/ws/multi-telemetry") as ws:
            ws.send_json({
                "action": "start",
                "drones": [
                    {
                        "drone_id": "D1",
                        "waypoints": [
                            {"lat": 37.5665, "lon": 126.975, "alt_m": 100},
                            {"lat": 37.5665, "lon": 126.985, "alt_m": 100},
                        ],
                        "speed_ms": 10.0,
                    },
                    {
                        "drone_id": "D2",
                        "waypoints": [
                            {"lat": 37.5665, "lon": 126.981, "alt_m": 100},
                            {"lat": 37.5665, "lon": 126.971, "alt_m": 100},
                        ],
                        "speed_ms": 10.0,
                    },
                ]
            })

            events = set()
            for _ in range(20):
                data = ws.receive_json()
                events.add(data["event"])
                if "conflict" in events:
                    break

            assert "conflict" in events

    def test_priority_in_multi_drone(self):
        """priority 파라미터가 정상 파싱된다."""
        client = TestClient(app)
        with client.websocket_connect("/ws/multi-telemetry") as ws:
            ws.send_json({
                "action": "start",
                "drones": [
                    {
                        "drone_id": "D1",
                        "waypoints": [
                            {"lat": 37.5665, "lon": 126.978, "alt_m": 100},
                            {"lat": 37.5666, "lon": 126.978, "alt_m": 100},
                        ],
                        "speed_ms": 100.0,
                        "priority": "HIGH",
                    },
                ]
            })
            data = ws.receive_json()
            assert data["event"] == "telemetry"
