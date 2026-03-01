import { create } from "zustand";
import type {
  Drone,
  Telemetry,
  Position3D,
  ConflictInfo,
  AvoidanceCommand,
  WeatherInfo,
  EmergencyAlert,
  LandingZoneInfo,
  ChatMessage,
  MetricsSummary,
} from "../types";

type SimStatus = "idle" | "running" | "completed" | "error";

interface DroneState {
  /** 드론 상태 맵 */
  drones: Map<string, Drone>;
  /** 비행 경로 트레일 (drone_id → Position3D[]) */
  trails: Map<string, Position3D[]>;
  /** 시뮬레이션 상태 */
  simStatus: SimStatus;
  /** 계획된 경유점 (시뮬레이션 시작 시 설정) */
  plannedWaypoints: Position3D[];
  /** 다중 드론별 계획 경로 */
  plannedRoutes: Map<string, Position3D[]>;
  /** 현재 활성 충돌 목록 */
  conflicts: ConflictInfo[];
  /** 현재 회피 명령 */
  avoidanceCommands: AvoidanceCommand[];
  /** 활성 드론 수 */
  activeCount: number;
  /** 현재 기상 정보 */
  weather: WeatherInfo | null;
  /** 비상 알림 목록 */
  emergencyAlerts: EmergencyAlert[];
  /** 비상착륙장 목록 */
  landingZones: LandingZoneInfo[];
  /** 채팅 메시지 목록 */
  chatMessages: ChatMessage[];
  /** 채팅 패널 열림 여부 */
  chatOpen: boolean;
  /** 채팅 응답 대기 중 */
  chatLoading: boolean;
  /** 채팅 세션 ID */
  chatSessionId: string;
  /** 성능 메트릭 */
  metrics: MetricsSummary | null;

  updateTelemetry: (telemetry: Telemetry) => void;
  setDrones: (drones: Drone[]) => void;
  setSimStatus: (status: SimStatus) => void;
  setPlannedWaypoints: (waypoints: Position3D[]) => void;
  setPlannedRoutes: (routes: Map<string, Position3D[]>) => void;
  setConflicts: (conflicts: ConflictInfo[], commands: AvoidanceCommand[]) => void;
  setActiveCount: (count: number) => void;
  setWeather: (weather: WeatherInfo) => void;
  addEmergencyAlert: (alert: EmergencyAlert) => void;
  clearEmergencyAlerts: () => void;
  setLandingZones: (zones: LandingZoneInfo[]) => void;
  clearTrails: () => void;
  addChatMessage: (msg: ChatMessage) => void;
  setChatOpen: (open: boolean) => void;
  setChatLoading: (loading: boolean) => void;
  clearChat: () => void;
  setMetrics: (metrics: MetricsSummary) => void;
  clearAll: () => void;
}

export const useDroneState = create<DroneState>((set) => ({
  drones: new Map(),
  trails: new Map(),
  simStatus: "idle",
  plannedWaypoints: [],
  plannedRoutes: new Map(),
  conflicts: [],
  avoidanceCommands: [],
  activeCount: 0,
  weather: null,
  emergencyAlerts: [],
  landingZones: [],
  chatMessages: [],
  chatOpen: false,
  chatLoading: false,
  chatSessionId: `session-${Date.now()}`,
  metrics: null,

  updateTelemetry: (telemetry) =>
    set((state) => {
      const drones = new Map(state.drones);
      const trails = new Map(state.trails);

      const existing = drones.get(telemetry.drone_id);
      const updated: Drone = existing
        ? {
            ...existing,
            position: telemetry.position,
            velocity: telemetry.velocity,
            heading: telemetry.heading,
            battery_percent: telemetry.battery_percent,
            status: "AIRBORNE",
          }
        : {
            drone_id: telemetry.drone_id,
            callsign: telemetry.drone_id,
            type: "MULTIROTOR",
            status: "AIRBORNE",
            position: telemetry.position,
            velocity: telemetry.velocity,
            heading: telemetry.heading,
            battery_percent: telemetry.battery_percent,
            max_speed_ms: 15,
            max_altitude_m: 400,
            current_flight_plan_id: null,
          };
      drones.set(telemetry.drone_id, updated);

      const trail = trails.get(telemetry.drone_id) ?? [];
      trail.push({ ...telemetry.position });
      trails.set(telemetry.drone_id, trail);

      return { drones, trails };
    }),

  setDrones: (drones) =>
    set(() => ({
      drones: new Map(drones.map((d) => [d.drone_id, d])),
    })),

  setSimStatus: (simStatus) => set({ simStatus }),

  setPlannedWaypoints: (plannedWaypoints) => set({ plannedWaypoints }),

  setPlannedRoutes: (plannedRoutes) => set({ plannedRoutes }),

  setConflicts: (conflicts, avoidanceCommands) =>
    set({ conflicts, avoidanceCommands }),

  setActiveCount: (activeCount) => set({ activeCount }),

  setWeather: (weather) => set({ weather }),

  addEmergencyAlert: (alert) =>
    set((state) => ({
      emergencyAlerts: [alert, ...state.emergencyAlerts].slice(0, 50),
    })),

  clearEmergencyAlerts: () => set({ emergencyAlerts: [] }),

  setLandingZones: (landingZones) => set({ landingZones }),

  clearTrails: () => set({ trails: new Map(), plannedWaypoints: [] }),

  addChatMessage: (msg) =>
    set((state) => ({
      chatMessages: [...state.chatMessages, msg],
    })),

  setChatOpen: (chatOpen) => set({ chatOpen }),

  setChatLoading: (chatLoading) => set({ chatLoading }),

  clearChat: () =>
    set({ chatMessages: [], chatSessionId: `session-${Date.now()}` }),

  setMetrics: (metrics) => set({ metrics }),

  clearAll: () =>
    set({
      drones: new Map(),
      trails: new Map(),
      simStatus: "idle",
      plannedWaypoints: [],
      plannedRoutes: new Map(),
      conflicts: [],
      avoidanceCommands: [],
      activeCount: 0,
      weather: null,
      emergencyAlerts: [],
      landingZones: [],
      chatMessages: [],
      chatOpen: false,
      chatLoading: false,
      chatSessionId: `session-${Date.now()}`,
      metrics: null,
    }),
}));
