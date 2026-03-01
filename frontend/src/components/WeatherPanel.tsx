import { useDroneState } from "../hooks/useDroneState";

function WeatherPanel() {
  const weather = useDroneState((s) => s.weather);

  if (!weather) return null;

  const windLevel =
    weather.wind_speed_ms >= 20
      ? "GROUNDED"
      : weather.wind_speed_ms >= 15
        ? "DANGER"
        : weather.wind_speed_ms >= 10
          ? "CAUTION"
          : "NORMAL";

  const precipLevel =
    weather.rain_1h_mm + weather.snow_1h_mm >= 15
      ? "GROUNDED"
      : weather.rain_1h_mm + weather.snow_1h_mm >= 5
        ? "CAUTION"
        : "NORMAL";

  const overallLevel =
    windLevel === "GROUNDED" || precipLevel === "GROUNDED"
      ? "GROUNDED"
      : windLevel === "DANGER"
        ? "DANGER"
        : windLevel === "CAUTION" || precipLevel === "CAUTION"
          ? "CAUTION"
          : "NORMAL";

  const statusColor = {
    NORMAL: "text-green-400",
    CAUTION: "text-yellow-400",
    DANGER: "text-orange-400",
    GROUNDED: "text-red-400",
  }[overallLevel];

  const statusBg = {
    NORMAL: "bg-green-900/30",
    CAUTION: "bg-yellow-900/30",
    DANGER: "bg-orange-900/30",
    GROUNDED: "bg-red-900/30",
  }[overallLevel];

  // Wind direction arrow rotation (meteorological: where wind comes FROM)
  const arrowRotation = weather.wind_deg;

  return (
    <div className="border-b border-gray-700">
      <div className={`px-4 py-2 flex items-center justify-between ${statusBg}`}>
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Weather
        </h2>
        <span className={`text-xs font-bold ${statusColor}`}>{overallLevel}</span>
      </div>
      <div className="px-4 py-2.5 grid grid-cols-2 gap-x-3 gap-y-1.5 text-xs">
        {/* Wind */}
        <div className="flex items-center gap-1.5">
          <span
            className="text-gray-400 inline-block"
            style={{ transform: `rotate(${arrowRotation + 180}deg)` }}
          >
            ↑
          </span>
          <span className="text-gray-500">Wind</span>
        </div>
        <span className="text-gray-300 font-mono text-right">
          {weather.wind_speed_ms.toFixed(1)} m/s {weather.wind_deg.toFixed(0)}°
        </span>

        {/* Rain */}
        <span className="text-gray-500">Rain</span>
        <span className="text-gray-300 font-mono text-right">
          {weather.rain_1h_mm.toFixed(1)} mm/h
        </span>

        {/* Snow */}
        {weather.snow_1h_mm > 0 && (
          <>
            <span className="text-gray-500">Snow</span>
            <span className="text-gray-300 font-mono text-right">
              {weather.snow_1h_mm.toFixed(1)} mm/h
            </span>
          </>
        )}

        {/* Description */}
        {weather.description && (
          <>
            <span className="text-gray-500">Desc</span>
            <span className="text-gray-400 text-right capitalize">
              {weather.description}
            </span>
          </>
        )}
      </div>
    </div>
  );
}

export default WeatherPanel;
