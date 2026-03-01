import { useDroneState } from "../hooks/useDroneState";

function MetricsPanel() {
  const metrics = useDroneState((s) => s.metrics);
  const simStatus = useDroneState((s) => s.simStatus);

  if (!metrics || simStatus === "idle") return null;

  return (
    <div className="border-b border-gray-700">
      <div className="px-4 py-2.5 bg-indigo-900/30 flex items-center gap-2 border-b border-gray-700">
        <span className="w-2 h-2 rounded-full bg-indigo-400" />
        <h2 className="text-xs font-semibold text-indigo-300 uppercase tracking-wider">
          Performance Metrics
        </h2>
      </div>

      <div className="px-4 py-3 space-y-2.5">
        {/* 주요 지표 */}
        <MetricBar
          label="Collision Avoidance"
          value={metrics.collision_avoidance_rate}
          format="percent"
          color="green"
        />
        <MetricBar
          label="Route Efficiency"
          value={metrics.route_efficiency}
          format="percent"
          color="blue"
        />
        <MetricBar
          label="Mission Complete"
          value={metrics.mission_completion_rate}
          format="percent"
          color="cyan"
        />

        {/* 수치 지표 */}
        <div className="grid grid-cols-2 gap-x-3 gap-y-1.5 pt-1">
          <MetricValue
            label="Avg Response"
            value={`${metrics.avg_response_time_ms.toFixed(0)}ms`}
          />
          <MetricValue
            label="Energy Eff."
            value={`${metrics.energy_efficiency.toFixed(1)} m/%`}
          />
          <MetricValue
            label="Avg Flight"
            value={`${metrics.avg_flight_time_sec.toFixed(1)}s`}
          />
          <MetricValue
            label="Total Dist."
            value={formatDistance(metrics.total_distance_m)}
          />
        </div>

        {/* 충돌/회피 통계 */}
        <div className="flex gap-3 pt-1 border-t border-gray-700/50">
          <div className="flex-1 text-center">
            <div className="text-lg font-bold text-yellow-400 font-mono">
              {metrics.total_conflicts_detected}
            </div>
            <div className="text-[10px] text-gray-500 uppercase">Conflicts</div>
          </div>
          <div className="flex-1 text-center">
            <div className="text-lg font-bold text-green-400 font-mono">
              {metrics.total_avoidance_maneuvers}
            </div>
            <div className="text-[10px] text-gray-500 uppercase">Avoidance</div>
          </div>
          <div className="flex-1 text-center">
            <div className="text-lg font-bold text-blue-400 font-mono">
              {Object.keys(metrics.drone_metrics).length}
            </div>
            <div className="text-[10px] text-gray-500 uppercase">Drones</div>
          </div>
        </div>
      </div>
    </div>
  );
}

/** 퍼센트 바 */
function MetricBar({
  label,
  value,
  format,
  color,
}: {
  label: string;
  value: number;
  format: "percent";
  color: "green" | "blue" | "cyan";
}) {
  const pct = Math.round(value * 100);
  const barColor =
    color === "green"
      ? "bg-green-500"
      : color === "blue"
        ? "bg-blue-500"
        : "bg-cyan-500";
  const textColor =
    color === "green"
      ? "text-green-400"
      : color === "blue"
        ? "text-blue-400"
        : "text-cyan-400";

  return (
    <div>
      <div className="flex justify-between text-xs mb-0.5">
        <span className="text-gray-400">{label}</span>
        <span className={`font-mono font-medium ${textColor}`}>
          {format === "percent" ? `${pct}%` : value}
        </span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full ${barColor} transition-all`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

/** 수치 표시 */
function MetricValue({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-300 font-mono">{value}</span>
    </div>
  );
}

/** 거리 포맷 (m → km) */
function formatDistance(meters: number): string {
  if (meters >= 1000) {
    return `${(meters / 1000).toFixed(1)} km`;
  }
  return `${Math.round(meters)} m`;
}

export default MetricsPanel;
