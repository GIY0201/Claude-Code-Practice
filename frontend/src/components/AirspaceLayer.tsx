import { useState, useEffect } from "react";
import { Entity, PolygonGraphics, LabelGraphics } from "resium";
import {
  Cartesian3,
  Color,
  VerticalOrigin,
  HorizontalOrigin,
  Cartesian2,
} from "cesium";
import type { AirspaceZone, ZoneType } from "../types";

/** zone_type별 폴리곤 색상 */
function zoneColor(type: ZoneType): { fill: Color; outline: Color } {
  switch (type) {
    case "RESTRICTED":
      return {
        fill: Color.RED.withAlpha(0.2),
        outline: Color.RED.withAlpha(0.8),
      };
    case "CONTROLLED":
      return {
        fill: Color.YELLOW.withAlpha(0.12),
        outline: Color.YELLOW.withAlpha(0.7),
      };
    case "FREE":
      return {
        fill: Color.GREEN.withAlpha(0.08),
        outline: Color.GREEN.withAlpha(0.5),
      };
    case "EMERGENCY_ONLY":
      return {
        fill: Color.ORANGE.withAlpha(0.15),
        outline: Color.ORANGE.withAlpha(0.7),
      };
    default:
      return {
        fill: Color.GRAY.withAlpha(0.1),
        outline: Color.GRAY.withAlpha(0.5),
      };
  }
}

/** zone_type 라벨 */
function zoneLabel(type: ZoneType): string {
  switch (type) {
    case "RESTRICTED":
      return "RESTRICTED";
    case "CONTROLLED":
      return "CONTROLLED";
    case "FREE":
      return "FREE";
    case "EMERGENCY_ONLY":
      return "EMERGENCY";
    default:
      return type;
  }
}

/** GeoJSON 폴리곤 좌표의 중심점 계산 */
function polygonCenter(
  coords: number[][]
): { lat: number; lon: number } {
  let latSum = 0;
  let lonSum = 0;
  for (const [lon, lat] of coords) {
    latSum += lat;
    lonSum += lon;
  }
  return {
    lat: latSum / coords.length,
    lon: lonSum / coords.length,
  };
}

/** GeoJSON coordinates → Cesium Cartesian3 hierarchy positions */
function toPositions(
  coords: number[][],
  altitudeM: number
): Cartesian3[] {
  const positions: Cartesian3[] = [];
  for (const [lon, lat] of coords) {
    positions.push(Cartesian3.fromDegrees(lon, lat, altitudeM));
  }
  return positions;
}

function AirspaceLayer() {
  const [zones, setZones] = useState<AirspaceZone[]>([]);

  useEffect(() => {
    fetch("/api/airspaces/?active_only=false")
      .then((r) => {
        if (!r.ok) return [];
        return r.json();
      })
      .then((data: AirspaceZone[]) => {
        if (Array.isArray(data)) setZones(data);
      })
      .catch(() => {});
  }, []);

  if (zones.length === 0) return null;

  return (
    <>
      {zones.map((zone) => {
        const coords = zone.geometry?.coordinates?.[0];
        if (!coords || coords.length < 3) return null;

        const colors = zoneColor(zone.zone_type);

        return (
          <Entity key={zone.zone_id}>
            <PolygonGraphics
              hierarchy={toPositions(coords, zone.floor_altitude_m)}
              material={colors.fill}
              outline
              outlineColor={colors.outline}
              outlineWidth={2}
              height={zone.floor_altitude_m}
              extrudedHeight={zone.ceiling_altitude_m}
            />
          </Entity>
        );
      })}
      {/* 구역 라벨 (별도 Entity — position 필요) */}
      {zones.map((zone) => {
        const coords = zone.geometry?.coordinates?.[0];
        if (!coords || coords.length < 3) return null;

        const colors = zoneColor(zone.zone_type);
        const center = polygonCenter(coords);
        const midAlt =
          (zone.floor_altitude_m + zone.ceiling_altitude_m) / 2;

        return (
          <Entity
            key={`label-${zone.zone_id}`}
            position={Cartesian3.fromDegrees(center.lon, center.lat, midAlt)}
          >
            <LabelGraphics
              text={`${zone.name}\n[${zoneLabel(zone.zone_type)}] ${zone.floor_altitude_m}-${zone.ceiling_altitude_m}m`}
              font="11px monospace"
              fillColor={colors.outline}
              outlineColor={Color.BLACK}
              outlineWidth={2}
              style={2 /* FILL_AND_OUTLINE */}
              verticalOrigin={VerticalOrigin.CENTER}
              horizontalOrigin={HorizontalOrigin.CENTER}
              pixelOffset={new Cartesian2(0, 0)}
              showBackground
              backgroundColor={new Color(0, 0, 0, 0.5)}
              disableDepthTestDistance={Number.POSITIVE_INFINITY}
            />
          </Entity>
        );
      })}
    </>
  );
}

export default AirspaceLayer;
