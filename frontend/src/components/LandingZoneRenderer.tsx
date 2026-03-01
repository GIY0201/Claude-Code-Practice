import { Entity, PointGraphics, LabelGraphics, PolylineGraphics } from "resium";
import { Cartesian3, Color, NearFarScalar } from "cesium";
import { useDroneState } from "../hooks/useDroneState";
import type { Position3D } from "../types";

// Default Seoul emergency landing zones (matching backend handler.py)
const DEFAULT_LANDING_ZONES = [
  { zone_id: "ELZ-001", name: "Yeouido Park", lat: 37.5264, lon: 126.9345, alt_m: 10 },
  { zone_id: "ELZ-002", name: "Ttukseom Hangang Park", lat: 37.5313, lon: 127.0662, alt_m: 10 },
  { zone_id: "ELZ-003", name: "Olympic Park", lat: 37.5209, lon: 127.1215, alt_m: 10 },
  { zone_id: "ELZ-004", name: "Nanji Hangang Park", lat: 37.5667, lon: 126.8722, alt_m: 10 },
  { zone_id: "ELZ-005", name: "Seoul Forest", lat: 37.5443, lon: 127.0374, alt_m: 10 },
];

function LandingZoneRenderer() {
  const storeZones = useDroneState((s) => s.landingZones);
  const alerts = useDroneState((s) => s.emergencyAlerts);

  // Use store zones if available, otherwise default
  const zones = storeZones.length > 0 ? storeZones : DEFAULT_LANDING_ZONES;

  // Collect landing paths from emergency alerts
  const landingPaths = alerts
    .filter((a) => a.landing_path && a.landing_path.length >= 2)
    .map((a) => ({
      droneId: a.drone_id,
      path: a.landing_path!,
    }));

  return (
    <>
      {/* Landing zone markers */}
      {zones.map((z) => {
        const isActive = alerts.some(
          (a) => a.landing_zone?.zone_id === z.zone_id
        );
        const color = isActive ? Color.RED : Color.LIME;

        return (
          <Entity
            key={z.zone_id}
            position={Cartesian3.fromDegrees(z.lon, z.lat, z.alt_m + 20)}
            name={`ELZ: ${z.name}`}
          >
            <PointGraphics
              pixelSize={isActive ? 12 : 8}
              color={color}
              outlineColor={Color.WHITE}
              outlineWidth={2}
            />
            <LabelGraphics
              text={z.name}
              font="10px sans-serif"
              fillColor={color}
              showBackground
              backgroundColor={Color.BLACK.withAlpha(0.6)}
              scale={0.7}
              pixelOffset={{ x: 0, y: -18 } as any}
              scaleByDistance={new NearFarScalar(500, 1.0, 30000, 0.2)}
            />
          </Entity>
        );
      })}

      {/* Emergency landing paths */}
      {landingPaths.map(({ droneId, path }) => (
        <Entity key={`elp-${droneId}`} name={`Emergency path: ${droneId}`}>
          <PolylineGraphics
            positions={path.map((p: Position3D) =>
              Cartesian3.fromDegrees(p.lon, p.lat, p.alt_m)
            )}
            width={3}
            material={Color.RED.withAlpha(0.8)}
          />
        </Entity>
      ))}
    </>
  );
}

export default LandingZoneRenderer;
