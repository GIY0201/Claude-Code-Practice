"""CPA 충돌 예측 엔진 테스트."""

import sys
from pathlib import Path

import pytest

backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from models.common import Position3D, Velocity3D
from core.deconfliction.cpa import compute_cpa, check_all_pairs, CPAResult


# ──────────── compute_cpa ────────────

class TestComputeCPA:
    def test_stationary_drones_far_apart(self):
        """정지 상태 드론 2대가 멀리 떨어져 있으면 위반 아님."""
        result = compute_cpa(
            "D1", Position3D(lat=37.5665, lon=126.978, alt_m=100),
            Velocity3D(),
            "D2", Position3D(lat=37.57, lon=126.978, alt_m=100),
            Velocity3D(),
        )
        assert result.is_violation is False
        assert result.t_cpa_sec == 0.0

    def test_stationary_drones_close(self):
        """정지 상태 드론 2대가 가까이 있으면 위반."""
        result = compute_cpa(
            "D1", Position3D(lat=37.5665, lon=126.978, alt_m=100),
            Velocity3D(),
            "D2", Position3D(lat=37.5665, lon=126.9781, alt_m=100),
            Velocity3D(),
        )
        # ~8.8m 떨어져 있음 → 수평 100m 미만이고 수직 0m < 30m → 위반
        assert result.is_violation is True

    def test_head_on_collision(self):
        """정면 충돌 코스 — 서로를 향해 비행."""
        # D1: 동쪽으로 10m/s, D2: 서쪽으로 10m/s, 같은 고도
        result = compute_cpa(
            "D1", Position3D(lat=37.5665, lon=126.975, alt_m=100),
            Velocity3D(vx=10.0, vy=0, vz=0),
            "D2", Position3D(lat=37.5665, lon=126.981, alt_m=100),
            Velocity3D(vx=-10.0, vy=0, vz=0),
        )
        assert result.is_violation is True
        assert result.t_cpa_sec > 0
        # 충돌 지점에서의 거리가 매우 작아야 함
        assert result.d_cpa_m < 10

    def test_parallel_no_collision(self):
        """같은 방향으로 평행 비행 — 충돌 없음."""
        result = compute_cpa(
            "D1", Position3D(lat=37.5665, lon=126.978, alt_m=100),
            Velocity3D(vx=10.0, vy=0, vz=0),
            "D2", Position3D(lat=37.57, lon=126.978, alt_m=100),
            Velocity3D(vx=10.0, vy=0, vz=0),
        )
        # 상대 속도가 0이므로 거리 변하지 않음
        assert result.is_violation is False

    def test_diverging_drones(self):
        """서로 멀어지는 방향 — CPA는 현재(t=0)."""
        result = compute_cpa(
            "D1", Position3D(lat=37.5665, lon=126.978, alt_m=100),
            Velocity3D(vx=-10.0, vy=0, vz=0),  # 서쪽으로
            "D2", Position3D(lat=37.5665, lon=126.98, alt_m=100),
            Velocity3D(vx=10.0, vy=0, vz=0),   # 동쪽으로
        )
        assert result.t_cpa_sec == 0.0

    def test_vertical_separation_prevents_violation(self):
        """수직 이격이 충분하면 위반이 아님."""
        result = compute_cpa(
            "D1", Position3D(lat=37.5665, lon=126.978, alt_m=100),
            Velocity3D(vx=10.0, vy=0, vz=0),
            "D2", Position3D(lat=37.5665, lon=126.980, alt_m=150),  # 50m 위
            Velocity3D(vx=-10.0, vy=0, vz=0),
        )
        # 수직 50m > 30m → 위반 아님
        assert result.is_violation is False

    def test_crossing_paths(self):
        """교차 경로 — 하나는 동쪽, 하나는 북쪽."""
        result = compute_cpa(
            "D1", Position3D(lat=37.5665, lon=126.975, alt_m=100),
            Velocity3D(vx=10.0, vy=0, vz=0),     # 동쪽
            "D2", Position3D(lat=37.563, lon=126.978, alt_m=100),
            Velocity3D(vx=0, vy=10.0, vz=0),     # 북쪽
        )
        # 교차하므로 CPA가 존재
        assert result.t_cpa_sec > 0
        # 교차점에서 근접 가능
        assert isinstance(result.d_cpa_m, float)


# ──────────── check_all_pairs ────────────

class TestCheckAllPairs:
    def test_no_drones(self):
        assert check_all_pairs({}) == []

    def test_single_drone(self):
        drones = {
            "D1": (Position3D(lat=37.5665, lon=126.978, alt_m=100), Velocity3D()),
        }
        assert check_all_pairs(drones) == []

    def test_two_safe_drones(self):
        """충분히 떨어진 2대 → 위반 없음."""
        drones = {
            "D1": (Position3D(lat=37.56, lon=126.978, alt_m=100), Velocity3D()),
            "D2": (Position3D(lat=37.58, lon=126.978, alt_m=100), Velocity3D()),
        }
        violations = check_all_pairs(drones)
        assert len(violations) == 0

    def test_two_violating_drones(self):
        """정면 충돌 코스 → 위반 감지."""
        drones = {
            "D1": (
                Position3D(lat=37.5665, lon=126.975, alt_m=100),
                Velocity3D(vx=10.0, vy=0, vz=0),
            ),
            "D2": (
                Position3D(lat=37.5665, lon=126.981, alt_m=100),
                Velocity3D(vx=-10.0, vy=0, vz=0),
            ),
        }
        violations = check_all_pairs(drones)
        assert len(violations) == 1
        assert violations[0].drone_id_a == "D1"
        assert violations[0].drone_id_b == "D2"

    def test_three_drones_one_violation(self):
        """3대 중 1쌍만 위반."""
        drones = {
            "D1": (
                Position3D(lat=37.5665, lon=126.975, alt_m=100),
                Velocity3D(vx=10.0, vy=0, vz=0),
            ),
            "D2": (
                Position3D(lat=37.5665, lon=126.981, alt_m=100),
                Velocity3D(vx=-10.0, vy=0, vz=0),
            ),
            "D3": (
                Position3D(lat=37.60, lon=126.978, alt_m=200),  # 멀리 떨어짐
                Velocity3D(),
            ),
        }
        violations = check_all_pairs(drones)
        assert len(violations) == 1

    def test_lookahead_filters(self):
        """CPA가 lookahead 밖이면 무시한다."""
        # 매우 느린 접근 → CPA가 먼 미래
        drones = {
            "D1": (
                Position3D(lat=37.56, lon=126.978, alt_m=100),
                Velocity3D(vx=0.01, vy=0, vz=0),
            ),
            "D2": (
                Position3D(lat=37.56, lon=127.0, alt_m=100),
                Velocity3D(vx=-0.01, vy=0, vz=0),
            ),
        }
        # lookahead 1초로 짧게 → 위반 필터됨
        violations = check_all_pairs(drones, lookahead_sec=1.0)
        assert len(violations) == 0
