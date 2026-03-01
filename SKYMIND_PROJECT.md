# SkyMind — AI Drone Air Traffic Controller

## Project Overview

SkyMind는 실제 항공 ATC(Air Traffic Control) 시스템의 개념을 드론 스케일로 구현한 AI 기반 UTM(UAV Traffic Management) 시스템이다. 다수 드론의 항로를 자동 생성하고, 충돌 회피·우선순위 관리·기상 대응·비상 처리까지 수행하는 "AI 드론 관제사"를 목표로 한다.

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18+ + TypeScript | UI 프레임워크 |
| 3D Visualization | CesiumJS | 3D 지구본, 드론 추적, 경로/공역 렌더링 |
| Backend | FastAPI (Python 3.11+) | API 서버, AI 엔진, WebSocket |
| AI/ML | PyTorch | 강화학습 (PPO) 경로 최적화 |
| LLM | LangChain + Claude API | 자연어 비행계획 파싱, 관제 채팅, 브리핑 |
| Core Engine (Phase 3) | C++ (pybind11) | 경로 계산, 충돌 감지 고성능 모듈 |
| Database | PostgreSQL + PostGIS | 공간 데이터, 비행계획, 드론 상태 |
| Realtime | WebSocket (FastAPI) | 드론 위치 실시간 스트리밍 |
| Weather API | OpenWeatherMap API | 기상 데이터 연동 |
| Container | Docker + Docker Compose | 개발/배포 환경 |

## Project Structure

```
skymind/
├── README.md
├── SKYMIND_PROJECT.md          # 이 문서 (프로젝트 스펙)
├── docker-compose.yml
│
├── backend/
│   ├── main.py                 # FastAPI 엔트리포인트
│   ├── requirements.txt
│   ├── config.py               # 환경설정
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── flight_plan.py  # 비행계획 CRUD API
│   │   │   ├── drone.py        # 드론 상태/제어 API
│   │   │   ├── airspace.py     # 공역 관리 API
│   │   │   ├── weather.py      # 기상 데이터 API
│   │   │   └── chat.py         # LLM 관제 채팅 API
│   │   └── websocket/
│   │       └── telemetry.py    # 드론 텔레메트리 WebSocket
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── path_engine/
│   │   │   ├── astar.py        # A* 경로탐색
│   │   │   ├── rrt_star.py     # RRT* 경로탐색
│   │   │   └── optimizer.py    # 경로 최적화 (스무딩, 단축)
│   │   │
│   │   ├── deconfliction/
│   │   │   ├── strategic.py    # 비행 전 경로 충돌 검사
│   │   │   ├── tactical.py     # 비행 중 실시간 DAA
│   │   │   ├── cpa.py          # CPA (Closest Point of Approach) 계산
│   │   │   └── avoidance.py    # 회피 기동 전략
│   │   │
│   │   ├── airspace/
│   │   │   ├── manager.py      # 공역 등급/구역 관리
│   │   │   ├── notam.py        # NOTAM 파싱 및 적용
│   │   │   ├── sid_star.py     # 이착륙 표준절차
│   │   │   └── altitude.py     # 고도 레이어 시스템
│   │   │
│   │   ├── traffic/
│   │   │   ├── flow_control.py # 교통량 관리, 슬롯 배정
│   │   │   ├── holding.py      # 홀딩 패턴
│   │   │   └── priority.py     # 우선순위 시스템
│   │   │
│   │   ├── weather/
│   │   │   ├── fetcher.py      # 기상 데이터 수집
│   │   │   ├── analyzer.py     # 기상 영향 분석
│   │   │   └── rerouter.py     # 기상 기반 동적 재경로
│   │   │
│   │   └── emergency/
│   │       ├── detector.py     # 비상 상황 감지
│   │       ├── handler.py      # 비상 절차 실행
│   │       └── landing.py      # 비상 착륙장 탐색/경로 생성
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── rl/
│   │   │   ├── environment.py  # 강화학습 환경 (Gymnasium)
│   │   │   ├── agent.py        # PPO 에이전트
│   │   │   ├── reward.py       # 보상 함수
│   │   │   └── train.py        # 학습 스크립트
│   │   │
│   │   └── llm/
│   │       ├── controller.py   # LLM 관제사 메인 로직
│   │       ├── parser.py       # 자연어 → 비행계획 변환
│   │       ├── briefing.py     # 상황 브리핑 생성
│   │       └── prompts/
│   │           ├── flight_plan.py   # 비행계획 파싱 프롬프트
│   │           ├── command.py       # 관제 명령 프롬프트
│   │           └── briefing.py      # 브리핑 생성 프롬프트
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── drone.py            # 드론 데이터 모델
│   │   ├── flight_plan.py      # 비행계획 데이터 모델
│   │   ├── airspace.py         # 공역 데이터 모델
│   │   ├── waypoint.py         # 경유점 데이터 모델
│   │   └── telemetry.py        # 텔레메트리 데이터 모델
│   │
│   ├── simulator/
│   │   ├── __init__.py
│   │   ├── drone_sim.py        # 드론 물리 시뮬레이션
│   │   ├── multi_drone.py      # 다중 드론 시뮬레이터
│   │   ├── scenario.py         # 시나리오 관리
│   │   └── scenarios/
│   │       ├── delivery.json   # 배송 시나리오
│   │       ├── surveillance.json # 감시 시나리오
│   │       └── emergency.json  # 비상 시나리오
│   │
│   └── db/
│       ├── database.py         # DB 연결 관리
│       ├── crud.py             # CRUD 함수
│       └── migrations/         # Alembic 마이그레이션
│
├── cpp_engine/                 # Phase 3: C++ 고성능 모듈
│   ├── CMakeLists.txt
│   ├── src/
│   │   ├── path_engine.cpp     # C++ 경로 계산
│   │   ├── cpa_engine.cpp      # C++ CPA 계산
│   │   └── collision.cpp       # C++ 충돌 감지
│   ├── include/
│   │   └── skymind/
│   │       ├── path_engine.h
│   │       ├── cpa_engine.h
│   │       └── collision.h
│   └── bindings/
│       └── pybind_module.cpp   # pybind11 바인딩
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   │
│   └── src/
│       ├── App.tsx
│       ├── main.tsx
│       │
│       ├── components/
│       │   ├── CesiumViewer.tsx     # Cesium 3D 뷰어
│       │   ├── DroneTracker.tsx     # 드론 실시간 추적
│       │   ├── RouteRenderer.tsx    # 경로 렌더링
│       │   ├── AirspaceLayer.tsx    # 공역 시각화
│       │   ├── WeatherOverlay.tsx   # 기상 오버레이
│       │   ├── Dashboard.tsx        # 메인 대시보드
│       │   ├── FlightPlanPanel.tsx  # 비행계획 패널
│       │   ├── ChatController.tsx   # LLM 관제 채팅 UI
│       │   ├── AlertPanel.tsx       # 경고/비상 알림
│       │   └── MetricsPanel.tsx     # 성능 메트릭
│       │
│       ├── hooks/
│       │   ├── useWebSocket.ts      # WebSocket 연결
│       │   ├── useCesium.ts         # Cesium 인스턴스 관리
│       │   └── useDroneState.ts     # 드론 상태 관리
│       │
│       ├── services/
│       │   ├── api.ts               # REST API 클라이언트
│       │   └── websocket.ts         # WebSocket 서비스
│       │
│       ├── types/
│       │   └── index.ts             # TypeScript 타입 정의
│       │
│       └── utils/
│           ├── geo.ts               # 지리 계산 유틸
│           └── constants.ts         # 상수 정의
│
└── tests/
    ├── backend/
    │   ├── test_path_engine.py
    │   ├── test_deconfliction.py
    │   ├── test_airspace.py
    │   ├── test_weather.py
    │   └── test_emergency.py
    └── frontend/
        └── ...
```

## Aviation Concepts Mapping

SkyMind는 실제 항공 관제 시스템의 핵심 개념을 드론 UTM으로 매핑한다. 모든 모듈 구현 시 아래 매핑을 참고하여 실제 항공 용어와 개념을 최대한 반영한다.

| 실제 항공 개념 | SkyMind 구현 | 설명 |
|--------------|-------------|------|
| **Flight Plan (ICAO format)** | `FlightPlan` 모델 | 출발/도착, 경유점, 고도, 속도, 비행 목적 포함 |
| **Airspace Class (A~G)** | 드론 공역 등급 시스템 | RESTRICTED (금지), CONTROLLED (허가 필요), FREE (자유 비행) |
| **SID (Standard Instrument Departure)** | 버티포트 출발 절차 | 이륙 후 표준 상승 경로 |
| **STAR (Standard Terminal Arrival Route)** | 버티포트 접근 절차 | 착륙 전 표준 하강 경로 |
| **Separation Minima** | 드론 간 최소 이격 | 수평 100m, 수직 30m (설정 가능) |
| **TCAS (Traffic Collision Avoidance)** | DAA (Detect And Avoid) | AI 기반 실시간 충돌 예측 + 자동 회피 기동 |
| **METAR/TAF** | 기상 데이터 연동 | OpenWeather API → 풍속, 강수, 시정 데이터 |
| **NOTAM** | 실시간 공역 공지 | 임시 비행금지구역 동적 생성/해제 |
| **Squawk / Transponder** | Remote ID | 드론 고유 식별 코드 + 위치 브로드캐스트 |
| **ADS-B** | 드론 텔레메트리 | 위치, 속도, 고도, 배터리, 상태 실시간 전송 |
| **Flow Control (ATFM)** | 교통량 관리 | 혼잡 구역 슬롯 배정, 지연 관리 |
| **Emergency (Mayday/Pan-Pan)** | 비상 관리 시스템 | 배터리 부족, 통신 두절, GPS 장애, 기체 이상 |
| **Flight Level** | 고도 레이어 시스템 | 방향별 고도 분리: 동→서 짝수층(60m, 80m, 100m), 서→동 홀수층(70m, 90m, 110m) |
| **Holding Pattern** | 드론 홀딩 | 대기 구역에서 원형/레이스트랙 패턴 비행 |
| **Clearance** | 비행 승인 시스템 | 비행계획 제출 → 검증 → 승인/거부 |

## Data Models

### Drone

```python
class Drone(BaseModel):
    drone_id: str                    # 고유 식별자 (Remote ID)
    callsign: str                    # 호출부호 (예: "SKY-001")
    type: DroneType                  # MULTIROTOR, FIXED_WING, VTOL
    status: DroneStatus              # IDLE, TAXIING, AIRBORNE, HOLDING, EMERGENCY, LANDED
    position: Position3D             # 현재 위치 (lat, lon, alt_m)
    velocity: Velocity3D             # 현재 속도 (vx, vy, vz m/s)
    heading: float                   # 기수 방향 (degrees)
    battery_percent: float           # 배터리 잔량 (%)
    max_speed_ms: float              # 최대 속도 (m/s)
    max_altitude_m: float            # 최대 비행 고도 (m)
    endurance_minutes: float         # 최대 체공 시간 (분)
    weight_kg: float                 # 기체 중량 (kg)
    current_flight_plan_id: str | None
```

### FlightPlan

```python
class FlightPlan(BaseModel):
    plan_id: str                     # 고유 식별자
    drone_id: str                    # 배정 드론
    status: PlanStatus               # DRAFT, SUBMITTED, APPROVED, ACTIVE, COMPLETED, CANCELLED
    departure: Waypoint              # 출발 버티포트/위치
    destination: Waypoint            # 도착 버티포트/위치
    waypoints: list[Waypoint]        # 경유점 목록
    departure_time: datetime         # 예정 출발 시각
    estimated_arrival: datetime      # 예상 도착 시각
    cruise_altitude_m: float         # 순항 고도 (m)
    cruise_speed_ms: float           # 순항 속도 (m/s)
    priority: Priority               # LOW, NORMAL, HIGH, EMERGENCY
    mission_type: MissionType        # DELIVERY, SURVEILLANCE, INSPECTION, EMERGENCY_RESPONSE
    route_distance_m: float          # 총 경로 거리
    estimated_energy_wh: float       # 예상 에너지 소비량
```

### Waypoint

```python
class Waypoint(BaseModel):
    waypoint_id: str
    name: str                        # 경유점 이름
    position: Position3D             # 위치 (lat, lon, alt_m)
    waypoint_type: WaypointType      # DEPARTURE, ENROUTE, APPROACH, ARRIVAL, HOLDING, EMERGENCY
    speed_constraint_ms: float | None # 속도 제한
    altitude_constraint_m: float | None # 고도 제한
    estimated_time: datetime | None
```

### Airspace Zone

```python
class AirspaceZone(BaseModel):
    zone_id: str
    name: str
    zone_type: ZoneType              # RESTRICTED, CONTROLLED, FREE, EMERGENCY_ONLY
    geometry: GeoJSON                # 구역 경계 (GeoJSON Polygon)
    floor_altitude_m: float          # 하한 고도
    ceiling_altitude_m: float        # 상한 고도
    active: bool                     # 활성 여부
    schedule: str | None             # 활성 시간 (NOTAM 기반)
    restrictions: list[str]          # 제한 사항
```

### Telemetry (실시간 스트리밍)

```python
class Telemetry(BaseModel):
    drone_id: str
    timestamp: datetime
    position: Position3D
    velocity: Velocity3D
    heading: float
    battery_percent: float
    gps_fix: GPSFixType              # NO_FIX, 2D, 3D, RTK
    signal_strength: float           # 통신 신호 강도 (%)
    motor_status: list[MotorStatus]
    alerts: list[Alert]              # 활성 경고 목록
```

## Core Algorithms

### 1. Path Engine

**A* Algorithm (Phase 1)**
- 3D 그리드 기반 경로탐색
- 비용 함수: 거리 + 고도 변화 + 공역 제한 페널티 + 기상 페널티
- 휴리스틱: Haversine distance + 고도차

**RRT* Algorithm (Phase 2)**
- 연속 공간 경로탐색 (그리드 제한 없음)
- 장애물(건물, 금지구역) 회피 내장
- Path smoothing: B-spline 기반 경로 스무딩

**Reinforcement Learning (Phase 3)**
- Algorithm: PPO (Proximal Policy Optimization)
- Environment: Gymnasium 커스텀 환경

```
State Space:
  - 드론 현재 위치 (lat, lon, alt) — normalized
  - 목적지 상대 위치 (dx, dy, dz)
  - 주변 드론 위치 (최근접 K대)
  - 주변 장애물/금지구역 거리
  - 기상 조건 (풍속, 풍향, 강수)
  - 배터리 잔량
  - 현재 속도/방향

Action Space (Continuous):
  - 방향 변경 (delta_heading: -30° ~ +30°)
  - 속도 변경 (delta_speed: -5 ~ +5 m/s)
  - 고도 변경 (delta_altitude: -10 ~ +10 m)

Reward Function:
  + 목적지 접근 보상 (거리 감소량 비례)
  + 도착 보너스 (+100)
  - 공역 위반 페널티 (-50)
  - 이격거리 위반 페널티 (-30, 거리 반비례)
  - 에너지 소비 페널티 (배터리 사용량 비례)
  - 시간 경과 페널티 (-0.1/step)
  + 기상 안전 보상 (위험 기상 회피 시)
  + 규정 준수 보상 (고도 레이어, 속도 제한 준수)
```

### 2. Collision Avoidance (DAA)

**CPA (Closest Point of Approach) 계산**

```
두 드론 i, j에 대해:
  상대 위치: dr = pos_j - pos_i
  상대 속도: dv = vel_j - vel_i
  
  t_cpa = -dot(dr, dv) / dot(dv, dv)    # CPA까지 시간
  d_cpa = |dr + dv * t_cpa|              # CPA 거리
  
  if t_cpa > 0 and d_cpa < separation_minima:
      → 충돌 경고 발생 → 회피 기동 실행
```

**회피 전략 우선순위**

1. **속도 조절** — 감속/가속으로 시간 분리 (최소 경로 변경)
2. **고도 변경** — 수직 분리 확보 (빠르고 효과적)
3. **경로 우회** — 수평 경로 변경 (최후 수단)

**우선순위 규칙**
- EMERGENCY > HIGH > NORMAL > LOW
- 동일 우선순위: 오른쪽 드론 우선 (항공 규칙 준용)
- 상승 중인 드론이 회피 기동 실행 (강하 중인 드론 경로 유지)

### 3. Weather-based Dynamic Rerouting

```
기상 조건별 제한:
  풍속 > 10 m/s  → 고도 조정 (저고도로 이동)
  풍속 > 15 m/s  → 경로 우회 (바람 수직 방향)
  풍속 > 20 m/s  → 비행 중지 / 최근접 착륙
  강수 > 5 mm/h  → 속도 50% 제한
  강수 > 15 mm/h → 비행 중지
  시정 < 1 km    → 속도 제한 + 이격거리 2배
  시정 < 500 m   → 비행 중지
```

### 4. Emergency Procedures

```
배터리 부족 (< 20%):
  → 경고 발생
  → 최근접 착륙 가능 지점 탐색
  → 직행 경로 생성 (최소 에너지)
  → 다른 드론에 우선순위 부여

배터리 위험 (< 10%):
  → EMERGENCY 선언
  → 즉시 강하 시작
  → 최근접 안전 지점 강제 착륙
  → 모든 주변 드론 회피 기동

통신 두절 (> 30초):
  → 마지막 알려진 비행계획 유지
  → 60초 후: 사전 지정 귀환 경로 실행
  → 120초 후: 제자리 강하 착륙

GPS 장애:
  → INS(관성항법) 데드레코닝 전환
  → 정확도 저하 시 안전 착륙
  → 주변 드론 이격거리 확대
```

## LLM Controller Specification

### Natural Language → Flight Plan Parsing

**입력 예시:**
```
"홍대에서 강남역까지 드론 배송, 고도 120m, 한강 위로 가줘"
"서울역 주변 30분 감시비행, 반경 500m"
"인천공항에서 김포공항으로 3대 동시 배송, 10분 간격"
```

**출력: 구조화된 FlightPlan JSON**

### Controller Chat Commands

**관제 명령 예시:**
```
"드론 3번 고도 올려" → 고도 변경 API 호출
"전체 드론 홀딩" → 모든 활성 드론 홀딩 패턴 진입
"A구역 비행금지 설정, 30분" → 임시 NOTAM 생성
"드론 5번 귀환시켜" → RTL(Return To Launch) 경로 생성
"현재 상황 브리핑해줘" → 전체 교통 상황 자연어 요약
```

### Situation Briefing Generation

LLM이 현재 시스템 상태를 자연어로 요약:
```
"현재 12대 운항 중, 3대 대기. B구역 교통량 높음 — 슬롯 배정 활성.
드론 SKY-007 배터리 15%, 비상착륙 경로 생성 완료.
30분 후 A구역 기상 악화 예보 — 해당 구역 드론 2대 사전 재경로 권고."
```

## Development Phases

### Phase 1: Foundation (2~3주)

**목표:** 지도 위에 드론 한 대가 A→B로 날아가는 것

**Tasks:**
1. 프로젝트 스캐폴딩
   - FastAPI 백엔드 + React/CesiumJS 프론트엔드 초기 설정
   - Docker Compose 개발 환경
   - PostgreSQL + PostGIS 설정
2. 데이터 모델 구현
   - Drone, FlightPlan, Waypoint, AirspaceZone 모델
   - SQLAlchemy ORM + Alembic 마이그레이션
3. A* 경로 생성 엔진
   - 3D 그리드 기반 경로탐색
   - 금지구역 회피
   - 경로 스무딩
4. 기본 공역 관리
   - GeoJSON 기반 공역 구역 정의
   - RESTRICTED / CONTROLLED / FREE 구역
5. CesiumJS 3D 시각화
   - 지구본 렌더링
   - 드론 Entity + 경로 Polyline
   - 공역 구역 Polygon 렌더링
6. 실시간 통신
   - WebSocket으로 드론 위치 스트리밍
   - 드론 시뮬레이터 (단일 드론 직선/경유점 비행)
7. REST API
   - 비행계획 생성/조회/승인
   - 드론 상태 조회

**완료 기준:** 웹에서 3D 지도 위에 드론 한 대가 출발지→경유점→도착지로 비행하는 애니메이션이 보이면 Phase 1 완료.

---

### Phase 2: Multi-Drone & Deconfliction (3~4주)

**목표:** 다수 드론이 동시에 날면서 서로 안 부딪히는 것

**Tasks:**
1. 다중 드론 시뮬레이터
   - N대 드론 동시 시뮬레이션
   - 각 드론 독립 비행계획 실행
2. Strategic Deconfliction
   - 비행계획 제출 시 기존 경로와 4D 시공간 충돌 검사
   - 충돌 발견 시 자동 시간 조정 or 경로 수정 제안
3. Tactical DAA
   - CPA 계산 엔진
   - 실시간 충돌 예측 (Look-ahead: 30초~120초)
   - 자동 회피 기동 (속도 조절 → 고도 변경 → 경로 우회)
4. 고도 레이어 시스템
   - 방향별 고도 분리
   - 자동 고도 배정
5. 대시보드 강화
   - 이격거리 모니터링 (위험 시 빨간색 표시)
   - 충돌 경고 알림
   - 다중 드론 상태 패널

**완료 기준:** 10대 드론이 동시에 다양한 경로로 비행하며, 교차 시 자동으로 회피 기동이 발생하고, 대시보드에서 실시간 모니터링 가능.

---

### Phase 3: AI Brain (4~5주)

**목표:** AI가 스스로 최적 경로를 찾고 상황에 따라 판단하는 것

**Tasks:**
1. RRT* 경로 엔진
   - 연속 공간 경로탐색
   - 장애물/금지구역 회피
   - B-spline 경로 스무딩
2. 강화학습 경로 최적화
   - Gymnasium 커스텀 환경 구현
   - PPO 에이전트 학습
   - A*/RRT* 결과를 초기 정책으로 활용 (imitation learning)
3. 기상 연동 동적 재경로
   - OpenWeather API 연동
   - 기상 조건별 비행 제한 적용
   - 자동 재경로 생성
4. 비상 관리 시스템
   - 배터리 부족 / 통신 두절 / GPS 장애 감지
   - 비상 착륙장 DB + 최근접 탐색
   - 비상 경로 자동 생성
5. C++ 핵심 엔진 포팅
   - 경로 계산 (A*, RRT*) C++ 구현
   - CPA 계산 C++ 구현
   - pybind11로 Python 바인딩
   - 벤치마크: Python vs C++ 성능 비교

**완료 기준:** RL 에이전트가 학습된 정책으로 경로를 생성하고, 기상 변화에 실시간 대응하며, C++ 엔진이 Python 대비 유의미한 성능 향상을 보임.

---

### Phase 4: LLM Controller (2~3주)

**목표:** 자연어로 관제할 수 있는 AI 관제사

**Tasks:**
1. 자연어 비행계획 파서
   - LangChain + Claude API
   - 자연어 → 구조화된 FlightPlan JSON 변환
   - 지오코딩 연동 (주소/장소명 → 좌표)
2. 관제사 채팅 인터페이스
   - 실시간 자연어 명령 → API 호출 매핑
   - 명령 확인/검증 단계 포함
   - 명령 이력 관리
3. 상황 브리핑 생성
   - 현재 교통 상황 자연어 요약
   - 이상 징후 하이라이트
   - 권고 사항 제시
4. NOTAM 자동 해석
   - 텍스트 NOTAM → 공역 제한 자동 적용
   - 자연어로 NOTAM 생성 가능

**완료 기준:** 채팅으로 "홍대에서 강남까지 배송 드론 보내줘"라고 입력하면, 비행계획이 자동 생성되고, 드론이 비행을 시작하며, 진행 상황을 자연어로 브리핑받을 수 있음.

---

### Phase 5: Full System & Polish (2~3주)

**목표:** 데모 가능한 완성품

**Tasks:**
1. 3D 대시보드 완성
   - 드론 3D 모델 렌더링
   - 경로 궤적 트레일
   - 공역 등급별 색상 구분
   - 기상 오버레이
2. 시나리오 시뮬레이터
   - 배송 시나리오 (다수 드론 동시 배송)
   - 감시 시나리오 (순찰 경로 자동 생성)
   - 비상 시나리오 (배터리 부족 + 기상 악화 복합 상황)
3. 성능 메트릭 대시보드
   - 충돌 회피율
   - 경로 효율 (최적 경로 대비 %)
   - 평균 응답 시간
   - 에너지 효율
4. 문서화 & 데모
   - README.md (설치/실행 가이드)
   - Architecture Document
   - 데모 영상 녹화
   - 포트폴리오 슬라이드

**완료 기준:** 비개발자도 데모를 보고 시스템을 이해할 수 있으며, 주요 시나리오가 안정적으로 실행됨.

## Configuration

### Environment Variables

```env
# Backend
DATABASE_URL=postgresql://skymind:password@localhost:5432/skymind
REDIS_URL=redis://localhost:6379

# API Keys
OPENWEATHER_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here

# Cesium
CESIUM_ION_TOKEN=your_token_here

# Simulation
SIM_TICK_RATE_HZ=10
SIM_DEFAULT_DRONES=5

# DAA Parameters
SEPARATION_HORIZONTAL_M=100
SEPARATION_VERTICAL_M=30
CPA_LOOKAHEAD_SEC=120
CPA_WARNING_SEC=60

# Altitude Layers
ALTITUDE_MIN_M=30
ALTITUDE_MAX_M=400
ALTITUDE_LAYER_STEP_M=10
```

## Key Libraries

### Backend (Python)
- `fastapi` — Web framework + WebSocket
- `sqlalchemy` + `geoalchemy2` — ORM + 공간 데이터
- `alembic` — DB 마이그레이션
- `torch` — PyTorch (강화학습)
- `gymnasium` — RL 환경
- `stable-baselines3` — PPO 구현
- `langchain` + `anthropic` — LLM 연동
- `shapely` — 기하학 연산
- `pyproj` — 좌표계 변환
- `httpx` — 외부 API 호출 (기상 등)
- `pydantic` — 데이터 검증
- `geopy` — 지오코딩

### Frontend (TypeScript)
- `react` — UI 프레임워크
- `cesium` + `resium` — CesiumJS React 바인딩
- `zustand` — 상태 관리
- `axios` — HTTP 클라이언트
- `tailwindcss` — 스타일링

### C++ Engine
- `Eigen` — 선형대수
- `pybind11` — Python 바인딩
- `Boost.Geometry` — 기하학 연산

## Testing Strategy

- **Unit Tests:** 각 모듈별 pytest 테스트 (경로 계산 정확도, CPA 계산, 공역 판정)
- **Integration Tests:** API 엔드포인트 테스트, WebSocket 통신 테스트
- **Simulation Tests:** 시나리오 기반 End-to-End 테스트 (10대 드론 충돌 없이 비행 완료)
- **Performance Tests:** C++ vs Python 벤치마크, 동시 드론 수 한계 테스트
- **LLM Tests:** 자연어 입력 → 비행계획 변환 정확도, 명령 실행 정확도

## Notes for Claude Code

- 각 Phase는 순차적으로 개발한다. Phase N이 완료되어야 Phase N+1로 넘어간다.
- 모든 코드는 type hint를 포함하고, docstring을 작성한다.
- 커밋 메시지는 Conventional Commits 규칙을 따른다.
- 새 기능 추가 시 관련 테스트를 함께 작성한다.
- 공역/경로 관련 좌표는 WGS84 (EPSG:4326)를 사용한다.
- 거리 계산은 Haversine 또는 Vincenty 공식을 사용한다.
- 시뮬레이션 기본 지역은 서울 수도권 (37.5665°N, 126.9780°E 중심)으로 설정한다.
- 항공 용어와 개념은 ICAO 표준을 최대한 따른다.
- Phase 1부터 작동하는 프로토타입을 유지하며 점진적으로 기능을 추가한다.
