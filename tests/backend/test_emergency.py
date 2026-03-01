"""Tests for emergency detection and handling."""

import time
import pytest

from models.common import (
    Position3D,
    Velocity3D,
    GPSFixType,
    MotorStatus,
    AlertLevel,
    Alert,
    Priority,
)
from models.telemetry import Telemetry
from core.emergency.detector import (
    EmergencyDetector,
    EmergencyEvent,
    EmergencyType,
    EmergencySeverity,
)
from core.emergency.handler import (
    EmergencyHandler,
    EmergencyAction,
    EmergencyResponse,
    LandingZone,
    _haversine,
)


# ── helpers ─────────────────────────────────────────────────────────


def _telem(
    drone_id: str = "SKY-001",
    battery: float = 80.0,
    gps: GPSFixType = GPSFixType.FIX_3D,
    motors: list[MotorStatus] | None = None,
    lat: float = 37.56,
    lon: float = 126.98,
    alt: float = 100.0,
) -> Telemetry:
    return Telemetry(
        drone_id=drone_id,
        timestamp="2026-01-01T00:00:00Z",
        position=Position3D(lat=lat, lon=lon, alt_m=alt),
        velocity=Velocity3D(vx=5, vy=0, vz=0),
        heading=90,
        battery_percent=battery,
        gps_fix=gps,
        signal_strength=90,
        motor_status=motors or [MotorStatus.OK] * 4,
        alerts=[],
    )


# ── EmergencyDetector ──────────────────────────────────────────────


class TestDetectorBattery:
    def test_normal_battery_no_event(self):
        d = EmergencyDetector()
        events = d.update(_telem(battery=50))
        assert len(events) == 0

    def test_low_battery_warning(self):
        d = EmergencyDetector()
        events = d.update(_telem(battery=18))
        assert len(events) == 1
        assert events[0].emergency_type == EmergencyType.BATTERY_LOW
        assert events[0].severity == EmergencySeverity.WARNING

    def test_critical_battery(self):
        d = EmergencyDetector()
        events = d.update(_telem(battery=8))
        assert len(events) == 1
        assert events[0].emergency_type == EmergencyType.BATTERY_CRITICAL
        assert events[0].severity == EmergencySeverity.CRITICAL

    def test_no_duplicate_alerts(self):
        d = EmergencyDetector()
        d.update(_telem(battery=15))
        events = d.update(_telem(battery=14))
        assert len(events) == 0  # already flagged

    def test_escalation_low_to_critical(self):
        d = EmergencyDetector()
        d.update(_telem(battery=18))
        events = d.update(_telem(battery=8))
        assert len(events) == 1
        assert events[0].emergency_type == EmergencyType.BATTERY_CRITICAL

    def test_battery_recovery_clears(self):
        d = EmergencyDetector()
        d.update(_telem(battery=15))
        d.update(_telem(battery=50))  # recovered
        events = d.update(_telem(battery=18))  # should re-trigger
        assert len(events) == 1
        assert events[0].emergency_type == EmergencyType.BATTERY_LOW


class TestDetectorGPS:
    def test_good_gps_no_event(self):
        d = EmergencyDetector()
        events = d.update(_telem(gps=GPSFixType.FIX_3D))
        assert len(events) == 0

    def test_no_fix_triggers(self):
        d = EmergencyDetector()
        events = d.update(_telem(gps=GPSFixType.NO_FIX))
        assert len(events) == 1
        assert events[0].emergency_type == EmergencyType.GPS_DEGRADED

    def test_2d_fix_triggers(self):
        d = EmergencyDetector()
        events = d.update(_telem(gps=GPSFixType.FIX_2D))
        assert len(events) == 1
        assert events[0].emergency_type == EmergencyType.GPS_DEGRADED

    def test_rtk_ok(self):
        d = EmergencyDetector()
        events = d.update(_telem(gps=GPSFixType.RTK))
        assert len(events) == 0

    def test_gps_recovery(self):
        d = EmergencyDetector()
        d.update(_telem(gps=GPSFixType.NO_FIX))
        d.update(_telem(gps=GPSFixType.FIX_3D))
        assert EmergencyType.GPS_DEGRADED not in d.get_active_emergencies("SKY-001")


class TestDetectorMotor:
    def test_all_ok_no_event(self):
        d = EmergencyDetector()
        events = d.update(_telem(motors=[MotorStatus.OK] * 4))
        assert len(events) == 0

    def test_motor_failure(self):
        d = EmergencyDetector()
        motors = [MotorStatus.OK, MotorStatus.FAILURE, MotorStatus.OK, MotorStatus.OK]
        events = d.update(_telem(motors=motors))
        assert len(events) == 1
        assert events[0].emergency_type == EmergencyType.MOTOR_FAILURE
        assert events[0].severity == EmergencySeverity.CRITICAL

    def test_motor_recovery(self):
        d = EmergencyDetector()
        d.update(_telem(motors=[MotorStatus.OK, MotorStatus.FAILURE, MotorStatus.OK, MotorStatus.OK]))
        d.update(_telem(motors=[MotorStatus.OK] * 4))
        assert EmergencyType.MOTOR_FAILURE not in d.get_active_emergencies("SKY-001")


class TestDetectorComms:
    def test_recent_telemetry_no_event(self):
        d = EmergencyDetector()
        d.update(_telem())
        events = d.check_comms()
        assert len(events) == 0

    def test_comms_lost_after_timeout(self):
        d = EmergencyDetector(comms_lost_sec=30)
        d._last_seen["SKY-001"] = time.time() - 35
        d._active["SKY-001"] = set()
        events = d.check_comms()
        assert len(events) == 1
        assert events[0].emergency_type == EmergencyType.COMMS_LOST

    def test_comms_critical(self):
        d = EmergencyDetector(comms_lost_sec=30, comms_critical_sec=60)
        d._last_seen["SKY-001"] = time.time() - 65
        d._active["SKY-001"] = set()
        events = d.check_comms()
        assert len(events) == 1
        assert events[0].emergency_type == EmergencyType.COMMS_CRITICAL

    def test_telemetry_resets_comms(self):
        d = EmergencyDetector()
        d._last_seen["SKY-001"] = time.time() - 40
        d._active["SKY-001"] = {EmergencyType.COMMS_LOST}
        d.update(_telem())  # fresh telemetry
        assert EmergencyType.COMMS_LOST not in d.get_active_emergencies("SKY-001")


class TestDetectorMisc:
    def test_clear_drone(self):
        d = EmergencyDetector()
        d.update(_telem())
        d.clear_drone("SKY-001")
        assert "SKY-001" not in d._last_seen
        assert "SKY-001" not in d._active

    def test_multiple_drones(self):
        d = EmergencyDetector()
        d.update(_telem(drone_id="A", battery=8))
        d.update(_telem(drone_id="B", battery=50))
        assert EmergencyType.BATTERY_CRITICAL in d.get_active_emergencies("A")
        assert len(d.get_active_emergencies("B")) == 0


# ── EmergencyHandler ───────────────────────────────────────────────


class TestHandlerLandingZone:
    def test_find_nearest(self):
        zones = [
            LandingZone("Z1", "Near", Position3D(lat=37.56, lon=126.98, alt_m=10)),
            LandingZone("Z2", "Far", Position3D(lat=37.60, lon=127.10, alt_m=10)),
        ]
        h = EmergencyHandler(landing_zones=zones)
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        nearest = h.find_nearest_landing_zone(pos)
        assert nearest is not None
        assert nearest.zone_id == "Z1"

    def test_no_zones(self):
        h = EmergencyHandler(landing_zones=[])
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        assert h.find_nearest_landing_zone(pos) is None


class TestHandlerBattery:
    def test_battery_critical_emergency_landing(self):
        h = EmergencyHandler()
        event = EmergencyEvent(
            drone_id="SKY-001",
            emergency_type=EmergencyType.BATTERY_CRITICAL,
            severity=EmergencySeverity.CRITICAL,
            message="Battery critical",
        )
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        resp = h.handle(event, pos)
        assert resp.action == EmergencyAction.IMMEDIATE_DESCENT
        assert resp.priority == Priority.EMERGENCY
        assert resp.landing_zone is not None
        assert resp.route is not None
        assert len(resp.route) >= 2

    def test_battery_low_divert(self):
        h = EmergencyHandler()
        event = EmergencyEvent(
            drone_id="SKY-001",
            emergency_type=EmergencyType.BATTERY_LOW,
            severity=EmergencySeverity.WARNING,
            message="Battery low",
        )
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        resp = h.handle(event, pos)
        assert resp.action == EmergencyAction.DIVERT_TO_LANDING
        assert resp.priority == Priority.HIGH

    def test_battery_critical_no_zones(self):
        h = EmergencyHandler(landing_zones=[])
        event = EmergencyEvent(
            drone_id="SKY-001",
            emergency_type=EmergencyType.BATTERY_CRITICAL,
            severity=EmergencySeverity.CRITICAL,
            message="Battery critical",
        )
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        resp = h.handle(event, pos)
        assert resp.action == EmergencyAction.IMMEDIATE_DESCENT
        assert resp.landing_zone is None


class TestHandlerComms:
    def test_comms_lost_continue(self):
        h = EmergencyHandler()
        event = EmergencyEvent(
            drone_id="SKY-001",
            emergency_type=EmergencyType.COMMS_LOST,
            severity=EmergencySeverity.WARNING,
            message="Comms lost",
        )
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        resp = h.handle(event, pos)
        assert resp.action == EmergencyAction.CONTINUE_PLAN

    def test_comms_critical_rtl(self):
        h = EmergencyHandler()
        h.set_launch_position("SKY-001", Position3D(lat=37.55, lon=126.97, alt_m=10))
        event = EmergencyEvent(
            drone_id="SKY-001",
            emergency_type=EmergencyType.COMMS_CRITICAL,
            severity=EmergencySeverity.CRITICAL,
            message="Comms critical",
        )
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        resp = h.handle(event, pos)
        assert resp.action == EmergencyAction.RETURN_TO_LAUNCH
        assert resp.route is not None

    def test_comms_critical_no_launch_descend(self):
        h = EmergencyHandler()
        event = EmergencyEvent(
            drone_id="SKY-001",
            emergency_type=EmergencyType.COMMS_CRITICAL,
            severity=EmergencySeverity.CRITICAL,
            message="Comms critical",
        )
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        resp = h.handle(event, pos)
        assert resp.action == EmergencyAction.HOLD_AND_DESCEND


class TestHandlerGPS:
    def test_gps_expand_separation(self):
        h = EmergencyHandler()
        event = EmergencyEvent(
            drone_id="SKY-001",
            emergency_type=EmergencyType.GPS_DEGRADED,
            severity=EmergencySeverity.WARNING,
            message="GPS degraded",
        )
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        resp = h.handle(event, pos)
        assert resp.action == EmergencyAction.EXPAND_SEPARATION
        assert resp.separation_multiplier == 2.0


class TestHandlerMotor:
    def test_motor_failure_emergency(self):
        h = EmergencyHandler()
        event = EmergencyEvent(
            drone_id="SKY-001",
            emergency_type=EmergencyType.MOTOR_FAILURE,
            severity=EmergencySeverity.CRITICAL,
            message="Motor failure",
        )
        pos = Position3D(lat=37.56, lon=126.98, alt_m=100)
        resp = h.handle(event, pos)
        assert resp.action == EmergencyAction.IMMEDIATE_DESCENT
        assert resp.priority == Priority.EMERGENCY
