/** 서울 수도권 중심 좌표 (WGS84) */
export const SEOUL_CENTER = {
  lat: 37.5665,
  lon: 126.978,
  alt_m: 0,
} as const;

/** 드론 최소 이격거리 (미터) */
export const SEPARATION_HORIZONTAL_M = 100;
export const SEPARATION_VERTICAL_M = 30;

/** 고도 레이어 범위 (미터) */
export const ALTITUDE_MIN_M = 30;
export const ALTITUDE_MAX_M = 400;
