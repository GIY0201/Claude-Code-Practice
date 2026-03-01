export interface Position3D {
  lat: number;
  lon: number;
  alt_m: number;
}

export interface Velocity3D {
  vx: number;
  vy: number;
  vz: number;
}

export type DroneStatus = "IDLE" | "TAXIING" | "AIRBORNE" | "HOLDING" | "EMERGENCY" | "LANDED";
export type DroneType = "MULTIROTOR" | "FIXED_WING" | "VTOL";
export type PlanStatus = "DRAFT" | "SUBMITTED" | "APPROVED" | "ACTIVE" | "COMPLETED" | "CANCELLED";
export type Priority = "LOW" | "NORMAL" | "HIGH" | "EMERGENCY";
export type MissionType = "DELIVERY" | "SURVEILLANCE" | "INSPECTION" | "EMERGENCY_RESPONSE";
export type ZoneType = "RESTRICTED" | "CONTROLLED" | "FREE" | "EMERGENCY_ONLY";

export interface Drone {
  drone_id: string;
  callsign: string;
  type: DroneType;
  status: DroneStatus;
  position: Position3D;
  velocity: Velocity3D;
  heading: number;
  battery_percent: number;
  max_speed_ms: number;
  max_altitude_m: number;
  current_flight_plan_id: string | null;
}

export interface Waypoint {
  waypoint_id: string;
  name: string;
  position: Position3D;
  waypoint_type: "DEPARTURE" | "ENROUTE" | "APPROACH" | "ARRIVAL" | "HOLDING" | "EMERGENCY";
  speed_constraint_ms: number | null;
  altitude_constraint_m: number | null;
}

export interface FlightPlan {
  plan_id: string;
  drone_id: string;
  status: PlanStatus;
  departure: Waypoint;
  destination: Waypoint;
  waypoints: Waypoint[];
  departure_time: string;
  estimated_arrival: string;
  cruise_altitude_m: number;
  cruise_speed_ms: number;
  priority: Priority;
  mission_type: MissionType;
}

export interface Telemetry {
  drone_id: string;
  timestamp: string;
  position: Position3D;
  velocity: Velocity3D;
  heading: number;
  battery_percent: number;
}

export type ManeuverType = "SPEED_CHANGE" | "ALTITUDE_CHANGE" | "LATERAL_OFFSET" | "HOLD";

export interface ConflictInfo {
  drone_a: string;
  drone_b: string;
  t_cpa_sec: number;
  d_cpa_m: number;
  horizontal_sep_m: number;
  vertical_sep_m: number;
}

export interface AvoidanceCommand {
  drone_id: string;
  maneuver_type: ManeuverType;
  target_speed_ms: number | null;
  target_alt_m: number | null;
  heading_offset_deg: number | null;
  reason: string;
}

export interface MultiDroneConfig {
  drone_id: string;
  waypoints: Position3D[];
  speed_ms: number;
  priority: Priority;
}

// ── Weather ──────────────────────────────────────────────────────────

export interface WeatherInfo {
  wind_speed_ms: number;
  wind_deg: number;
  rain_1h_mm: number;
  snow_1h_mm: number;
  description: string;
  timestamp: number;
}

// ── Emergency ────────────────────────────────────────────────────────

export type AlertLevel = "WARNING" | "CRITICAL";

export interface LandingZoneInfo {
  zone_id: string;
  name: string;
  lat: number;
  lon: number;
  alt_m: number;
}

export interface EmergencyAlert {
  drone_id: string;
  level: AlertLevel;
  type: string;
  message: string;
  landing_zone?: LandingZoneInfo;
  landing_path?: Position3D[];
  timestamp: number;
}

// ── Chat ──────────────────────────────────────────────────────────────

export type ChatIntent =
  | "FLIGHT_PLAN"
  | "ALTITUDE_CHANGE"
  | "SPEED_CHANGE"
  | "HOLD"
  | "RETURN_TO_BASE"
  | "SET_NOTAM"
  | "BRIEFING"
  | "GENERAL_QUERY";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  intent?: ChatIntent;
  requiresConfirmation?: boolean;
  action?: Record<string, unknown>;
}

// ── Metrics ──────────────────────────────────────────────────────────

export interface DroneMetrics {
  drone_id: string;
  total_distance_m: number;
  ideal_distance_m: number;
  route_efficiency: number;
  battery_consumed: number;
  flight_time_sec: number;
  completed: boolean;
}

export interface MetricsSummary {
  collision_avoidance_rate: number;
  route_efficiency: number;
  avg_response_time_ms: number;
  energy_efficiency: number;
  mission_completion_rate: number;
  avg_flight_time_sec: number;
  total_conflicts_detected: number;
  total_avoidance_maneuvers: number;
  total_distance_m: number;
  drone_metrics: Record<string, DroneMetrics>;
}

// ── Scenario ─────────────────────────────────────────────────────────

export interface ScenarioInfo {
  name: string;
  description: string;
  drone_count: number;
}

// ── Airspace ─────────────────────────────────────────────────────────

export interface AirspaceZone {
  zone_id: string;
  name: string;
  zone_type: ZoneType;
  geometry: { type: string; coordinates: number[][][] };
  floor_altitude_m: number;
  ceiling_altitude_m: number;
  active: boolean;
  schedule?: string;
  restrictions: string[];
}
