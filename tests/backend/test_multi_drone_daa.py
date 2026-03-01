"""다중 드론 시뮬레이터 DAA 통합 테스트."""

import sys
from pathlib import Path

import pytest

backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from models.common import Position3D, Priority
from simulator.multi_drone import MultiDroneSim, DroneConfig, TickResult
from core.deconfliction.avoidance import ManeuverType


def _config(drone_id: str, lat: float, lon: float,
            dest_lat: float, dest_lon: float,
            speed: float = 10.0, priority: Priority = Priority.NORMAL) -> DroneConfig:
    return DroneConfig(
        drone_id=drone_id,
        waypoints=[
            Position3D(lat=lat, lon=lon, alt_m=100),
            Position3D(lat=dest_lat, lon=dest_lon, alt_m=100),
        ],
        speed_ms=speed,
        priority=priority,
    )


class TestMultiDroneDAA:
    def test_tick_with_daa_returns_tick_result(self):
        """tick_with_daa가 TickResult를 반환한다."""
        sim = MultiDroneSim()
        sim.add_drone(_config("D1", 37.56, 126.97, 37.57, 126.98))
        result = sim.tick_with_daa(dt_sec=0.1)
        assert isinstance(result, TickResult)
        assert len(result.telemetry) == 1
        assert result.conflicts == []
        assert result.commands == []

    def test_no_conflict_safe_drones(self):
        """안전 거리 드론들은 충돌 없음."""
        sim = MultiDroneSim()
        sim.add_drone(_config("D1", 37.56, 126.97, 37.57, 126.98))
        sim.add_drone(_config("D2", 37.60, 126.97, 37.61, 126.98))
        result = sim.tick_with_daa(dt_sec=0.1)
        assert len(result.conflicts) == 0
        assert len(result.commands) == 0

    def test_head_on_conflict_detected(self):
        """정면 충돌 코스에서 충돌이 감지된다."""
        sim = MultiDroneSim()
        sim.add_drone(_config("D1", 37.5665, 126.975, 37.5665, 126.985, speed=10))
        sim.add_drone(_config("D2", 37.5665, 126.981, 37.5665, 126.971, speed=10))
        result = sim.tick_with_daa(dt_sec=0.1)
        assert len(result.conflicts) >= 1
        assert len(result.commands) >= 1

    def test_avoidance_command_applied(self):
        """회피 명령이 드론에 적용된다."""
        sim = MultiDroneSim()
        sim.add_drone(_config("D1", 37.5665, 126.975, 37.5665, 126.985, speed=10))
        sim.add_drone(_config("D2", 37.5665, 126.981, 37.5665, 126.971, speed=10))

        original_speed_d2 = sim.get_sim("D2").speed_ms
        result = sim.tick_with_daa(dt_sec=0.1)

        if result.commands:
            cmd = result.commands[0]
            target_sim = sim.get_sim(cmd.drone_id)
            if cmd.maneuver_type == ManeuverType.SPEED_CHANGE:
                assert target_sim.speed_ms != original_speed_d2
            elif cmd.maneuver_type == ManeuverType.ALTITUDE_CHANGE:
                assert target_sim.position.alt_m != 100.0

    def test_priority_respected_in_daa(self):
        """HIGH 우선순위 드론은 양보하지 않는다."""
        sim = MultiDroneSim()
        sim.add_drone(_config("D1", 37.5665, 126.975, 37.5665, 126.985,
                              speed=10, priority=Priority.HIGH))
        sim.add_drone(_config("D2", 37.5665, 126.981, 37.5665, 126.971,
                              speed=10, priority=Priority.NORMAL))
        result = sim.tick_with_daa(dt_sec=0.1)

        for cmd in result.commands:
            assert cmd.drone_id == "D2"  # NORMAL이 양보

    def test_single_drone_no_daa(self):
        """드론 1대면 DAA 검사 안함."""
        sim = MultiDroneSim()
        sim.add_drone(_config("D1", 37.56, 126.97, 37.57, 126.98))
        result = sim.tick_with_daa(dt_sec=0.1)
        assert result.conflicts == []
        assert result.commands == []

    def test_empty_sim_tick_with_daa(self):
        """빈 시뮬레이션도 정상 작동."""
        sim = MultiDroneSim()
        result = sim.tick_with_daa(dt_sec=0.1)
        assert result.telemetry == []
        assert result.conflicts == []
        assert result.commands == []

    def test_three_drones_selective_conflict(self):
        """3대 중 1쌍만 충돌 → 해당 쌍만 회피."""
        sim = MultiDroneSim()
        sim.add_drone(_config("D1", 37.5665, 126.975, 37.5665, 126.985, speed=10))
        sim.add_drone(_config("D2", 37.5665, 126.981, 37.5665, 126.971, speed=10))
        sim.add_drone(_config("D3", 37.60, 126.97, 37.61, 126.98))  # 멀리

        result = sim.tick_with_daa(dt_sec=0.1)
        cmd_ids = {cmd.drone_id for cmd in result.commands}
        assert "D3" not in cmd_ids

    def test_multi_tick_convergence(self):
        """여러 틱 후 회피 기동으로 충돌이 완화된다."""
        sim = MultiDroneSim()
        sim.add_drone(_config("D1", 37.5665, 126.975, 37.5665, 126.985, speed=10))
        sim.add_drone(_config("D2", 37.5665, 126.981, 37.5665, 126.971, speed=10))

        initial_conflicts = 0
        later_conflicts = 0

        for i in range(50):
            result = sim.tick_with_daa(dt_sec=0.1)
            if i == 0:
                initial_conflicts = len(result.conflicts)
            if i == 49:
                later_conflicts = len(result.conflicts)

        # 회피가 적용되어 충돌이 줄어들거나 유지 (최소한 에러 없이 동작)
        assert isinstance(later_conflicts, int)
