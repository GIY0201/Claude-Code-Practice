import { Entity, PolylineGraphics } from "resium";
import { Cartesian3, Color } from "cesium";
import { useDroneState } from "../hooks/useDroneState";

/** 드론별 계획 경로 색상 */
const ROUTE_COLORS = [
  Color.YELLOW.withAlpha(0.5),
  Color.ORANGE.withAlpha(0.5),
  Color.MAGENTA.withAlpha(0.5),
  Color.LIME.withAlpha(0.5),
  Color.AQUA.withAlpha(0.5),
];

/** 비행 경로를 Cesium Polyline으로 렌더링한다. */
function RouteRenderer() {
  const trails = useDroneState((s) => s.trails);
  const plannedWaypoints = useDroneState((s) => s.plannedWaypoints);
  const plannedRoutes = useDroneState((s) => s.plannedRoutes);

  const trailEntries = Array.from(trails.entries());
  const routeEntries = Array.from(plannedRoutes.entries());

  return (
    <>
      {/* 단일 드론 계획 경로 (기존 호환) */}
      {plannedWaypoints.length >= 2 && routeEntries.length === 0 && (
        <Entity>
          <PolylineGraphics
            positions={Cartesian3.fromDegreesArrayHeights(
              plannedWaypoints.flatMap((wp) => [wp.lon, wp.lat, wp.alt_m])
            )}
            width={2}
            material={Color.YELLOW.withAlpha(0.5)}
            clampToGround={false}
          />
        </Entity>
      )}

      {/* 다중 드론 계획 경로 */}
      {routeEntries.map(([droneId, wps], idx) =>
        wps.length >= 2 ? (
          <Entity key={`route-${droneId}`}>
            <PolylineGraphics
              positions={Cartesian3.fromDegreesArrayHeights(
                wps.flatMap((wp) => [wp.lon, wp.lat, wp.alt_m])
              )}
              width={2}
              material={ROUTE_COLORS[idx % ROUTE_COLORS.length]}
              clampToGround={false}
            />
          </Entity>
        ) : null
      )}

      {/* 실제 비행 트레일 */}
      {trailEntries.map(
        ([droneId, trail]) =>
          trail.length >= 2 && (
            <Entity key={`trail-${droneId}`}>
              <PolylineGraphics
                positions={Cartesian3.fromDegreesArrayHeights(
                  trail.flatMap((p) => [p.lon, p.lat, p.alt_m])
                )}
                width={3}
                material={Color.CYAN.withAlpha(0.8)}
                clampToGround={false}
              />
            </Entity>
          )
      )}
    </>
  );
}

export default RouteRenderer;
