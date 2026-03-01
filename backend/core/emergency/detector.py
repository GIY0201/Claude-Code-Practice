"""Emergency condition detector.

Monitors telemetry streams and identifies emergency situations:
- Battery low / critical
- Communication loss (stale telemetry)
- GPS degradation
- Motor failure
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum

from models.common import GPSFixType, MotorStatus
from models.telemetry import Telemetry


class EmergencyType(str, Enum):
    BATTERY_LOW = "BATTERY_LOW"  # < 20 %
    BATTERY_CRITICAL = "BATTERY_CRITICAL"  # < 10 %
    COMMS_LOST = "COMMS_LOST"  # no telemetry > 30 s
    COMMS_CRITICAL = "COMMS_CRITICAL"  # no telemetry > 60 s
    GPS_DEGRADED = "GPS_DEGRADED"  # 2D or NO_FIX
    MOTOR_FAILURE = "MOTOR_FAILURE"  # any motor FAILURE


class EmergencySeverity(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class EmergencyEvent:
    drone_id: str
    emergency_type: EmergencyType
    severity: EmergencySeverity
    message: str
    timestamp: float = field(default_factory=time.time)


# ── thresholds ──────────────────────────────────────────────────────

_BATTERY_LOW_PCT = 20.0
_BATTERY_CRITICAL_PCT = 10.0
_COMMS_LOST_SEC = 30.0
_COMMS_CRITICAL_SEC = 60.0


class EmergencyDetector:
    """Detect emergency conditions from telemetry updates.

    Call :meth:`update` with each telemetry packet.  Call
    :meth:`check_comms` periodically to detect stale connections.
    """

    def __init__(
        self,
        battery_low_pct: float = _BATTERY_LOW_PCT,
        battery_critical_pct: float = _BATTERY_CRITICAL_PCT,
        comms_lost_sec: float = _COMMS_LOST_SEC,
        comms_critical_sec: float = _COMMS_CRITICAL_SEC,
    ) -> None:
        self.battery_low = battery_low_pct
        self.battery_critical = battery_critical_pct
        self.comms_lost = comms_lost_sec
        self.comms_critical = comms_critical_sec

        # last-seen wall-clock time per drone
        self._last_seen: dict[str, float] = {}
        # active emergency flags so we don't re-fire continuously
        self._active: dict[str, set[EmergencyType]] = {}

    def update(self, telemetry: Telemetry) -> list[EmergencyEvent]:
        """Process a telemetry packet and return any new emergencies."""
        did = telemetry.drone_id
        self._last_seen[did] = time.time()
        if did not in self._active:
            self._active[did] = set()

        events: list[EmergencyEvent] = []

        # ── battery ─────────────────────────────────────────────────
        if telemetry.battery_percent < self.battery_critical:
            if EmergencyType.BATTERY_CRITICAL not in self._active[did]:
                self._active[did].add(EmergencyType.BATTERY_CRITICAL)
                # Remove lower-severity duplicate
                self._active[did].discard(EmergencyType.BATTERY_LOW)
                events.append(
                    EmergencyEvent(
                        drone_id=did,
                        emergency_type=EmergencyType.BATTERY_CRITICAL,
                        severity=EmergencySeverity.CRITICAL,
                        message=f"Battery critical: {telemetry.battery_percent:.1f}%",
                    )
                )
        elif telemetry.battery_percent < self.battery_low:
            if EmergencyType.BATTERY_LOW not in self._active[did]:
                self._active[did].add(EmergencyType.BATTERY_LOW)
                events.append(
                    EmergencyEvent(
                        drone_id=did,
                        emergency_type=EmergencyType.BATTERY_LOW,
                        severity=EmergencySeverity.WARNING,
                        message=f"Battery low: {telemetry.battery_percent:.1f}%",
                    )
                )
        else:
            # Battery recovered (e.g. swap) → clear flags
            self._active[did].discard(EmergencyType.BATTERY_LOW)
            self._active[did].discard(EmergencyType.BATTERY_CRITICAL)

        # ── GPS ─────────────────────────────────────────────────────
        if telemetry.gps_fix in (GPSFixType.NO_FIX, GPSFixType.FIX_2D):
            if EmergencyType.GPS_DEGRADED not in self._active[did]:
                self._active[did].add(EmergencyType.GPS_DEGRADED)
                events.append(
                    EmergencyEvent(
                        drone_id=did,
                        emergency_type=EmergencyType.GPS_DEGRADED,
                        severity=EmergencySeverity.WARNING,
                        message=f"GPS degraded: {telemetry.gps_fix.value}",
                    )
                )
        else:
            self._active[did].discard(EmergencyType.GPS_DEGRADED)

        # ── motor ───────────────────────────────────────────────────
        failed = [
            i
            for i, m in enumerate(telemetry.motor_status)
            if m == MotorStatus.FAILURE
        ]
        if failed:
            if EmergencyType.MOTOR_FAILURE not in self._active[did]:
                self._active[did].add(EmergencyType.MOTOR_FAILURE)
                events.append(
                    EmergencyEvent(
                        drone_id=did,
                        emergency_type=EmergencyType.MOTOR_FAILURE,
                        severity=EmergencySeverity.CRITICAL,
                        message=f"Motor failure on motor(s): {failed}",
                    )
                )
        else:
            self._active[did].discard(EmergencyType.MOTOR_FAILURE)

        # Comms reset — we just received data
        self._active[did].discard(EmergencyType.COMMS_LOST)
        self._active[did].discard(EmergencyType.COMMS_CRITICAL)

        return events

    def check_comms(self, now: float | None = None) -> list[EmergencyEvent]:
        """Check all tracked drones for communication timeouts.

        Call periodically (e.g. every second) from the main loop.
        """
        if now is None:
            now = time.time()

        events: list[EmergencyEvent] = []
        for did, last in self._last_seen.items():
            if did not in self._active:
                self._active[did] = set()

            gap = now - last

            if gap >= self.comms_critical:
                if EmergencyType.COMMS_CRITICAL not in self._active[did]:
                    self._active[did].add(EmergencyType.COMMS_CRITICAL)
                    self._active[did].discard(EmergencyType.COMMS_LOST)
                    events.append(
                        EmergencyEvent(
                            drone_id=did,
                            emergency_type=EmergencyType.COMMS_CRITICAL,
                            severity=EmergencySeverity.CRITICAL,
                            message=f"Communications lost for {gap:.0f}s — critical",
                        )
                    )
            elif gap >= self.comms_lost:
                if EmergencyType.COMMS_LOST not in self._active[did]:
                    self._active[did].add(EmergencyType.COMMS_LOST)
                    events.append(
                        EmergencyEvent(
                            drone_id=did,
                            emergency_type=EmergencyType.COMMS_LOST,
                            severity=EmergencySeverity.WARNING,
                            message=f"Communications lost for {gap:.0f}s",
                        )
                    )

        return events

    def clear_drone(self, drone_id: str) -> None:
        """Stop tracking a drone (e.g. after landing)."""
        self._last_seen.pop(drone_id, None)
        self._active.pop(drone_id, None)

    def get_active_emergencies(self, drone_id: str) -> set[EmergencyType]:
        """Return current active emergency types for a drone."""
        return set(self._active.get(drone_id, set()))
