import { Entity, PointGraphics, LabelGraphics, PolylineGraphics } from "resium";
import {
  Cartesian3,
  Color,
  VerticalOrigin,
  HorizontalOrigin,
  Cartesian2,
} from "cesium";
import { useDroneState } from "../hooks/useDroneState";
import type { Drone } from "../types";

/** heading 방향으로 100m 전방 좌표 계산 */
function headingEndpoint(
  lat: number,
  lon: number,
  alt: number,
  headingDeg: number
): Cartesian3 {
  const headingRad = (headingDeg * Math.PI) / 180;
  const dLat = (100 / 111320) * Math.cos(headingRad);
  const dLon =
    (100 / (111320 * Math.cos((lat * Math.PI) / 180))) *
    Math.sin(headingRad);
  return Cartesian3.fromDegrees(lon + dLon, lat + dLat, alt);
}

/** 속도 크기 계산 */
function speed(drone: Drone): number {
  return Math.sqrt(
    drone.velocity.vx ** 2 + drone.velocity.vy ** 2 + drone.velocity.vz ** 2
  );
}

/** Zustand 스토어의 드론 위치를 Cesium Entity로 렌더링한다. */
function DroneTracker() {
  const drones = useDroneState((s) => s.drones);

  const entries = Array.from(drones.values());

  return (
    <>
      {entries.map((drone) => {
        const pos = Cartesian3.fromDegrees(
          drone.position.lon,
          drone.position.lat,
          drone.position.alt_m
        );
        const isEmergency = drone.status === "EMERGENCY";
        const spd = speed(drone);

        return (
          <Entity key={drone.drone_id} position={pos}>
            <PointGraphics
              pixelSize={isEmergency ? 16 : 12}
              color={statusColor(drone.status)}
              outlineColor={isEmergency ? Color.YELLOW : Color.WHITE}
              outlineWidth={isEmergency ? 3 : 2}
            />
            <LabelGraphics
              text={`${drone.callsign}\n${Math.round(drone.battery_percent)}% | ${spd.toFixed(1)}m/s`}
              font="12px monospace"
              fillColor={Color.WHITE}
              outlineColor={Color.BLACK}
              outlineWidth={2}
              style={2 /* FILL_AND_OUTLINE */}
              verticalOrigin={VerticalOrigin.BOTTOM}
              horizontalOrigin={HorizontalOrigin.LEFT}
              pixelOffset={new Cartesian2(8, -8)}
              showBackground
              backgroundColor={
                isEmergency
                  ? new Color(0.5, 0, 0, 0.7)
                  : new Color(0, 0, 0, 0.6)
              }
              disableDepthTestDistance={Number.POSITIVE_INFINITY}
            />
          </Entity>
        );
      })}

      {/* Heading indicator (별도 Entity — PolylineGraphics는 positions 배열 사용) */}
      {entries
        .filter((d) => d.status === "AIRBORNE" || d.status === "HOLDING")
        .map((drone) => {
          const startPos = Cartesian3.fromDegrees(
            drone.position.lon,
            drone.position.lat,
            drone.position.alt_m
          );
          const endPos = headingEndpoint(
            drone.position.lat,
            drone.position.lon,
            drone.position.alt_m,
            drone.heading
          );
          const color =
            drone.status === "HOLDING"
              ? Color.ORANGE.withAlpha(0.8)
              : Color.CYAN.withAlpha(0.8);

          return (
            <Entity key={`hdg-${drone.drone_id}`}>
              <PolylineGraphics
                positions={[startPos, endPos]}
                width={2}
                material={color}
              />
            </Entity>
          );
        })}
    </>
  );
}

function statusColor(status: string): Color {
  switch (status) {
    case "AIRBORNE":
      return Color.DODGERBLUE;
    case "LANDED":
      return Color.LIME;
    case "EMERGENCY":
      return Color.RED;
    case "HOLDING":
      return Color.ORANGE;
    default:
      return Color.GRAY;
  }
}

export default DroneTracker;
