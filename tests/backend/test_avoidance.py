"""DAA 회피 기동 전략 테스트."""

import sys
from pathlib import Path

import pytest

backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from models.common import Position3D, Velocity3D, Priority
from core.deconfliction.cpa import compute_cpa
from core.deconfliction.avoidance import (
    AvoidanceCommand, DroneState, ManeuverType,
    resolve_conflict, _yielding_drone,
)


# ──────────── _yielding_drone ────────────

class TestYieldingDrone:
    def test_lower_priority_yields(self):
        """낮은 우선순위 드론이 양보한다."""
        a = DroneState("D1", Position3D(lat=37.56, lon=126.97, alt_m=100),
                       Velocity3D(), speed_ms=10, heading=0, priority=Priority.NORMAL)
        b = DroneState("D2", Position3D(lat=37.57, lon=126.97, alt_m=100),
                       Velocity3D(), speed_ms=10, heading=0, priority=Priority.HIGH)
        yielder, keeper = _yielding_drone(a, b)
        assert yielder.drone_id == "D1"
        assert keeper.drone_id == "D2"

    def test_emergency_never_yields(self):
        """EMERGENCY 우선순위는 양보하지 않는다."""
        a = DroneState("D1", Position3D(lat=37.56, lon=126.97, alt_m=100),
                       Velocity3D(), speed_ms=10, heading=0, priority=Priority.EMERGENCY)
        b = DroneState("D2", Position3D(lat=37.57, lon=126.97, alt_m=100),
                       Velocity3D(), speed_ms=10, heading=0, priority=Priority.HIGH)
        yielder, keeper = _yielding_drone(a, b)
        assert yielder.drone_id == "D2"

    def test_same_priority_id_tiebreak(self):
        """동일 우선순위면 ID 사전순 후순위가 양보."""
        a = DroneState("D1", Position3D(lat=37.56, lon=126.97, alt_m=100),
                       Velocity3D(), speed_ms=10, heading=0, priority=Priority.NORMAL)
        b = DroneState("D2", Position3D(lat=37.57, lon=126.97, alt_m=100),
                       Velocity3D(), speed_ms=10, heading=0, priority=Priority.NORMAL)
        yielder, keeper = _yielding_drone(a, b)
        assert yielder.drone_id == "D2"  # D2 > D1
        assert keeper.drone_id == "D1"


# ──────────── resolve_conflict ────────────

class TestResolveConflict:
    def _make_cpa(self, t_sec: float, d_m: float, h_sep: float, v_sep: float) -> "CPAResult":
        """테스트용 CPAResult 생성."""
        from core.deconfliction.cpa import CPAResult
        return CPAResult(
            drone_id_a="D1", drone_id_b="D2",
            t_cpa_sec=t_sec, d_cpa_m=d_m,
            current_distance_m=200.0,
            horizontal_sep_m=h_sep, vertical_sep_m=v_sep,
            is_violation=True,
        )

    def _make_states(self, alt_a=100.0, alt_b=100.0, speed=10.0,
                     priority_a=Priority.NORMAL, priority_b=Priority.NORMAL):
        a = DroneState("D1", Position3D(lat=37.56, lon=126.975, alt_m=alt_a),
                       Velocity3D(vx=10, vy=0, vz=0), speed_ms=speed,
                       heading=90, priority=priority_a)
        b = DroneState("D2", Position3D(lat=37.56, lon=126.981, alt_m=alt_b),
                       Velocity3D(vx=-10, vy=0, vz=0), speed_ms=speed,
                       heading=270, priority=priority_b)
        return a, b

    def test_speed_reduction_for_far_cpa(self):
        """t_cpa > 3초이면 속도 감속 전략."""
        cpa = self._make_cpa(t_sec=15.0, d_m=50.0, h_sep=50.0, v_sep=0.0)
        a, b = self._make_states()
        cmds = resolve_conflict(cpa, a, b)
        assert len(cmds) == 1
        assert cmds[0].maneuver_type == ManeuverType.SPEED_CHANGE
        assert cmds[0].target_speed_ms < 10.0  # 감속
        assert cmds[0].drone_id == "D2"  # D2 양보 (D2 > D1)

    def test_altitude_change_for_close_cpa(self):
        """t_cpa <= 3초이고 수직 이격 부족이면 고도 변경."""
        cpa = self._make_cpa(t_sec=2.0, d_m=30.0, h_sep=20.0, v_sep=5.0)
        a, b = self._make_states()
        cmds = resolve_conflict(cpa, a, b)
        assert len(cmds) == 1
        assert cmds[0].maneuver_type == ManeuverType.ALTITUDE_CHANGE
        assert cmds[0].target_alt_m is not None
        assert cmds[0].target_alt_m != a.position.alt_m

    def test_lateral_offset_for_horizontal_violation(self):
        """수직 이격 충분, 수평 이격 부족이면 수평 우회."""
        cpa = self._make_cpa(t_sec=2.0, d_m=80.0, h_sep=70.0, v_sep=35.0)
        a, b = self._make_states()
        cmds = resolve_conflict(cpa, a, b)
        assert len(cmds) == 1
        assert cmds[0].maneuver_type == ManeuverType.LATERAL_OFFSET
        assert cmds[0].heading_offset_deg is not None

    def test_hold_as_last_resort(self):
        """모든 전략 불가 시 정지."""
        cpa = self._make_cpa(t_sec=1.0, d_m=200.0, h_sep=150.0, v_sep=50.0)
        a, b = self._make_states()
        cmds = resolve_conflict(cpa, a, b)
        assert len(cmds) == 1
        assert cmds[0].maneuver_type == ManeuverType.HOLD

    def test_high_priority_keeps_flying(self):
        """HIGH 우선순위 드론은 양보하지 않는다."""
        cpa = self._make_cpa(t_sec=10.0, d_m=50.0, h_sep=50.0, v_sep=0.0)
        a, b = self._make_states(priority_a=Priority.HIGH, priority_b=Priority.NORMAL)
        cmds = resolve_conflict(cpa, a, b)
        assert cmds[0].drone_id == "D2"  # NORMAL이 양보

    def test_altitude_clamp_high(self):
        """고도가 400m 초과되면 아래로 이동."""
        cpa = self._make_cpa(t_sec=2.0, d_m=30.0, h_sep=20.0, v_sep=5.0)
        a, b = self._make_states(alt_a=390.0, alt_b=390.0)
        cmds = resolve_conflict(cpa, a, b)
        assert cmds[0].maneuver_type == ManeuverType.ALTITUDE_CHANGE
        assert cmds[0].target_alt_m <= 400.0

    def test_altitude_clamp_low(self):
        """고도가 30m 미만이면 30m로 클램프."""
        cpa = self._make_cpa(t_sec=2.0, d_m=30.0, h_sep=20.0, v_sep=5.0)
        a, b = self._make_states(alt_a=50.0, alt_b=50.0)
        cmds = resolve_conflict(cpa, a, b)
        assert cmds[0].target_alt_m >= 30.0

    def test_command_has_reason(self):
        """모든 명령에 사유가 있다."""
        cpa = self._make_cpa(t_sec=10.0, d_m=50.0, h_sep=50.0, v_sep=0.0)
        a, b = self._make_states()
        cmds = resolve_conflict(cpa, a, b)
        assert len(cmds[0].reason) > 0
