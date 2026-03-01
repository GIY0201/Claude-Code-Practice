"""다중 드론 동시 시뮬레이터.

N대 드론을 독립적으로 시뮬레이션하고, 매 틱마다 전체 텔레메트리를 반환한다.
DAA(Detect and Avoid) 엔진과 통합하여 충돌 회피를 수행한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from models.common import Position3D, Priority
from models.telemetry import Telemetry
from simulator.drone_sim import DroneSim
from core.deconfliction.avoidance import DroneState, AvoidanceCommand, ManeuverType
from core.deconfliction.tactical import TacticalDAA, ConflictRecord


@dataclass
class DroneConfig:
    """드론 시뮬레이션 설정."""
    drone_id: str
    waypoints: list[Position3D]
    speed_ms: float = 10.0
    battery_percent: float = 100.0
    priority: Priority = Priority.NORMAL


@dataclass
class TickResult:
    """tick_with_daa()의 반환 결과."""
    telemetry: list[Telemetry]
    conflicts: list[ConflictRecord]
    commands: list[AvoidanceCommand]


@dataclass
class MultiDroneSim:
    """다중 드론 동시 시뮬레이터.

    각 드론은 독립 DroneSim 인스턴스로 관리된다.
    tick() 호출 시 전체 드론을 한 프레임 진행하고 텔레메트리 목록을 반환한다.
    """

    _sims: dict[str, DroneSim] = field(default_factory=dict, init=False)
    _priorities: dict[str, Priority] = field(default_factory=dict, init=False)
    _daa: TacticalDAA = field(default_factory=TacticalDAA, init=False)
    _tick_count: int = field(default=0, init=False)

    def add_drone(self, config: DroneConfig) -> None:
        """드론을 시뮬레이션에 추가한다.

        Args:
            config: 드론 설정 (ID, 경유점, 속도, 배터리).

        Raises:
            ValueError: 동일 ID의 드론이 이미 존재할 때.
        """
        if config.drone_id in self._sims:
            raise ValueError(f"Drone {config.drone_id} already exists")
        self._sims[config.drone_id] = DroneSim(
            drone_id=config.drone_id,
            waypoints=config.waypoints,
            speed_ms=config.speed_ms,
            battery_percent=config.battery_percent,
        )
        self._priorities[config.drone_id] = config.priority

    def remove_drone(self, drone_id: str) -> bool:
        """드론을 시뮬레이션에서 제거한다."""
        self._priorities.pop(drone_id, None)
        return self._sims.pop(drone_id, None) is not None

    def tick(self, dt_sec: float = 0.1) -> list[Telemetry]:
        """전체 드론을 한 프레임 진행하고 텔레메트리 목록을 반환한다."""
        self._tick_count += 1
        return [sim.tick(dt_sec) for sim in self._sims.values()]

    @property
    def all_completed(self) -> bool:
        """모든 드론이 비행을 완료했는지 확인한다."""
        if not self._sims:
            return True
        return all(sim.completed for sim in self._sims.values())

    @property
    def active_count(self) -> int:
        """현재 비행 중인 드론 수."""
        return sum(1 for sim in self._sims.values() if not sim.completed)

    @property
    def drone_count(self) -> int:
        """등록된 전체 드론 수."""
        return len(self._sims)

    def get_sim(self, drone_id: str) -> DroneSim | None:
        """특정 드론의 DroneSim 인스턴스를 반환한다."""
        return self._sims.get(drone_id)

    def get_positions(self) -> dict[str, Position3D]:
        """전체 드론의 현재 위치를 반환한다."""
        return {
            drone_id: sim.position
            for drone_id, sim in self._sims.items()
        }

    def get_active_telemetry(self) -> list[Telemetry]:
        """비행 중인 드론의 마지막 텔레메트리만 반환한다 (tick 호출 없이)."""
        return [
            sim._build_telemetry(sim._check_alerts())
            for sim in self._sims.values()
            if not sim.completed
        ]

    def tick_with_daa(self, dt_sec: float = 0.1) -> TickResult:
        """전체 드론을 진행하고, DAA 검사를 수행하여 결과를 반환한다.

        Returns:
            TickResult: 텔레메트리, 충돌 기록, 회피 명령.
        """
        telemetry = self.tick(dt_sec)

        # 활성 드론 상태만 DAA에 전달
        states = self._build_drone_states()
        if len(states) < 2:
            return TickResult(telemetry=telemetry, conflicts=[], commands=[])

        commands = self._daa.evaluate(states)
        conflicts = self._daa.active_conflicts

        # 회피 명령 적용
        for cmd in commands:
            self._apply_avoidance(cmd)

        return TickResult(
            telemetry=telemetry,
            conflicts=conflicts,
            commands=commands,
        )

    def _build_drone_states(self) -> dict[str, DroneState]:
        """활성 드론의 DroneState 딕셔너리를 생성한다."""
        states: dict[str, DroneState] = {}
        for drone_id, sim in self._sims.items():
            if sim.completed:
                continue
            states[drone_id] = DroneState(
                drone_id=drone_id,
                position=sim.position,
                velocity=sim._velocity,
                speed_ms=sim.speed_ms,
                heading=sim._heading,
                priority=self._priorities.get(drone_id, Priority.NORMAL),
            )
        return states

    def _apply_avoidance(self, cmd: AvoidanceCommand) -> None:
        """회피 명령을 해당 드론에 적용한다."""
        sim = self._sims.get(cmd.drone_id)
        if sim is None or sim.completed:
            return

        if cmd.maneuver_type == ManeuverType.SPEED_CHANGE:
            if cmd.target_speed_ms is not None:
                sim.speed_ms = cmd.target_speed_ms

        elif cmd.maneuver_type == ManeuverType.ALTITUDE_CHANGE:
            if cmd.target_alt_m is not None:
                sim._position = Position3D(
                    lat=sim._position.lat,
                    lon=sim._position.lon,
                    alt_m=cmd.target_alt_m,
                )

        elif cmd.maneuver_type == ManeuverType.HOLD:
            sim.speed_ms = 0.0

        elif cmd.maneuver_type == ManeuverType.LATERAL_OFFSET:
            if cmd.heading_offset_deg is not None:
                import math
                offset_rad = math.radians(cmd.heading_offset_deg)
                # 현재 위치에서 오른쪽으로 50m 오프셋
                heading_rad = math.radians(sim._heading + 90)
                offset_m = 50.0
                dlat = (offset_m * math.cos(heading_rad)) / 111_320.0
                dlon = (offset_m * math.sin(heading_rad)) / (
                    111_320.0 * math.cos(math.radians(sim._position.lat))
                )
                sim._position = Position3D(
                    lat=sim._position.lat + dlat,
                    lon=sim._position.lon + dlon,
                    alt_m=sim._position.alt_m,
                )
