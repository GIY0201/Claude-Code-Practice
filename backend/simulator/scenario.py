"""시나리오 매니저.

scenarios/ 디렉토리의 JSON 파일을 로드하여 DroneConfig 리스트로 변환한다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from models.common import Position3D, Priority
from simulator.multi_drone import DroneConfig

# 시나리오 JSON 디렉토리
SCENARIOS_DIR = Path(__file__).parent / "scenarios"


@dataclass
class ScenarioInfo:
    """시나리오 메타 정보."""
    name: str
    description: str
    drone_count: int


class ScenarioManager:
    """시나리오 JSON 파일을 로드하고 관리한다."""

    def __init__(self, scenarios_dir: Path | None = None):
        self._dir = scenarios_dir or SCENARIOS_DIR

    def list_scenarios(self) -> list[ScenarioInfo]:
        """사용 가능한 시나리오 목록을 반환한다."""
        result: list[ScenarioInfo] = []
        if not self._dir.exists():
            return result
        for path in sorted(self._dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                result.append(ScenarioInfo(
                    name=data.get("name", path.stem),
                    description=data.get("description", ""),
                    drone_count=len(data.get("drones", [])),
                ))
            except (json.JSONDecodeError, KeyError):
                continue
        return result

    def load_scenario(self, name: str) -> list[DroneConfig]:
        """시나리오 이름으로 DroneConfig 리스트를 반환한다."""
        data = self._load_json(name)
        configs: list[DroneConfig] = []
        for d in data["drones"]:
            waypoints = [
                Position3D(lat=w["lat"], lon=w["lon"], alt_m=w["alt_m"])
                for w in d["waypoints"]
            ]
            configs.append(DroneConfig(
                drone_id=d["drone_id"],
                waypoints=waypoints,
                speed_ms=d.get("speed_ms", 10.0),
                battery_percent=d.get("battery_percent", 100.0),
                priority=Priority(d.get("priority", "NORMAL")),
            ))
        return configs

    def get_scenario_info(self, name: str) -> ScenarioInfo:
        """시나리오 상세 정보를 반환한다."""
        data = self._load_json(name)
        return ScenarioInfo(
            name=data.get("name", name),
            description=data.get("description", ""),
            drone_count=len(data.get("drones", [])),
        )

    def get_scenario_raw(self, name: str) -> dict:
        """시나리오 원본 JSON을 반환한다."""
        return self._load_json(name)

    def _load_json(self, name: str) -> dict:
        """이름으로 JSON 파일을 찾아 로드한다."""
        # 이름으로 직접 매칭 (파일명 또는 JSON name 필드)
        if not self._dir.exists():
            raise FileNotFoundError(f"Scenarios directory not found: {self._dir}")

        # 1) 파일명 매칭
        for path in self._dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if data.get("name") == name or path.stem == name:
                    return data
            except (json.JSONDecodeError, KeyError):
                continue

        raise FileNotFoundError(f"Scenario not found: {name}")
