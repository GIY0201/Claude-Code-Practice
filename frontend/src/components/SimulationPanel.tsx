import { useState, useEffect } from "react";
import { useSimulation } from "../hooks/useSimulation";
import { useMultiSimulation } from "../hooks/useMultiSimulation";
import { useDroneState } from "../hooks/useDroneState";
import type { Position3D, MultiDroneConfig, ScenarioInfo } from "../types";

/** 단일 드론 시나리오 (기존) */
const SINGLE_SCENARIOS: Record<
  string,
  { label: string; waypoints: Position3D[]; speed: number }
> = {
  hangang: {
    label: "한강 비행 (여의도 → 잠실)",
    waypoints: [
      { lat: 37.5249, lon: 126.9322, alt_m: 100 },
      { lat: 37.5197, lon: 126.9635, alt_m: 100 },
      { lat: 37.5169, lon: 126.9978, alt_m: 100 },
      { lat: 37.5171, lon: 127.0246, alt_m: 100 },
      { lat: 37.5145, lon: 127.0566, alt_m: 100 },
    ],
    speed: 30,
  },
  delivery: {
    label: "배송 (서울역 → 강남역)",
    waypoints: [
      { lat: 37.5547, lon: 126.9707, alt_m: 80 },
      { lat: 37.537, lon: 126.978, alt_m: 120 },
      { lat: 37.5172, lon: 126.995, alt_m: 120 },
      { lat: 37.4979, lon: 127.0276, alt_m: 80 },
    ],
    speed: 20,
  },
  short: {
    label: "단거리 테스트",
    waypoints: [
      { lat: 37.5665, lon: 126.978, alt_m: 100 },
      { lat: 37.563, lon: 126.985, alt_m: 120 },
      { lat: 37.56, lon: 126.99, alt_m: 100 },
    ],
    speed: 15,
  },
};

/** 다중 드론 시나리오 */
const MULTI_SCENARIOS: Record<
  string,
  { label: string; drones: MultiDroneConfig[] }
> = {
  head_on: {
    label: "정면 충돌 테스트 (2대)",
    drones: [
      {
        drone_id: "SKY-001",
        waypoints: [
          { lat: 37.5665, lon: 126.97, alt_m: 100 },
          { lat: 37.5665, lon: 126.99, alt_m: 100 },
        ],
        speed_ms: 15,
        priority: "NORMAL",
      },
      {
        drone_id: "SKY-002",
        waypoints: [
          { lat: 37.5665, lon: 126.99, alt_m: 100 },
          { lat: 37.5665, lon: 126.97, alt_m: 100 },
        ],
        speed_ms: 15,
        priority: "NORMAL",
      },
    ],
  },
  crossing: {
    label: "교차 비행 (3대)",
    drones: [
      {
        drone_id: "SKY-001",
        waypoints: [
          { lat: 37.56, lon: 126.97, alt_m: 100 },
          { lat: 37.57, lon: 126.99, alt_m: 100 },
        ],
        speed_ms: 12,
        priority: "NORMAL",
      },
      {
        drone_id: "SKY-002",
        waypoints: [
          { lat: 37.57, lon: 126.97, alt_m: 100 },
          { lat: 37.56, lon: 126.99, alt_m: 100 },
        ],
        speed_ms: 12,
        priority: "NORMAL",
      },
      {
        drone_id: "SKY-003",
        waypoints: [
          { lat: 37.565, lon: 126.965, alt_m: 100 },
          { lat: 37.565, lon: 126.995, alt_m: 100 },
        ],
        speed_ms: 12,
        priority: "HIGH",
      },
    ],
  },
  multi_delivery: {
    label: "다중 배송 (5대)",
    drones: [
      {
        drone_id: "DEL-001",
        waypoints: [
          { lat: 37.555, lon: 126.97, alt_m: 80 },
          { lat: 37.535, lon: 126.99, alt_m: 80 },
        ],
        speed_ms: 10,
        priority: "NORMAL",
      },
      {
        drone_id: "DEL-002",
        waypoints: [
          { lat: 37.55, lon: 126.975, alt_m: 100 },
          { lat: 37.57, lon: 126.985, alt_m: 100 },
        ],
        speed_ms: 12,
        priority: "NORMAL",
      },
      {
        drone_id: "DEL-003",
        waypoints: [
          { lat: 37.565, lon: 126.96, alt_m: 120 },
          { lat: 37.545, lon: 126.995, alt_m: 120 },
        ],
        speed_ms: 8,
        priority: "LOW",
      },
      {
        drone_id: "EMG-001",
        waypoints: [
          { lat: 37.56, lon: 126.985, alt_m: 60 },
          { lat: 37.54, lon: 126.97, alt_m: 60 },
        ],
        speed_ms: 20,
        priority: "EMERGENCY",
      },
      {
        drone_id: "DEL-004",
        waypoints: [
          { lat: 37.545, lon: 126.965, alt_m: 140 },
          { lat: 37.565, lon: 126.99, alt_m: 140 },
        ],
        speed_ms: 10,
        priority: "HIGH",
      },
    ],
  },
};

type SimMode = "single" | "multi" | "server";

function SimulationPanel() {
  const { startSimulation, stopSimulation } = useSimulation();
  const { startMultiSimulation, stopMultiSimulation } = useMultiSimulation();
  const simStatus = useDroneState((s) => s.simStatus);
  const drones = useDroneState((s) => s.drones);
  const activeCount = useDroneState((s) => s.activeCount);

  const [mode, setMode] = useState<SimMode>("multi");
  const [selectedSingle, setSelectedSingle] = useState("hangang");
  const [selectedMulti, setSelectedMulti] = useState("head_on");
  const [serverScenarios, setServerScenarios] = useState<ScenarioInfo[]>([]);
  const [selectedServer, setSelectedServer] = useState("");
  const [serverLoading, setServerLoading] = useState(false);

  const isRunning = simStatus === "running";

  // 서버 시나리오 목록 로드
  useEffect(() => {
    fetch("/api/scenarios/")
      .then((r) => r.json())
      .then((data: ScenarioInfo[]) => {
        setServerScenarios(data);
        if (data.length > 0 && !selectedServer) {
          setSelectedServer(data[0].name);
        }
      })
      .catch(() => {});
  }, []);

  const handleStart = async () => {
    if (mode === "single") {
      const s = SINGLE_SCENARIOS[selectedSingle];
      startSimulation("SKY-001", s.waypoints, s.speed);
    } else if (mode === "server") {
      // 서버 시나리오 로드 후 시작
      setServerLoading(true);
      try {
        const resp = await fetch(`/api/scenarios/${selectedServer}`);
        if (!resp.ok) throw new Error("Failed to load scenario");
        const data = await resp.json();
        const configs: MultiDroneConfig[] = data.drones.map(
          (d: { drone_id: string; waypoints: Position3D[]; speed_ms?: number; priority?: string }) => ({
            drone_id: d.drone_id,
            waypoints: d.waypoints,
            speed_ms: d.speed_ms ?? 10,
            priority: d.priority ?? "NORMAL",
          })
        );
        startMultiSimulation(configs);
      } catch (err) {
        console.error("Scenario load error:", err);
      } finally {
        setServerLoading(false);
      }
    } else {
      const s = MULTI_SCENARIOS[selectedMulti];
      startMultiSimulation(s.drones);
    }
  };

  const handleStop = () => {
    if (mode === "single") {
      stopSimulation();
    } else {
      stopMultiSimulation();
    }
  };

  const droneList = Array.from(drones.values());

  return (
    <div className="ui-overlay top-14 left-4 w-72 bg-gray-800/95 rounded-lg shadow-xl border border-gray-700 text-sm max-h-[calc(100vh-80px)] overflow-y-auto">
      {/* 헤더 */}
      <div className="px-4 py-3 border-b border-gray-700">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Simulation Control
        </h2>
      </div>

      <div className="px-4 py-3 space-y-3">
        {/* 모드 전환 */}
        <div className="flex gap-1 bg-gray-700 rounded p-0.5">
          <button
            className={`flex-1 py-1 text-xs rounded transition-colors ${
              mode === "single"
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => setMode("single")}
            disabled={isRunning}
          >
            Single
          </button>
          <button
            className={`flex-1 py-1 text-xs rounded transition-colors ${
              mode === "multi"
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => setMode("multi")}
            disabled={isRunning}
          >
            Multi
          </button>
          <button
            className={`flex-1 py-1 text-xs rounded transition-colors ${
              mode === "server"
                ? "bg-blue-600 text-white"
                : "text-gray-400 hover:text-white"
            }`}
            onClick={() => setMode("server")}
            disabled={isRunning}
          >
            Scenario
          </button>
        </div>

        {/* 시나리오 선택 */}
        <div>
          <label className="block text-xs text-gray-400 mb-1">Scenario</label>
          {mode === "server" ? (
            <select
              className="w-full bg-gray-700 text-white rounded px-2 py-1.5 text-xs border border-gray-600 focus:border-blue-500 focus:outline-none"
              value={selectedServer}
              onChange={(e) => setSelectedServer(e.target.value)}
              disabled={isRunning || serverLoading}
            >
              {serverScenarios.map((s) => (
                <option key={s.name} value={s.name}>
                  {s.description} ({s.drone_count} drones)
                </option>
              ))}
            </select>
          ) : (
            <select
              className="w-full bg-gray-700 text-white rounded px-2 py-1.5 text-xs border border-gray-600 focus:border-blue-500 focus:outline-none"
              value={mode === "single" ? selectedSingle : selectedMulti}
              onChange={(e) =>
                mode === "single"
                  ? setSelectedSingle(e.target.value)
                  : setSelectedMulti(e.target.value)
              }
              disabled={isRunning}
            >
              {Object.entries(
                mode === "single" ? SINGLE_SCENARIOS : MULTI_SCENARIOS
              ).map(([key, { label }]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          )}
        </div>

        {/* 시나리오 정보 */}
        {mode === "multi" && !isRunning && (
          <div className="text-xs text-gray-500">
            {MULTI_SCENARIOS[selectedMulti].drones.length} drones configured
          </div>
        )}
        {mode === "server" && !isRunning && selectedServer && (
          <div className="text-xs text-gray-500">
            {serverScenarios.find((s) => s.name === selectedServer)?.drone_count ?? 0} drones configured
          </div>
        )}

        {/* 시작/중지 */}
        <button
          className={`w-full py-2 rounded font-medium text-xs uppercase tracking-wider transition-colors ${
            isRunning
              ? "bg-red-600 hover:bg-red-700 text-white"
              : "bg-blue-600 hover:bg-blue-700 text-white"
          }`}
          onClick={isRunning ? handleStop : handleStart}
        >
          {isRunning ? "Stop Simulation" : "Start Simulation"}
        </button>

        {/* 상태 */}
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full ${
                simStatus === "running"
                  ? "bg-green-400 animate-pulse"
                  : simStatus === "completed"
                    ? "bg-blue-400"
                    : simStatus === "error"
                      ? "bg-red-400"
                      : "bg-gray-500"
              }`}
            />
            <span className="text-gray-400">
              {simStatus === "running"
                ? "Simulating..."
                : simStatus === "completed"
                  ? "Flight completed"
                  : simStatus === "error"
                    ? "Error"
                    : "Ready"}
            </span>
          </div>
          {isRunning && mode === "multi" && (
            <span className="text-gray-500">
              {activeCount}/{drones.size} active
            </span>
          )}
        </div>
      </div>

      {/* 드론 목록 (간략) */}
      {droneList.length > 0 && (
        <div className="border-t border-gray-700">
          <div className="px-4 py-2">
            <h3 className="text-xs font-semibold text-gray-400 uppercase">
              Drones ({droneList.length})
            </h3>
          </div>
          {droneList.map((d) => (
            <div
              key={d.drone_id}
              className="px-4 py-1.5 flex items-center justify-between hover:bg-gray-700/50"
            >
              <div className="flex items-center gap-2">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    d.status === "AIRBORNE"
                      ? "bg-blue-400"
                      : d.status === "EMERGENCY"
                        ? "bg-red-400"
                        : d.status === "LANDED"
                          ? "bg-green-400"
                          : "bg-gray-400"
                  }`}
                />
                <span className="text-gray-300 text-xs font-mono">
                  {d.callsign}
                </span>
              </div>
              <BatteryMini percent={d.battery_percent} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function BatteryMini({ percent }: { percent: number }) {
  const color =
    percent > 50
      ? "text-green-400"
      : percent > 20
        ? "text-yellow-400"
        : "text-red-400";
  return (
    <span className={`text-xs font-mono ${color}`}>{Math.round(percent)}%</span>
  );
}

export default SimulationPanel;
