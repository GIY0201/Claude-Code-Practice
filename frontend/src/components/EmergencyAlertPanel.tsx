import { useDroneState } from "../hooks/useDroneState";
import type { EmergencyAlert } from "../types";

function EmergencyAlertPanel() {
  const alerts = useDroneState((s) => s.emergencyAlerts);

  if (alerts.length === 0) return null;

  return (
    <div className="border-b border-orange-800">
      <div className="px-4 py-2 bg-orange-900/40 flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
        <h2 className="text-xs font-semibold text-orange-300 uppercase tracking-wider">
          Emergency Alerts ({alerts.length})
        </h2>
      </div>
      <div className="max-h-48 overflow-y-auto">
        {alerts.map((alert, i) => (
          <AlertRow key={`${alert.drone_id}-${alert.timestamp}-${i}`} alert={alert} />
        ))}
      </div>
    </div>
  );
}

function AlertRow({ alert }: { alert: EmergencyAlert }) {
  const levelColor =
    alert.level === "CRITICAL"
      ? "text-red-400 bg-red-900/20"
      : "text-yellow-400 bg-yellow-900/20";

  const levelBadge =
    alert.level === "CRITICAL"
      ? "bg-red-600 text-white"
      : "bg-yellow-600 text-white";

  const timeStr = new Date(alert.timestamp).toLocaleTimeString("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <div className={`px-4 py-2 border-t border-gray-700/50 ${levelColor}`}>
      <div className="flex items-center justify-between mb-0.5">
        <div className="flex items-center gap-2">
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${levelBadge}`}>
            {alert.level}
          </span>
          <span className="font-mono text-xs">{alert.drone_id}</span>
        </div>
        <span className="text-gray-500 text-[10px]">{timeStr}</span>
      </div>
      <div className="text-xs text-gray-400 mt-0.5">{alert.type}</div>
      <div className="text-xs text-gray-300">{alert.message}</div>
      {alert.landing_zone && (
        <div className="text-[10px] text-green-400 mt-1">
          Landing zone: {alert.landing_zone.name} ({alert.landing_zone.zone_id})
        </div>
      )}
    </div>
  );
}

export default EmergencyAlertPanel;
