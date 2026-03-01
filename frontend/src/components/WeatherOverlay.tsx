import { Entity, PointGraphics, LabelGraphics, EllipseGraphics } from "resium";
import { Cartesian3, Color, NearFarScalar } from "cesium";
import { useDroneState } from "../hooks/useDroneState";

const SEOUL_LAT = 37.5665;
const SEOUL_LON = 126.978;

function WeatherOverlay() {
  const weather = useDroneState((s) => s.weather);

  if (!weather) return null;

  // Wind direction arrow entity (placed at Seoul center, elevated)
  const windDeg = weather.wind_deg;
  const arrowLat =
    SEOUL_LAT + 0.015 * Math.cos(((windDeg + 180) * Math.PI) / 180);
  const arrowLon =
    SEOUL_LON + 0.015 * Math.sin(((windDeg + 180) * Math.PI) / 180);

  const windColor =
    weather.wind_speed_ms >= 20
      ? Color.RED.withAlpha(0.8)
      : weather.wind_speed_ms >= 15
        ? Color.ORANGE.withAlpha(0.8)
        : weather.wind_speed_ms >= 10
          ? Color.YELLOW.withAlpha(0.8)
          : Color.CYAN.withAlpha(0.6);

  const precipTotal = weather.rain_1h_mm + weather.snow_1h_mm;
  const showPrecip = precipTotal > 0;

  // Precipitation radius scales with intensity (100m base + 50m per mm)
  const precipRadius = showPrecip
    ? Math.min(100 + precipTotal * 50, 2000)
    : 0;

  const precipColor =
    precipTotal >= 15
      ? Color.RED.withAlpha(0.15)
      : precipTotal >= 5
        ? Color.YELLOW.withAlpha(0.12)
        : Color.CYAN.withAlpha(0.1);

  return (
    <>
      {/* Wind direction indicator at Seoul center */}
      <Entity
        position={Cartesian3.fromDegrees(SEOUL_LON, SEOUL_LAT, 500)}
        name="Wind Origin"
      >
        <PointGraphics
          pixelSize={8}
          color={windColor}
          outlineColor={Color.WHITE}
          outlineWidth={1}
        />
        <LabelGraphics
          text={`Wind ${weather.wind_speed_ms.toFixed(1)}m/s ${windDeg}°`}
          font="11px sans-serif"
          fillColor={windColor}
          showBackground
          backgroundColor={Color.BLACK.withAlpha(0.6)}
          scale={0.8}
          pixelOffset={{ x: 0, y: -20 } as any}
          scaleByDistance={new NearFarScalar(1000, 1.0, 50000, 0.3)}
        />
      </Entity>

      {/* Wind arrow head */}
      <Entity
        position={Cartesian3.fromDegrees(arrowLon, arrowLat, 500)}
        name="Wind Direction"
      >
        <PointGraphics
          pixelSize={5}
          color={windColor}
        />
      </Entity>

      {/* Precipitation overlay */}
      {showPrecip && (
        <Entity
          position={Cartesian3.fromDegrees(SEOUL_LON, SEOUL_LAT, 0)}
          name="Precipitation Area"
        >
          <EllipseGraphics
            semiMajorAxis={precipRadius}
            semiMinorAxis={precipRadius}
            material={precipColor}
            outline
            outlineColor={precipColor}
            height={50}
          />
          <LabelGraphics
            text={`Precip ${precipTotal.toFixed(1)}mm/h`}
            font="10px sans-serif"
            fillColor={precipColor.withAlpha(1)}
            showBackground
            backgroundColor={Color.BLACK.withAlpha(0.5)}
            scale={0.7}
            pixelOffset={{ x: 0, y: 20 } as any}
            scaleByDistance={new NearFarScalar(1000, 1.0, 50000, 0.3)}
          />
        </Entity>
      )}
    </>
  );
}

export default WeatherOverlay;
