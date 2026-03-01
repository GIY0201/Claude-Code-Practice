"""시나리오 매니저 + REST API 테스트."""

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from simulator.scenario import ScenarioManager, ScenarioInfo, SCENARIOS_DIR
from simulator.multi_drone import DroneConfig
from models.common import Priority


# ── 헬퍼 ──────────────────────────────────────────────────────────────

def _make_scenario_json(name: str, drones: list[dict]) -> dict:
    return {
        "name": name,
        "description": f"Test scenario: {name}",
        "drones": drones,
    }


SAMPLE_DRONE = {
    "drone_id": "T-001",
    "waypoints": [
        {"lat": 37.5, "lon": 126.9, "alt_m": 100},
        {"lat": 37.6, "lon": 127.0, "alt_m": 120},
    ],
    "speed_ms": 10,
    "priority": "NORMAL",
}

SAMPLE_DRONE_FULL = {
    "drone_id": "T-002",
    "waypoints": [
        {"lat": 37.55, "lon": 126.95, "alt_m": 80},
        {"lat": 37.60, "lon": 127.00, "alt_m": 80},
    ],
    "speed_ms": 15,
    "battery_percent": 50.0,
    "priority": "HIGH",
}


# ── ScenarioManager 유닛 테스트 ───────────────────────────────────────

class TestScenarioManager:
    """ScenarioManager 단위 테스트."""

    def _create_temp_dir(self, scenarios: dict[str, dict]) -> Path:
        """임시 디렉토리에 시나리오 JSON 파일 생성."""
        tmp = Path(tempfile.mkdtemp())
        for filename, data in scenarios.items():
            (tmp / f"{filename}.json").write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
        return tmp

    def test_list_scenarios_empty(self):
        """빈 디렉토리에서 빈 목록 반환."""
        tmp = Path(tempfile.mkdtemp())
        mgr = ScenarioManager(tmp)
        assert mgr.list_scenarios() == []

    def test_list_scenarios_nonexistent_dir(self):
        """존재하지 않는 디렉토리에서 빈 목록 반환."""
        mgr = ScenarioManager(Path("/nonexistent/path"))
        assert mgr.list_scenarios() == []

    def test_list_scenarios(self):
        """시나리오 목록 반환."""
        tmp = self._create_temp_dir({
            "s1": _make_scenario_json("alpha", [SAMPLE_DRONE]),
            "s2": _make_scenario_json("beta", [SAMPLE_DRONE, SAMPLE_DRONE_FULL]),
        })
        mgr = ScenarioManager(tmp)
        result = mgr.list_scenarios()
        assert len(result) == 2
        names = {s.name for s in result}
        assert names == {"alpha", "beta"}
        # drone_count 확인
        for s in result:
            if s.name == "alpha":
                assert s.drone_count == 1
            elif s.name == "beta":
                assert s.drone_count == 2

    def test_load_scenario_by_name(self):
        """JSON name 필드로 시나리오 로드."""
        tmp = self._create_temp_dir({
            "test": _make_scenario_json("test_scenario", [SAMPLE_DRONE]),
        })
        mgr = ScenarioManager(tmp)
        configs = mgr.load_scenario("test_scenario")
        assert len(configs) == 1
        assert isinstance(configs[0], DroneConfig)
        assert configs[0].drone_id == "T-001"
        assert configs[0].speed_ms == 10
        assert configs[0].priority == Priority.NORMAL
        assert len(configs[0].waypoints) == 2

    def test_load_scenario_by_filename(self):
        """파일명(stem)으로 시나리오 로드."""
        tmp = self._create_temp_dir({
            "my_file": _make_scenario_json("different_name", [SAMPLE_DRONE]),
        })
        mgr = ScenarioManager(tmp)
        configs = mgr.load_scenario("my_file")
        assert len(configs) == 1

    def test_load_scenario_with_battery(self):
        """battery_percent가 포함된 드론 로드."""
        tmp = self._create_temp_dir({
            "bat": _make_scenario_json("bat_test", [SAMPLE_DRONE_FULL]),
        })
        mgr = ScenarioManager(tmp)
        configs = mgr.load_scenario("bat_test")
        assert configs[0].battery_percent == 50.0
        assert configs[0].priority == Priority.HIGH

    def test_load_scenario_not_found(self):
        """존재하지 않는 시나리오 로드 시 FileNotFoundError."""
        tmp = self._create_temp_dir({})
        mgr = ScenarioManager(tmp)
        with pytest.raises(FileNotFoundError, match="Scenario not found"):
            mgr.load_scenario("nonexistent")

    def test_load_scenario_nonexistent_dir(self):
        """존재하지 않는 디렉토리에서 FileNotFoundError."""
        mgr = ScenarioManager(Path("/nonexistent"))
        with pytest.raises(FileNotFoundError, match="Scenarios directory not found"):
            mgr.load_scenario("any")

    def test_get_scenario_info(self):
        """시나리오 상세 정보 반환."""
        tmp = self._create_temp_dir({
            "info": _make_scenario_json("info_test", [SAMPLE_DRONE, SAMPLE_DRONE_FULL]),
        })
        mgr = ScenarioManager(tmp)
        info = mgr.get_scenario_info("info_test")
        assert isinstance(info, ScenarioInfo)
        assert info.name == "info_test"
        assert info.drone_count == 2
        assert "Test scenario" in info.description

    def test_get_scenario_raw(self):
        """원본 JSON 반환."""
        data = _make_scenario_json("raw_test", [SAMPLE_DRONE])
        tmp = self._create_temp_dir({"raw": data})
        mgr = ScenarioManager(tmp)
        raw = mgr.get_scenario_raw("raw_test")
        assert raw["name"] == "raw_test"
        assert len(raw["drones"]) == 1

    def test_invalid_json_skipped(self):
        """잘못된 JSON 파일은 건너뛴다."""
        tmp = Path(tempfile.mkdtemp())
        (tmp / "valid.json").write_text(
            json.dumps(_make_scenario_json("valid", [SAMPLE_DRONE])),
            encoding="utf-8",
        )
        (tmp / "invalid.json").write_text("not valid json", encoding="utf-8")
        mgr = ScenarioManager(tmp)
        result = mgr.list_scenarios()
        assert len(result) == 1
        assert result[0].name == "valid"

    def test_default_speed_and_battery(self):
        """speed_ms, battery_percent 미지정 시 기본값."""
        drone_minimal = {
            "drone_id": "MIN-001",
            "waypoints": [
                {"lat": 37.5, "lon": 126.9, "alt_m": 100},
                {"lat": 37.6, "lon": 127.0, "alt_m": 100},
            ],
        }
        tmp = self._create_temp_dir({
            "min": _make_scenario_json("minimal", [drone_minimal]),
        })
        mgr = ScenarioManager(tmp)
        configs = mgr.load_scenario("minimal")
        assert configs[0].speed_ms == 10.0
        assert configs[0].battery_percent == 100.0
        assert configs[0].priority == Priority.NORMAL


# ── 실제 시나리오 파일 로드 테스트 ────────────────────────────────────

class TestBuiltInScenarios:
    """기본 제공 시나리오 파일 검증."""

    def test_delivery_scenario_loads(self):
        """delivery.json 로드 성공."""
        mgr = ScenarioManager()
        configs = mgr.load_scenario("multi_delivery")
        assert len(configs) == 5
        ids = {c.drone_id for c in configs}
        assert "DEL-001" in ids
        assert "EMG-001" in ids

    def test_surveillance_scenario_loads(self):
        """surveillance.json 로드 성공."""
        mgr = ScenarioManager()
        configs = mgr.load_scenario("surveillance_patrol")
        assert len(configs) == 3
        for c in configs:
            assert c.drone_id.startswith("SUR-")
            assert len(c.waypoints) >= 6

    def test_emergency_scenario_loads(self):
        """emergency.json 로드 성공."""
        mgr = ScenarioManager()
        configs = mgr.load_scenario("emergency_complex")
        assert len(configs) == 4
        # 배터리 부족 드론 확인
        low_bat = [c for c in configs if c.battery_percent < 100]
        assert len(low_bat) == 1
        assert low_bat[0].battery_percent == 20
        # EMERGENCY 우선순위 드론 확인
        emg = [c for c in configs if c.priority == Priority.EMERGENCY]
        assert len(emg) == 1

    def test_list_all_built_in(self):
        """기본 시나리오 3개 모두 나열."""
        mgr = ScenarioManager()
        result = mgr.list_scenarios()
        names = {s.name for s in result}
        assert "multi_delivery" in names
        assert "surveillance_patrol" in names
        assert "emergency_complex" in names


# ── REST API 테스트 ───────────────────────────────────────────────────

class TestScenarioAPI:
    """시나리오 REST API 테스트."""

    @pytest.fixture(autouse=True)
    def client(self):
        from main import app
        self._client = TestClient(app)

    def test_list_scenarios(self):
        resp = self._client.get("/api/scenarios/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 3
        names = {s["name"] for s in data}
        assert "multi_delivery" in names

    def test_get_scenario(self):
        resp = self._client.get("/api/scenarios/multi_delivery")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "multi_delivery"
        assert len(data["drones"]) == 5

    def test_get_scenario_not_found(self):
        resp = self._client.get("/api/scenarios/nonexistent_scenario")
        assert resp.status_code == 404
