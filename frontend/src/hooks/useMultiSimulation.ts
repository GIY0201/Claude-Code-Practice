import { useCallback, useRef } from "react";
import type { MultiDroneConfig } from "../types";
import { useDroneState } from "./useDroneState";

export function useMultiSimulation() {
  const wsRef = useRef<WebSocket | null>(null);
  const {
    updateTelemetry,
    setSimStatus,
    setPlannedRoutes,
    setConflicts,
    setActiveCount,
    setWeather,
    addEmergencyAlert,
    setMetrics,
    clearAll,
  } = useDroneState();

  const startMultiSimulation = useCallback(
    (configs: MultiDroneConfig[]) => {
      if (wsRef.current) {
        wsRef.current.close();
      }

      clearAll();
      setSimStatus("running");

      // 계획 경로 저장
      const routes = new Map<string, typeof configs[0]["waypoints"]>();
      for (const c of configs) {
        routes.set(c.drone_id, c.waypoints);
      }
      setPlannedRoutes(routes);

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(
        `${protocol}//${window.location.host}/ws/multi-telemetry`
      );
      wsRef.current = ws;

      ws.onopen = () => {
        ws.send(
          JSON.stringify({
            action: "start",
            drones: configs.map((c) => ({
              drone_id: c.drone_id,
              waypoints: c.waypoints.map((wp) => ({
                lat: wp.lat,
                lon: wp.lon,
                alt_m: wp.alt_m,
              })),
              speed_ms: c.speed_ms,
              priority: c.priority,
            })),
          })
        );
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        if (msg.event === "telemetry") {
          // 다중 드론 텔레메트리
          for (const t of msg.drones) {
            updateTelemetry(t);
          }
          if (msg.active_count !== undefined) {
            setActiveCount(msg.active_count);
          }
        } else if (msg.event === "conflict") {
          setConflicts(msg.conflicts ?? [], msg.commands ?? []);
        } else if (msg.event === "weather") {
          setWeather(msg.data);
        } else if (msg.event === "emergency") {
          for (const alert of msg.alerts ?? []) {
            addEmergencyAlert({
              ...alert,
              drone_id: msg.drone_id ?? alert.drone_id,
              timestamp: Date.now(),
            });
          }
        } else if (msg.event === "metrics") {
          setMetrics(msg.data);
        } else if (msg.event === "completed") {
          setSimStatus("completed");
        } else if (msg.event === "error") {
          console.error("Multi-simulation error:", msg.message);
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
    [
      updateTelemetry,
      setSimStatus,
      setPlannedRoutes,
      setConflicts,
      setActiveCount,
      setWeather,
      addEmergencyAlert,
      setMetrics,
      clearAll,
    ]
  );

  const stopMultiSimulation = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "stop" }));
    }
    wsRef.current?.close();
    wsRef.current = null;
    setSimStatus("idle");
  }, [setSimStatus]);

  return { startMultiSimulation, stopMultiSimulation };
}
