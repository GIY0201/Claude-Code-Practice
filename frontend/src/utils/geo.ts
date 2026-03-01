import type { Position3D } from "../types";

/** Haversine 공식으로 두 좌표 간 거리 계산 (미터) */
export function haversineDistance(a: Position3D, b: Position3D): number {
  const R = 6371000; // 지구 반지름 (미터)
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);

  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;

  return 2 * R * Math.asin(Math.sqrt(h));
}

function toRad(deg: number): number {
  return (deg * Math.PI) / 180;
}
