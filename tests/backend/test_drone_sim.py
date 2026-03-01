"""단일 드론 시뮬레이터 테스트."""

import sys
from pathlib import Path

import pytest

backend_dir = str(Path(__file__).resolve().parent.parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from models.common import Position3D, DroneStatus
from simulator.drone_sim import DroneSim, _bearing, _distance_3d


# ──────────── Helper ────────────

SEOUL = Position3D(lat=37.5665, lon=126.9780, alt_m=100.0)
GANGNAM = Position3D(lat=37.4979, lon=127.0276, alt_m=100.0)
YEOUIDO = Position3D(lat=37.5219, lon=126.9245, alt_m=100.0)


# ──────────── _bearing / _distance_3d ────────────

def test_bearing_east():
    """동쪽으로 이동 시 약 90°."""
    a = Position3D(lat=37.5665, lon=126.978, alt_m=0)
    b = Position3D(lat=37.5665, lon=127.0, alt_m=0)
    h = _bearing(a, b)
    assert 85 < h < 95


def test_bearing_south():
    """남쪽으로 이동 시 약 180°."""
    a = Position3D(lat=37.57, lon=126.978, alt_m=0)
    b = Position3D(lat=37.50, lon=126.978, alt_m=0)
    h = _bearing(a, b)
    assert 175 < h < 185


def test_distance_3d_horizontal():
    """같은 고도면 haversine과 동일."""
    d = _distance_3d(SEOUL, GANGNAM)
    assert d > 5000  # 약 8.7km


def test_distance_3d_vertical():
    """같은 수평 좌표, 고도만 다르면 고도차만."""
    a = Position3D(lat=37.5665, lon=126.978, alt_m=0)
    b = Position3D(lat=37.5665, lon=126.978, alt_m=100)
    d = _distance_3d(a, b)
    assert abs(d - 100.0) < 1.0


# ──────────── DroneSim Init ────────────

def test_init_minimum_waypoints():
    """최소 2개 경유점 필요."""
    with pytest.raises(ValueError):
        DroneSim(drone_id="D1", waypoints=[SEOUL])


def test_init_status_airborne():
    """생성 시 AIRBORNE 상태."""
    sim = DroneSim(drone_id="D1", waypoints=[SEOUL, GANGNAM])
    assert sim.status == DroneStatus.AIRBORNE
    assert not sim.completed


def test_init_position_at_departure():
    """시작 위치는 첫 경유점."""
    sim = DroneSim(drone_id="D1", waypoints=[SEOUL, GANGNAM])
    assert sim.position.lat == SEOUL.lat
    assert sim.position.lon == SEOUL.lon


# ──────────── Tick & Movement ────────────

def test_tick_moves_drone():
    """tick() 호출 시 드론이 이동한다."""
    sim = DroneSim(drone_id="D1", waypoints=[SEOUL, GANGNAM], speed_ms=50.0)
    initial_pos = sim.position.model_copy()
    sim.tick(dt_sec=1.0)
    # 위치가 변경되어야 한다
    assert sim.position.lat != initial_pos.lat or sim.position.lon != initial_pos.lon


def test_tick_returns_telemetry():
    """tick()은 Telemetry 객체를 반환한다."""
    sim = DroneSim(drone_id="D1", waypoints=[SEOUL, GANGNAM])
    telem = sim.tick(dt_sec=0.1)
    assert telem.drone_id == "D1"
    assert telem.position is not None
    assert telem.velocity is not None
    assert 0 <= telem.heading < 360


def test_drone_reaches_destination():
    """충분한 틱 후 목적지에 도착하여 LANDED 상태."""
    start = Position3D(lat=37.5665, lon=126.978, alt_m=100)
    end = Position3D(lat=37.5670, lon=126.978, alt_m=100)  # ~55m 떨어짐
    sim = DroneSim(drone_id="D1", waypoints=[start, end], speed_ms=50.0)

    for _ in range(100):
        sim.tick(dt_sec=0.1)
        if sim.completed:
            break

    assert sim.completed
    assert sim.status == DroneStatus.LANDED


def test_multi_waypoint_flight():
    """여러 경유점을 순서대로 통과한다."""
    wps = [SEOUL, YEOUIDO, GANGNAM]
    sim = DroneSim(drone_id="D1", waypoints=wps, speed_ms=500.0)

    for _ in range(5000):
        sim.tick(dt_sec=0.1)
        if sim.completed:
            break

    assert sim.completed
    assert sim.status == DroneStatus.LANDED


def test_heading_updates_per_waypoint():
    """경유점 전환 시 헤딩이 업데이트된다."""
    wps = [SEOUL, YEOUIDO, GANGNAM]
    sim = DroneSim(drone_id="D1", waypoints=wps, speed_ms=500.0)
    initial_heading = sim._heading

    # 여의도 도착까지 이동
    for _ in range(2000):
        sim.tick(dt_sec=0.1)
        if sim.current_waypoint_index >= 2:
            break

    # 여의도→강남은 남동쪽 — 초기 헤딩(서쪽)과 다름
    assert sim._heading != initial_heading


# ──────────── Battery ────────────

def test_battery_drains():
    """비행 시 배터리가 소모된다."""
    sim = DroneSim(
        drone_id="D1", waypoints=[SEOUL, GANGNAM],
        battery_drain_per_sec=1.0,
    )
    sim.tick(dt_sec=1.0)
    assert sim.battery_percent < 100.0


def test_battery_critical_triggers_emergency():
    """배터리 10% 미만 시 EMERGENCY 상태 + CRITICAL 알림."""
    sim = DroneSim(
        drone_id="D1", waypoints=[SEOUL, GANGNAM],
        battery_percent=10.5,
        battery_drain_per_sec=2.0,
    )
    telem = sim.tick(dt_sec=1.0)  # 10.5 - 2 = 8.5%
    assert sim.status == DroneStatus.EMERGENCY
    assert any(a.level.value == "CRITICAL" for a in telem.alerts)


def test_battery_low_warning():
    """배터리 20% 미만 시 WARNING 알림."""
    sim = DroneSim(
        drone_id="D1", waypoints=[SEOUL, GANGNAM],
        battery_percent=19.0,
        battery_drain_per_sec=0.0,
    )
    telem = sim.tick(dt_sec=0.1)
    assert any(a.level.value == "WARNING" for a in telem.alerts)


# ──────────── Completed state ────────────

def test_no_movement_after_completion():
    """완료 후 위치가 변하지 않는다."""
    start = Position3D(lat=37.5665, lon=126.978, alt_m=100)
    end = Position3D(lat=37.5666, lon=126.978, alt_m=100)
    sim = DroneSim(drone_id="D1", waypoints=[start, end], speed_ms=100.0)

    # 완료까지 이동
    for _ in range(100):
        sim.tick(dt_sec=0.1)
        if sim.completed:
            break

    final_pos = sim.position.model_copy()
    sim.tick(dt_sec=1.0)
    assert sim.position.lat == final_pos.lat
    assert sim.position.lon == final_pos.lon
