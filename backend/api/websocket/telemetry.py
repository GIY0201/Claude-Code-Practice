"""드론 텔레메트리 WebSocket 엔드포인트.

클라이언트는 JSON 명령으로 시뮬레이션을 제어하고,
서버는 매 틱마다 텔레메트리 JSON을 스트리밍한다.

=== 단일 드론 모드 (/ws/telemetry) ===
Commands (client → server):
    {"action": "start", "drone_id": "D1", "waypoints": [{"lat":..., "lon":..., "alt_m":...}, ...], "speed_ms": 10}
    {"action": "stop"}

Events (server → client):
    {"event": "telemetry", "data": {...Telemetry JSON...}}
    {"event": "completed", "drone_id": "D1"}
    {"event": "error", "message": "..."}

=== 다중 드론 모드 (/ws/multi-telemetry) ===
Commands (client → server):
    {"action": "start", "drones": [{"drone_id": "D1", "waypoints": [...], "speed_ms": 10, "priority": "NORMAL"}, ...]}
    {"action": "stop"}

Events (server → client):
    {"event": "telemetry", "drones": [{...Telemetry JSON...}, ...]}
    {"event": "conflict", "conflicts": [...], "commands": [...]}
    {"event": "completed"}
    {"event": "error", "message": "..."}
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import settings
from models.common import Position3D, Priority
from simulator.drone_sim import DroneSim
from simulator.multi_drone import MultiDroneSim, DroneConfig
from core.weather.fetcher import WeatherFetcher
from core.emergency.detector import EmergencyDetector
from core.metrics.collector import MetricsCollector
from api.routes.metrics import set_latest_metrics

logger = logging.getLogger(__name__)

_weather_fetcher = WeatherFetcher()
_WEATHER_BROADCAST_INTERVAL_SEC = 10.0

router = APIRouter()


# ──────────── 단일 드론 WebSocket ────────────

@router.websocket("/ws/telemetry")
async def telemetry_endpoint(websocket: WebSocket) -> None:
    """단일 드론 텔레메트리 실시간 스트리밍."""
    await websocket.accept()
    sim_task: asyncio.Task | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"event": "error", "message": "Invalid JSON"})
                continue

            action = msg.get("action")

            if action == "start":
                if sim_task and not sim_task.done():
                    sim_task.cancel()
                    try:
                        await sim_task
                    except asyncio.CancelledError:
                        pass

                try:
                    sim = _parse_sim_params(msg)
                except (KeyError, ValueError) as e:
                    await websocket.send_json({"event": "error", "message": str(e)})
                    continue

                sim_task = asyncio.create_task(
                    _run_simulation(websocket, sim)
                )

            elif action == "stop":
                if sim_task and not sim_task.done():
                    sim_task.cancel()
                    try:
                        await sim_task
                    except asyncio.CancelledError:
                        pass
                    sim_task = None
                await websocket.send_json({"event": "stopped"})

            else:
                await websocket.send_json({"event": "error", "message": f"Unknown action: {action}"})

    except WebSocketDisconnect:
        pass
    finally:
        if sim_task and not sim_task.done():
            sim_task.cancel()
            try:
                await sim_task
            except asyncio.CancelledError:
                pass


# ──────────── 다중 드론 WebSocket ────────────

@router.websocket("/ws/multi-telemetry")
async def multi_telemetry_endpoint(websocket: WebSocket) -> None:
    """다중 드론 텔레메트리 + DAA 실시간 스트리밍."""
    await websocket.accept()
    sim_task: asyncio.Task | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"event": "error", "message": "Invalid JSON"})
                continue

            action = msg.get("action")

            if action == "start":
                if sim_task and not sim_task.done():
                    sim_task.cancel()
                    try:
                        await sim_task
                    except asyncio.CancelledError:
                        pass

                try:
                    multi_sim = _parse_multi_sim_params(msg)
                except (KeyError, ValueError) as e:
                    await websocket.send_json({"event": "error", "message": str(e)})
                    continue

                sim_task = asyncio.create_task(
                    _run_multi_simulation(websocket, multi_sim)
                )

            elif action == "stop":
                if sim_task and not sim_task.done():
                    sim_task.cancel()
                    try:
                        await sim_task
                    except asyncio.CancelledError:
                        pass
                    sim_task = None
                await websocket.send_json({"event": "stopped"})

            else:
                await websocket.send_json({"event": "error", "message": f"Unknown action: {action}"})

    except WebSocketDisconnect:
        pass
    finally:
        if sim_task and not sim_task.done():
            sim_task.cancel()
            try:
                await sim_task
            except asyncio.CancelledError:
                pass


# ──────────── 파싱 헬퍼 ────────────

def _parse_sim_params(msg: dict) -> DroneSim:
    """클라이언트 메시지에서 DroneSim 인스턴스를 생성한다."""
    drone_id = msg.get("drone_id", "SIM-001")
    raw_wps = msg.get("waypoints")
    if not raw_wps or len(raw_wps) < 2:
        raise ValueError("waypoints must have at least 2 points")

    waypoints = [
        Position3D(lat=wp["lat"], lon=wp["lon"], alt_m=wp.get("alt_m", 100.0))
        for wp in raw_wps
    ]
    speed_ms = float(msg.get("speed_ms", 10.0))

    return DroneSim(
        drone_id=drone_id,
        waypoints=waypoints,
        speed_ms=speed_ms,
    )


def _parse_multi_sim_params(msg: dict) -> MultiDroneSim:
    """클라이언트 메시지에서 MultiDroneSim 인스턴스를 생성한다."""
    raw_drones = msg.get("drones")
    if not raw_drones or len(raw_drones) < 1:
        raise ValueError("drones must have at least 1 entry")

    multi_sim = MultiDroneSim()
    for d in raw_drones:
        drone_id = d.get("drone_id")
        if not drone_id:
            raise ValueError("Each drone must have a drone_id")

        raw_wps = d.get("waypoints")
        if not raw_wps or len(raw_wps) < 2:
            raise ValueError(f"Drone {drone_id}: waypoints must have at least 2 points")

        waypoints = [
            Position3D(lat=wp["lat"], lon=wp["lon"], alt_m=wp.get("alt_m", 100.0))
            for wp in raw_wps
        ]
        speed_ms = float(d.get("speed_ms", 10.0))
        priority_str = d.get("priority", "NORMAL")
        try:
            priority = Priority(priority_str)
        except ValueError:
            priority = Priority.NORMAL

        multi_sim.add_drone(DroneConfig(
            drone_id=drone_id,
            waypoints=waypoints,
            speed_ms=speed_ms,
            priority=priority,
        ))

    return multi_sim


# ──────────── 시뮬레이션 루프 ────────────

async def _run_simulation(websocket: WebSocket, sim: DroneSim) -> None:
    """단일 드론 시뮬레이션 루프."""
    tick_hz = settings.SIM_TICK_RATE_HZ
    dt_sec = 1.0 / tick_hz
    sleep_sec = dt_sec

    try:
        while not sim.completed:
            telem = sim.tick(dt_sec=dt_sec)
            payload = telem.model_dump(mode="json")
            await websocket.send_json({"event": "telemetry", "data": payload})
            await asyncio.sleep(sleep_sec)

        await websocket.send_json({"event": "completed", "drone_id": sim.drone_id})

    except asyncio.CancelledError:
        logger.info("Simulation cancelled for drone %s", sim.drone_id)
        raise


async def _run_multi_simulation(websocket: WebSocket, sim: MultiDroneSim) -> None:
    """다중 드론 시뮬레이션 루프 (DAA + 기상 + 비상 + 메트릭 통합)."""
    tick_hz = settings.SIM_TICK_RATE_HZ
    dt_sec = 1.0 / tick_hz
    sleep_sec = dt_sec
    elapsed_since_weather = 0.0

    emergency_detector = EmergencyDetector()
    metrics_collector = MetricsCollector()

    try:
        while not sim.all_completed:
            result = sim.tick_with_daa(dt_sec=dt_sec)

            # 텔레메트리 전송
            telem_payload = [t.model_dump(mode="json") for t in result.telemetry]
            await websocket.send_json({
                "event": "telemetry",
                "drones": telem_payload,
                "active_count": sim.active_count,
            })

            # 메트릭 기록
            metrics_collector.record_tick(
                telemetry_list=result.telemetry,
                conflict_count=len(result.conflicts),
                avoidance_count=len(result.commands),
            )

            # 완료된 드론 기록
            for telem in result.telemetry:
                drone_sim = sim._sims.get(telem.drone_id)
                if drone_sim and drone_sim.completed:
                    metrics_collector.record_completion(telem.drone_id)

            # 충돌 경고 전송
            if result.conflicts:
                conflict_payload = []
                for cr in result.conflicts:
                    conflict_payload.append({
                        "drone_a": cr.cpa.drone_id_a,
                        "drone_b": cr.cpa.drone_id_b,
                        "t_cpa_sec": cr.cpa.t_cpa_sec,
                        "d_cpa_m": cr.cpa.d_cpa_m,
                        "horizontal_sep_m": cr.cpa.horizontal_sep_m,
                        "vertical_sep_m": cr.cpa.vertical_sep_m,
                    })
                cmd_payload = []
                for cmd in result.commands:
                    cmd_payload.append({
                        "drone_id": cmd.drone_id,
                        "maneuver_type": cmd.maneuver_type.value,
                        "target_speed_ms": cmd.target_speed_ms,
                        "target_alt_m": cmd.target_alt_m,
                        "heading_offset_deg": cmd.heading_offset_deg,
                        "reason": cmd.reason,
                    })
                await websocket.send_json({
                    "event": "conflict",
                    "conflicts": conflict_payload,
                    "commands": cmd_payload,
                })

            # 비상 감지 — 각 드론 텔레메트리 분석
            for telem in result.telemetry:
                alerts = emergency_detector.update(telem)
                if alerts:
                    alert_payload = []
                    for a in alerts:
                        alert_payload.append({
                            "level": a.severity.value,
                            "type": a.emergency_type.value,
                            "message": a.message,
                        })
                    await websocket.send_json({
                        "event": "emergency",
                        "drone_id": telem.drone_id,
                        "alerts": alert_payload,
                    })

            # 기상 정보 주기적 전송
            elapsed_since_weather += dt_sec
            if elapsed_since_weather >= _WEATHER_BROADCAST_INTERVAL_SEC:
                elapsed_since_weather = 0.0
                try:
                    weather = _weather_fetcher.get_weather(37.5665, 126.978)
                    if weather:
                        await websocket.send_json({
                            "event": "weather",
                            "data": {
                                "wind_speed_ms": weather.wind_speed_ms,
                                "wind_deg": weather.wind_deg,
                                "rain_1h_mm": weather.rain_1h_mm,
                                "snow_1h_mm": weather.snow_1h_mm,
                                "description": weather.description,
                                "timestamp": weather.timestamp,
                            },
                        })
                except Exception as e:
                    logger.debug("Weather fetch failed: %s", e)

            await asyncio.sleep(sleep_sec)

        # 메트릭 요약 생성 및 전송
        summary = metrics_collector.get_summary()
        set_latest_metrics(summary)
        await websocket.send_json({
            "event": "metrics",
            "data": summary.model_dump(mode="json"),
        })

        await websocket.send_json({"event": "completed"})

    except asyncio.CancelledError:
        logger.info("Multi-drone simulation cancelled")
        raise
