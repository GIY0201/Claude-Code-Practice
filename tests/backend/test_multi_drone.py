"""다중 드론 시뮬레이터 테스트."""

import sys
from pathlib import Path

import pytest

backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from models.common import Position3D
from simulator.multi_drone import MultiDroneSim, DroneConfig


def _config(drone_id: str, lat: float = 37.5665, lon: float = 126.978,
            dest_lat: float = 37.57, dest_lon: float = 126.98) -> DroneConfig:
    return DroneConfig(
        drone_id=drone_id,
        waypoints=[
            Position3D(lat=lat, lon=lon, alt_m=100),
            Position3D(lat=dest_lat, lon=dest_lon, alt_m=100),
        ],
        speed_ms=50.0,
    )


class TestMultiDroneSim:
    def test_add_drone(self):
        sim = MultiDroneSim()
        sim.add_drone(_config("D1"))
        assert sim.drone_count == 1

    def test_add_duplicate_raises(self):
        sim = MultiDroneSim()
        sim.add_drone(_config("D1"))
        with pytest.raises(ValueError):
            sim.add_drone(_config("D1"))

    def test_remove_drone(self):
        sim = MultiDroneSim()
        sim.add_drone(_config("D1"))
        assert sim.remove_drone("D1") is True
        assert sim.drone_count == 0

    def test_remove_nonexistent(self):
        sim = MultiDroneSim()
        assert sim.remove_drone("D1") is False

    def test_tick_returns_all_telemetry(self):
        sim = MultiDroneSim()
        sim.add_drone(_config("D1"))
        sim.add_drone(_config("D2", lat=37.50))
        telems = sim.tick(dt_sec=0.1)
        assert len(telems) == 2
        ids = {t.drone_id for t in telems}
        assert ids == {"D1", "D2"}

    def test_independent_flight(self):
        """각 드론이 독립적으로 비행한다."""
        sim = MultiDroneSim()
        sim.add_drone(_config("D1", lat=37.56, dest_lat=37.57))
        sim.add_drone(_config("D2", lat=37.50, dest_lat=37.51))
        sim.tick(dt_sec=1.0)
        positions = sim.get_positions()
        assert positions["D1"].lat != positions["D2"].lat

    def test_all_completed(self):
        """모든 드론 도착 시 all_completed == True."""
        sim = MultiDroneSim()
        # 아주 가까운 경유점 + 빠른 속도
        sim.add_drone(DroneConfig(
            drone_id="D1",
            waypoints=[
                Position3D(lat=37.5665, lon=126.978, alt_m=100),
                Position3D(lat=37.5666, lon=126.978, alt_m=100),
            ],
            speed_ms=100.0,
        ))
        for _ in range(100):
            sim.tick(dt_sec=0.1)
            if sim.all_completed:
                break
        assert sim.all_completed

    def test_active_count(self):
        sim = MultiDroneSim()
        sim.add_drone(DroneConfig(
            drone_id="D1",
            waypoints=[
                Position3D(lat=37.5665, lon=126.978, alt_m=100),
                Position3D(lat=37.5666, lon=126.978, alt_m=100),
            ],
            speed_ms=100.0,
        ))
        sim.add_drone(_config("D2", dest_lat=37.60))  # 멀리
        assert sim.active_count == 2

        for _ in range(100):
            sim.tick(dt_sec=0.1)
            if sim.get_sim("D1").completed:
                break

        # D1 완료, D2 아직 비행 중
        assert sim.active_count == 1

    def test_empty_sim(self):
        sim = MultiDroneSim()
        assert sim.all_completed is True
        assert sim.tick(dt_sec=0.1) == []

    def test_multi_drone_positions(self):
        """get_positions가 전체 드론 위치를 반환한다."""
        sim = MultiDroneSim()
        sim.add_drone(_config("D1"))
        sim.add_drone(_config("D2"))
        sim.add_drone(_config("D3"))
        pos = sim.get_positions()
        assert len(pos) == 3
        assert "D1" in pos and "D2" in pos and "D3" in pos
