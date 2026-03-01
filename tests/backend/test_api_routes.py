"""REST API 라우트 통합 테스트."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# ──────────────── Health Check ────────────────

def test_health_check():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ──────────────── Drone API ────────────────

class TestDroneAPI:
    def _create_drone(self, callsign="SKY-001"):
        return client.post("/api/drones/", json={"callsign": callsign})

    def test_create_drone(self):
        resp = self._create_drone()
        assert resp.status_code == 201
        data = resp.json()
        assert data["callsign"] == "SKY-001"
        assert data["status"] == "IDLE"
        assert "drone_id" in data

    def test_list_drones_empty(self):
        resp = client.get("/api/drones/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_drones_after_create(self):
        self._create_drone("SKY-001")
        self._create_drone("SKY-002")
        resp = client.get("/api/drones/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_drone(self):
        create_resp = self._create_drone()
        drone_id = create_resp.json()["drone_id"]
        resp = client.get(f"/api/drones/{drone_id}")
        assert resp.status_code == 200
        assert resp.json()["drone_id"] == drone_id

    def test_get_drone_not_found(self):
        resp = client.get("/api/drones/nonexist")
        assert resp.status_code == 404

    def test_update_drone(self):
        drone_id = self._create_drone().json()["drone_id"]
        resp = client.put(f"/api/drones/{drone_id}", json={
            "status": "AIRBORNE",
            "battery_percent": 85.0,
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "AIRBORNE"
        assert resp.json()["battery_percent"] == 85.0

    def test_update_drone_not_found(self):
        resp = client.put("/api/drones/nonexist", json={"status": "IDLE"})
        assert resp.status_code == 404

    def test_delete_drone(self):
        drone_id = self._create_drone().json()["drone_id"]
        resp = client.delete(f"/api/drones/{drone_id}")
        assert resp.status_code == 204
        # 삭제 후 조회 → 404
        assert client.get(f"/api/drones/{drone_id}").status_code == 404

    def test_delete_drone_not_found(self):
        resp = client.delete("/api/drones/nonexist")
        assert resp.status_code == 404

    def test_filter_by_status(self):
        self._create_drone("SKY-001")
        d2 = self._create_drone("SKY-002")
        client.put(f"/api/drones/{d2.json()['drone_id']}", json={"status": "AIRBORNE"})
        resp = client.get("/api/drones/", params={"status": "AIRBORNE"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["status"] == "AIRBORNE"


# ──────────────── FlightPlan API ────────────────

class TestFlightPlanAPI:
    _counter = 0

    def _create_drone(self):
        TestFlightPlanAPI._counter += 1
        resp = client.post("/api/drones/", json={"callsign": f"FP-{TestFlightPlanAPI._counter}"})
        return resp.json()["drone_id"]

    def _plan_payload(self, drone_id):
        return {
            "drone_id": drone_id,
            "departure_position": {"lat": 37.5665, "lon": 126.978, "alt_m": 0},
            "destination_position": {"lat": 37.4979, "lon": 127.0276, "alt_m": 0},
            "departure_time": "2026-03-01T10:00:00",
            "cruise_altitude_m": 100.0,
            "cruise_speed_ms": 10.0,
        }

    def test_create_flight_plan(self):
        drone_id = self._create_drone()
        resp = client.post("/api/flight-plans/", json=self._plan_payload(drone_id))
        assert resp.status_code == 201
        data = resp.json()
        assert data["drone_id"] == drone_id
        assert data["status"] == "DRAFT"
        assert "plan_id" in data

    def test_list_flight_plans_empty(self):
        resp = client.get("/api/flight-plans/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_flight_plan(self):
        drone_id = self._create_drone()
        plan_id = client.post("/api/flight-plans/", json=self._plan_payload(drone_id)).json()["plan_id"]
        resp = client.get(f"/api/flight-plans/{plan_id}")
        assert resp.status_code == 200
        assert resp.json()["plan_id"] == plan_id

    def test_get_flight_plan_not_found(self):
        resp = client.get("/api/flight-plans/nonexist")
        assert resp.status_code == 404

    def test_update_status(self):
        drone_id = self._create_drone()
        plan_id = client.post("/api/flight-plans/", json=self._plan_payload(drone_id)).json()["plan_id"]
        resp = client.patch(f"/api/flight-plans/{plan_id}/status", json={"status": "SUBMITTED"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "SUBMITTED"

    def test_update_status_not_found(self):
        resp = client.patch("/api/flight-plans/nonexist/status", json={"status": "SUBMITTED"})
        assert resp.status_code == 404

    def test_add_waypoints(self):
        drone_id = self._create_drone()
        plan_id = client.post("/api/flight-plans/", json=self._plan_payload(drone_id)).json()["plan_id"]
        waypoints = [
            {"position": {"lat": 37.53, "lon": 126.99, "alt_m": 100}, "name": "WP-1"},
            {"position": {"lat": 37.51, "lon": 127.01, "alt_m": 100}, "name": "WP-2"},
        ]
        resp = client.post(f"/api/flight-plans/{plan_id}/waypoints", json=waypoints)
        assert resp.status_code == 200
        assert len(resp.json()["waypoints"]) == 2

    def test_delete_flight_plan(self):
        drone_id = self._create_drone()
        plan_id = client.post("/api/flight-plans/", json=self._plan_payload(drone_id)).json()["plan_id"]
        resp = client.delete(f"/api/flight-plans/{plan_id}")
        assert resp.status_code == 204
        assert client.get(f"/api/flight-plans/{plan_id}").status_code == 404

    def test_filter_by_drone_id(self):
        d1 = self._create_drone()
        d2 = self._create_drone()
        client.post("/api/flight-plans/", json=self._plan_payload(d1))
        client.post("/api/flight-plans/", json=self._plan_payload(d2))
        resp = client.get("/api/flight-plans/", params={"drone_id": d1})
        assert len(resp.json()) == 1


# ──────────────── Airspace API ────────────────

class TestAirspaceAPI:
    SAMPLE_ZONE = {
        "name": "Test Restricted",
        "zone_type": "RESTRICTED",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[126.9, 37.5], [127.0, 37.5], [127.0, 37.6], [126.9, 37.6], [126.9, 37.5]]],
        },
        "floor_altitude_m": 0,
        "ceiling_altitude_m": 120,
    }

    def test_create_airspace(self):
        resp = client.post("/api/airspaces/", json=self.SAMPLE_ZONE)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Restricted"
        assert data["zone_type"] == "RESTRICTED"

    def test_list_airspaces_empty(self):
        resp = client.get("/api/airspaces/")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_airspace(self):
        zone_id = client.post("/api/airspaces/", json=self.SAMPLE_ZONE).json()["zone_id"]
        resp = client.get(f"/api/airspaces/{zone_id}")
        assert resp.status_code == 200
        assert resp.json()["zone_id"] == zone_id

    def test_get_airspace_not_found(self):
        resp = client.get("/api/airspaces/nonexist")
        assert resp.status_code == 404

    def test_deactivate_airspace(self):
        zone_id = client.post("/api/airspaces/", json=self.SAMPLE_ZONE).json()["zone_id"]
        resp = client.patch(f"/api/airspaces/{zone_id}/active", json={"active": False})
        assert resp.status_code == 200
        assert resp.json()["active"] is False

    def test_deactivated_filtered_out(self):
        zone_id = client.post("/api/airspaces/", json=self.SAMPLE_ZONE).json()["zone_id"]
        client.patch(f"/api/airspaces/{zone_id}/active", json={"active": False})
        # active_only=True (기본값) → 비활성 구역 제외
        assert len(client.get("/api/airspaces/").json()) == 0
        # active_only=False → 전체 포함
        assert len(client.get("/api/airspaces/", params={"active_only": False}).json()) == 1

    def test_delete_airspace(self):
        zone_id = client.post("/api/airspaces/", json=self.SAMPLE_ZONE).json()["zone_id"]
        resp = client.delete(f"/api/airspaces/{zone_id}")
        assert resp.status_code == 204
        assert client.get(f"/api/airspaces/{zone_id}").status_code == 404

    def test_delete_airspace_not_found(self):
        resp = client.delete("/api/airspaces/nonexist")
        assert resp.status_code == 404
