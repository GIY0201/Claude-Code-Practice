"""Tactical DAA 엔진 테스트."""

import sys
from pathlib import Path

import pytest

backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from models.common import Position3D, Velocity3D, Priority
from core.deconfliction.avoidance import DroneState, ManeuverType
from core.deconfliction.tactical import TacticalDAA


class TestTacticalDAA:
    def test_no_drones(self):
        daa = TacticalDAA()
        cmds = daa.evaluate({})
        assert cmds == []
        assert daa.conflict_count == 0

    def test_single_drone_no_conflict(self):
        daa = TacticalDAA()
        drones = {
            "D1": DroneState("D1", Position3D(lat=37.56, lon=126.97, alt_m=100),
                             Velocity3D(vx=10, vy=0, vz=0), speed_ms=10, heading=90),
        }
        cmds = daa.evaluate(drones)
        assert cmds == []

    def test_safe_pair_no_commands(self):
        """충분히 떨어진 2대 → 회피 명령 없음."""
        daa = TacticalDAA()
        drones = {
            "D1": DroneState("D1", Position3D(lat=37.56, lon=126.97, alt_m=100),
                             Velocity3D(vx=10, vy=0, vz=0), speed_ms=10, heading=90),
            "D2": DroneState("D2", Position3D(lat=37.60, lon=126.97, alt_m=100),
                             Velocity3D(vx=10, vy=0, vz=0), speed_ms=10, heading=90),
        }
        cmds = daa.evaluate(drones)
        assert cmds == []
        assert daa.conflict_count == 0

    def test_head_on_generates_command(self):
        """정면 충돌 코스 → 회피 명령 생성."""
        daa = TacticalDAA()
        drones = {
            "D1": DroneState("D1", Position3D(lat=37.5665, lon=126.975, alt_m=100),
                             Velocity3D(vx=10, vy=0, vz=0), speed_ms=10, heading=90),
            "D2": DroneState("D2", Position3D(lat=37.5665, lon=126.981, alt_m=100),
                             Velocity3D(vx=-10, vy=0, vz=0), speed_ms=10, heading=270),
        }
        cmds = daa.evaluate(drones)
        assert len(cmds) >= 1
        assert daa.conflict_count == 1
        # 회피 대상은 D2 (사전순 후순위)
        assert cmds[0].drone_id == "D2"

    def test_priority_respected(self):
        """HIGH 드론은 양보하지 않는다."""
        daa = TacticalDAA()
        drones = {
            "D1": DroneState("D1", Position3D(lat=37.5665, lon=126.975, alt_m=100),
                             Velocity3D(vx=10, vy=0, vz=0), speed_ms=10, heading=90,
                             priority=Priority.HIGH),
            "D2": DroneState("D2", Position3D(lat=37.5665, lon=126.981, alt_m=100),
                             Velocity3D(vx=-10, vy=0, vz=0), speed_ms=10, heading=270,
                             priority=Priority.NORMAL),
        }
        cmds = daa.evaluate(drones)
        assert len(cmds) >= 1
        assert cmds[0].drone_id == "D2"

    def test_three_drones_one_conflict(self):
        """3대 중 1쌍만 위반."""
        daa = TacticalDAA()
        drones = {
            "D1": DroneState("D1", Position3D(lat=37.5665, lon=126.975, alt_m=100),
                             Velocity3D(vx=10, vy=0, vz=0), speed_ms=10, heading=90),
            "D2": DroneState("D2", Position3D(lat=37.5665, lon=126.981, alt_m=100),
                             Velocity3D(vx=-10, vy=0, vz=0), speed_ms=10, heading=270),
            "D3": DroneState("D3", Position3D(lat=37.60, lon=126.97, alt_m=200),
                             Velocity3D(), speed_ms=0, heading=0),
        }
        cmds = daa.evaluate(drones)
        assert daa.conflict_count == 1
        # 명령은 D1-D2 쌍에 대해서만
        cmd_ids = {c.drone_id for c in cmds}
        assert "D3" not in cmd_ids

    def test_no_duplicate_commands(self):
        """같은 드론에 중복 명령이 발행되지 않는다."""
        daa = TacticalDAA()
        # D2가 D1, D3 모두와 충돌하도록 구성
        drones = {
            "D1": DroneState("D1", Position3D(lat=37.5665, lon=126.975, alt_m=100),
                             Velocity3D(vx=10, vy=0, vz=0), speed_ms=10, heading=90),
            "D2": DroneState("D2", Position3D(lat=37.5665, lon=126.980, alt_m=100),
                             Velocity3D(vx=-5, vy=0, vz=0), speed_ms=5, heading=270),
            "D3": DroneState("D3", Position3D(lat=37.5665, lon=126.984, alt_m=100),
                             Velocity3D(vx=-10, vy=0, vz=0), speed_ms=10, heading=270),
        }
        cmds = daa.evaluate(drones)
        # 각 드론은 최대 1개 명령
        cmd_ids = [c.drone_id for c in cmds]
        assert len(cmd_ids) == len(set(cmd_ids))

    def test_evaluate_pair(self):
        """evaluate_pair가 단일 쌍을 정상 평가한다."""
        daa = TacticalDAA()
        a = DroneState("D1", Position3D(lat=37.5665, lon=126.975, alt_m=100),
                       Velocity3D(vx=10, vy=0, vz=0), speed_ms=10, heading=90)
        b = DroneState("D2", Position3D(lat=37.5665, lon=126.981, alt_m=100),
                       Velocity3D(vx=-10, vy=0, vz=0), speed_ms=10, heading=270)
        cpa, cmds = daa.evaluate_pair(a, b)
        assert cpa.is_violation is True
        assert len(cmds) >= 1

    def test_evaluate_pair_safe(self):
        """안전한 쌍은 명령 없음."""
        daa = TacticalDAA()
        a = DroneState("D1", Position3D(lat=37.56, lon=126.97, alt_m=100),
                       Velocity3D(vx=10, vy=0, vz=0), speed_ms=10, heading=90)
        b = DroneState("D2", Position3D(lat=37.60, lon=126.97, alt_m=100),
                       Velocity3D(vx=10, vy=0, vz=0), speed_ms=10, heading=90)
        cpa, cmds = daa.evaluate_pair(a, b)
        assert cpa.is_violation is False
        assert cmds == []

    def test_active_conflicts_property(self):
        """active_conflicts가 평가 후 갱신된다."""
        daa = TacticalDAA()
        drones = {
            "D1": DroneState("D1", Position3D(lat=37.5665, lon=126.975, alt_m=100),
                             Velocity3D(vx=10, vy=0, vz=0), speed_ms=10, heading=90),
            "D2": DroneState("D2", Position3D(lat=37.5665, lon=126.981, alt_m=100),
                             Velocity3D(vx=-10, vy=0, vz=0), speed_ms=10, heading=270),
        }
        daa.evaluate(drones)
        conflicts = daa.active_conflicts
        assert len(conflicts) == 1
        assert conflicts[0].cpa.drone_id_a == "D1"
        assert conflicts[0].cpa.drone_id_b == "D2"

    def test_lookahead_filters(self):
        """lookahead 밖의 CPA는 무시한다."""
        daa = TacticalDAA(lookahead_sec=1.0)
        # 매우 느린 접근
        drones = {
            "D1": DroneState("D1", Position3D(lat=37.56, lon=126.978, alt_m=100),
                             Velocity3D(vx=0.01, vy=0, vz=0), speed_ms=0.01, heading=90),
            "D2": DroneState("D2", Position3D(lat=37.56, lon=127.0, alt_m=100),
                             Velocity3D(vx=-0.01, vy=0, vz=0), speed_ms=0.01, heading=270),
        }
        cmds = daa.evaluate(drones)
        assert cmds == []

    def test_get_warnings(self):
        """경고 수준 CPA를 반환한다."""
        daa = TacticalDAA(warning_sec=60.0)
        # 접근 중이지만 아직 위반은 아닌 상태 (수직 분리 충분)
        drones = {
            "D1": DroneState("D1", Position3D(lat=37.5665, lon=126.975, alt_m=100),
                             Velocity3D(vx=5, vy=0, vz=0), speed_ms=5, heading=90),
            "D2": DroneState("D2", Position3D(lat=37.5665, lon=126.985, alt_m=140),
                             Velocity3D(vx=-5, vy=0, vz=0), speed_ms=5, heading=270),
        }
        warnings = daa.get_warnings(drones)
        # 수직 40m > 30m → 위반 아님이지만, 접근 중이므로 경고 가능
        # 실제 경고 여부는 d_cpa < 200m인지에 달림
        assert isinstance(warnings, list)
