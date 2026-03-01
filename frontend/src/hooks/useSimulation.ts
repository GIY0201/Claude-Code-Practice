import { useCallback, useRef } from "react";
import type { Position3D } from "../types";
import { useDroneState } from "./useDroneState";

/**
 * WebSocket 기반 시뮬레이션 제어 훅.
 *
 * startSimulation()으로 백엔드에 시뮬레이션 시작 명령을 보내고,
 * 수신되는 텔레메트리를 Zustand 스토어에 반영한다.
 */
export function useSimulation() {
  const wsRef = useRef<WebSocket | null>(null);
  const { updateTelemetry, setSimStatus, setPlannedWaypoints, clearTrails } =
    useDroneState();

  const startSimulation = useCallback(
    (droneId: string, waypoints: Position3D[], speedMs: number = 10) => {
      // 기존 연결 정리
      if (wsRef.current) {
        wsRef.current.close();
      }

      clearTrails();
      setPlannedWaypoints(waypoints);
      setSimStatus("running");

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/telemetry`);
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            action: "start",
            drone_id: droneId,
            waypoints: waypoints.map((wp) => ({
              lat: wp.lat,
              lon: wp.lon,
              alt_m: wp.alt_m,
            })),
            speed_ms: speedMs,
          })
        );
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        if (msg.event === "telemetry") {
          updateTelemetry(msg.data);
        } else if (msg.event === "completed") {
          setSimStatus("completed");
        } else if (msg.event === "error") {
          console.error("Simulation error:", msg.message);
          setSimStatus("error");
        }
      };

      ws.onerror = () => {
        setSimStatus("error");
      };

      ws.onclose = () => {
        wsRef.current = null;
      };
    },
    [updateTelemetry, setSimStatus, setPlannedWaypoints, clearTrails]
  );

  const stopSimulation = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "stop" }));
    }
    wsRef.current?.close();
    wsRef.current = null;
    setSimStatus("idle");
  }, [setSimStatus]);

  return { startSimulation, stopSimulation };
}
