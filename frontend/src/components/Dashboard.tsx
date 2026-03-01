import { useDroneState } from "../hooks/useDroneState";
import type { Drone, ConflictInfo, AvoidanceCommand } from "../types";
import WeatherPanel from "./WeatherPanel";
import EmergencyAlertPanel from "./EmergencyAlertPanel";
import MetricsPanel from "./MetricsPanel";

function Dashboard() {
  const drones = useDroneState((s) => s.drones);
  const conflicts = useDroneState((s) => s.conflicts);
  const commands = useDroneState((s) => s.avoidanceCommands);
  const simStatus = useDroneState((s) => s.simStatus);

  const droneList = Array.from(drones.values());

  if (simStatus === "idle" && droneList.length === 0) {
    return null;
  }

  return (
    <div className="absolute top-14 right-4 w-80 max-h-[calc(100vh-80px)] bg-gray-800/95 rounded-lg shadow-xl border border-gray-700 text-sm overflow-y-auto">
      {/* 기상 정보 */}
      <WeatherPanel />

      {/* 충돌 경고 */}
      {conflicts.length > 0 && (
        <ConflictPanel conflicts={conflicts} commands={commands} />
      )}

      {/* 비상 알림 */}
      <EmergencyAlertPanel />

      {/* 성능 메트릭 */}
      <MetricsPanel />

      {/* 드론 상세 목록 */}
      <div className="px-4 py-3 border-b border-gray-700">
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Drone Status ({droneList.length})
        </h2>
      </div>
      {droneList.map((d) => (
        <DroneCard
          key={d.drone_id}
          drone={d}
          hasConflict={isInConflict(d.drone_id, conflicts)}
        />
      ))}
    </div>
  );
}

function ConflictPanel({
  conflicts,
  commands,
}: {
  conflicts: ConflictInfo[];
  commands: AvoidanceCommand[];
}) {
  return (
    <div className="border-b border-red-800">
      <div className="px-4 py-2 bg-red-900/50 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />
        <h2 className="text-xs font-semibold text-red-300 uppercase tracking-wider">
          Conflict Alert ({conflicts.length})
        </h2>
      </div>
      {conflicts.map((c, i) => (
        <div
          key={i}
          className="px-4 py-2 border-t border-gray-700/50 bg-red-900/20"
        >
          <div className="flex justify-between text-xs">
            <span className="text-red-300 font-mono">
              {c.drone_a} - {c.drone_b}
            </span>
            <span className="text-red-400">{c.d_cpa_m.toFixed(0)}m</span>
          </div>
          <div className="flex gap-3 text-xs text-gray-500 mt-0.5">
            <span>T-CPA: {c.t_cpa_sec.toFixed(1)}s</span>
            <span>H: {c.horizontal_sep_m.toFixed(0)}m</span>
            <span>V: {c.vertical_sep_m.toFixed(0)}m</span>
          </div>
        </div>
      ))}
      {commands.length > 0 && (
        <div className="px-4 py-2 bg-yellow-900/20 border-t border-gray-700/50">
          <div className="text-xs text-yellow-400 font-semibold mb-1">
            Avoidance Commands
          </div>
          {commands.map((cmd, i) => (
            <div
              key={i}
              className="text-xs text-yellow-300/80 flex gap-2 py-0.5"
            >
              <span className="font-mono text-yellow-400">{cmd.drone_id}</span>
              <span className="text-gray-500">
                {maneuverLabel(cmd.maneuver_type)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DroneCard({
  drone,
  hasConflict,
}: {
  drone: Drone;
  hasConflict: boolean;
}) {
  const speed = Math.sqrt(
    drone.velocity.vx ** 2 + drone.velocity.vy ** 2 + drone.velocity.vz ** 2
  );

  return (
    <div
      className={`px-4 py-2.5 border-t border-gray-700/50 ${
        hasConflict ? "bg-red-900/10" : ""
      }`}
    >
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full ${
              drone.status === "AIRBORNE"
                ? "bg-blue-400"
                : drone.status === "EMERGENCY"
                  ? "bg-red-400 animate-pulse"
                  : drone.status === "LANDED"
                    ? "bg-green-400"
                    : drone.status === "HOLDING"
                      ? "bg-orange-400"
                      : "bg-gray-400"
            }`}
          />
          <span className="text-gray-200 font-mono text-xs font-medium">
            {drone.callsign}
          </span>
          {hasConflict && (
            <span className="text-red-400 text-xs">CONFLICT</span>
          )}
        </div>
        <span className="text-gray-500 text-xs">{drone.status}</span>
      </div>

      {/* 정보 그리드 */}
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-xs">
        <InfoRow label="Lat" value={drone.position.lat.toFixed(4)} />
        <InfoRow label="Lon" value={drone.position.lon.toFixed(4)} />
        <InfoRow label="Alt" value={`${drone.position.alt_m.toFixed(1)}m`} />
        <InfoRow label="Hdg" value={`${drone.heading.toFixed(0)}°`} />
        <InfoRow label="Speed" value={`${speed.toFixed(1)} m/s`} />
        <InfoRow label="Vz" value={`${drone.velocity.vz.toFixed(1)} m/s`} />
      </div>

      {/* 배터리 바 */}
      <BatteryBar percent={drone.battery_percent} />
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-300 font-mono">{value}</span>
    </div>
  );
}

function BatteryBar({ percent }: { percent: number }) {
  const color =
    percent > 50
      ? "bg-green-500"
      : percent > 20
        ? "bg-yellow-500"
        : "bg-red-500";
  return (
    <div className="flex items-center gap-2 mt-1.5">
      <span className="text-gray-500 text-xs w-8">BAT</span>
      <div className="flex-1 bg-gray-600 rounded-full h-1">
        <div
          className={`h-1 rounded-full ${color} transition-all`}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-gray-300 font-mono text-xs w-8 text-right">
        {Math.round(percent)}%
      </span>
    </div>
  );
}

function isInConflict(droneId: string, conflicts: ConflictInfo[]): boolean {
  return conflicts.some(
    (c) => c.drone_a === droneId || c.drone_b === droneId
  );
}

function maneuverLabel(type: string): string {
  switch (type) {
    case "SPEED_CHANGE":
      return "Decelerating";
    case "ALTITUDE_CHANGE":
      return "Altitude change";
    case "LATERAL_OFFSET":
      return "Course deviation";
    case "HOLD":
      return "Holding position";
    default:
      return type;
  }
}

export default Dashboard;
