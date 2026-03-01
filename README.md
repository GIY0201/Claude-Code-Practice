# SkyMind — AI 드론 항공 관제 시스템

실제 항공 ATC(Air Traffic Control) 개념을 드론 스케일로 구현한 AI 기반 UTM(UAV Traffic Management) 시스템입니다. 다수 드론의 항로를 자동 생성하고, 충돌 감지 및 회피, 기상 대응, 비상 처리까지 실시간으로 수행합니다.

## 주요 기능

- **자율 경로 계획** — A* 및 RRT* 알고리즘 + 경로 스무딩/단축 최적화
- **충돌 회피 (DAA)** — CPA 기반 충돌 감지 + 전술적 회피 기동 (속도/고도/수평/정지)
- **전략적 경로 분리** — 비행 전 4D 경로 충돌 검사 + 우선순위 기반 양보
- **공역 관리** — 구역별 공역 (제한/통제/자유/비상전용) + 고도 레이어 시스템
- **기상 연동** — OpenWeatherMap API + 바람/강수/시정 기반 동적 재경로
- **비상 관리** — 배터리/고도/지오펜스 모니터링 + 장애물 회피 비상 착륙 경로 탐색
- **RL 경로 최적화** — PPO 에이전트 (Stable-Baselines3) + 커리큘럼 보상 함수
- **LLM 관제사** — 자연어 비행계획 파싱, 관제 채팅, 상황 브리핑 (Claude API)
- **3D 시각화** — CesiumJS 지구본 + 실시간 드론 추적, 방향 표시, 경로/공역 렌더링, 기상 오버레이
- **성능 메트릭** — 충돌 회피율, 경로 효율, 에너지 효율, 임무 완료율 실시간 추적
- **시나리오 시뮬레이터** — 배송/감시/비상 시나리오 내장 + 다중 드론 시뮬레이션
- **C++ 엔진** — A*/RRT*/CPA 고성능 모듈 (pybind11, Python 자동 폴백)

## 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│  프론트엔드 (React 18 + CesiumJS + Zustand + TailwindCSS) │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────┐ │
│  │ 3D 뷰어  │ │ 대시보드  │ │시뮬레이션│ │ 채팅 패널 │ │
│  │ 드론추적 │ │ 충돌경고  │ │ 시나리오 │ │ LLM 관제  │ │
│  │ 경로표시 │ │ 기상정보  │ │ 컨트롤  │ │           │ │
│  │ 공역표시 │ │ 메트릭   │ │          │ │           │ │
│  └────┬─────┘ └─────┬─────┘ └────┬─────┘ └─────┬─────┘ │
│       └──────────────┴───────────┬┴──────────────┘       │
│                     WebSocket + REST API                 │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────┐
│              백엔드 (FastAPI + Python 3.11+)              │
│                                                          │
│  API 계층:  REST CRUD + WebSocket 텔레메트리              │
│  ┌───────────────────────────────────────────────┐       │
│  │ 경로 엔진  │ DAA 엔진  │ 기상    │ 비상      │       │
│  │ A* / RRT*  │ CPA+회피  │ 수집    │ 감지      │       │
│  │ 최적화     │ 전술적    │ 분석    │ 처리      │       │
│  │            │ 전략적    │ 재경로  │ 착륙경로  │       │
│  └───────────────────────────────────────────────┘       │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────┐       │
│  │ RL 에이전트 │ │ LLM 모듈    │ │ 시뮬레이터   │       │
│  │ PPO / SB3   │ │ Claude API  │ │ 다중 드론    │       │
│  │ Gymnasium   │ │             │ │ 시나리오     │       │
│  └─────────────┘ └─────────────┘ └──────────────┘       │
│                                                          │
│  ┌────────────────┐  ┌────────────────────────┐          │
│  │ PostgreSQL     │  │ C++ 엔진 (선택사항)    │          │
│  │ + PostGIS      │  │ pybind11 바인딩         │          │
│  └────────────────┘  └────────────────────────┘          │
└──────────────────────────────────────────────────────────┘
```

## 빠른 시작

### 사전 요구사항

- Python 3.11+
- Node.js 18+
- PostgreSQL 16 + PostGIS (또는 Docker)

### 설치

```bash
# 클론
git clone <repo-url> && cd Drone_ATC

# 백엔드
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# 프론트엔드
cd frontend && npm install && cd ..

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 입력:
#   OPENWEATHER_API_KEY  (선택 — 비어있으면 Mock 모드로 동작)
#   ANTHROPIC_API_KEY    (LLM 채팅 기능용)
#   CESIUM_ION_TOKEN     (3D 지도 타일용)

# 데이터베이스 마이그레이션
cd backend && alembic upgrade head && cd ..
```

### 실행

```bash
# 터미널 1 — 백엔드
source .venv/bin/activate
cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 터미널 2 — 프론트엔드
cd frontend && npm run dev
# 브라우저에서 http://localhost:5173 접속
```

### Docker 실행

```bash
docker-compose up --build
# 백엔드: http://localhost:8000
# 프론트엔드: http://localhost:5173
```

## 기술 스택

| 계층 | 기술 |
|------|------|
| 프론트엔드 | React 18, TypeScript, CesiumJS (Resium), Zustand, TailwindCSS, Vite |
| 백엔드 | FastAPI, Python 3.11+, Pydantic, SQLAlchemy, WebSocket |
| AI/ML | PyTorch, Stable-Baselines3 (PPO), Gymnasium |
| LLM | Anthropic Claude API |
| 데이터베이스 | PostgreSQL 16 + PostGIS |
| C++ 엔진 | C++17, pybind11, CMake |
| 기상 API | OpenWeatherMap API |
| 컨테이너 | Docker + Docker Compose |

## 프로젝트 구조

```
Drone_ATC/
├── backend/
│   ├── main.py                  # FastAPI 진입점
│   ├── config.py                # 환경 설정
│   ├── api/routes/              # REST 엔드포인트 (drone, flight_plan, airspace, weather, chat, scenario, metrics)
│   ├── api/websocket/           # WebSocket 텔레메트리 스트리밍
│   ├── core/path_engine/        # A*, RRT*, 경로 최적화
│   ├── core/deconfliction/      # CPA, 회피, 전술적 DAA, 전략적 4D
│   ├── core/weather/            # 기상 수집, 분석, 동적 재경로
│   ├── core/emergency/          # 비상 감지, 처리, 착륙 경로
│   ├── core/airspace/           # 공역 관리, 고도 레이어
│   ├── core/metrics/            # 성능 메트릭 수집
│   ├── ai/rl/                   # RL 환경, PPO 에이전트, 보상 함수
│   ├── ai/llm/                  # LLM 컨트롤러, 파서, 브리핑
│   ├── simulator/               # 드론 물리 시뮬레이션, 다중 드론, 시나리오
│   ├── models/                  # Pydantic 데이터 모델
│   └── db/                      # ORM 모델, CRUD, 마이그레이션
├── frontend/src/
│   ├── components/              # CesiumViewer, DroneTracker, Dashboard 등
│   ├── hooks/                   # useDroneState, useSimulation, useMultiSimulation
│   └── types/                   # TypeScript 인터페이스
├── cpp_engine/                  # C++17 고성능 모듈
├── tests/backend/               # 461+ pytest 테스트
└── docker-compose.yml
```

## API 레퍼런스

| 메서드 | 엔드포인트 | 설명 |
|--------|----------|------|
| GET | `/api/drones/` | 전체 드론 목록 조회 |
| POST | `/api/drones/` | 드론 등록 |
| GET | `/api/flight-plans/` | 비행계획 목록 조회 |
| POST | `/api/flight-plans/` | 비행계획 생성 (A*/RRT* 경로 계산) |
| GET | `/api/airspaces/` | 공역 구역 목록 조회 |
| POST | `/api/airspaces/` | 공역 구역 생성 |
| GET | `/api/weather/current` | 현재 기상 데이터 조회 |
| GET | `/api/scenarios/` | 시나리오 목록 조회 |
| GET | `/api/scenarios/{name}` | 시나리오 상세 조회 |
| GET | `/api/metrics/latest` | 최신 시뮬레이션 메트릭 조회 |
| POST | `/api/chat/` | LLM 관제 채팅 |
| WS | `/ws/telemetry` | 단일 드론 텔레메트리 스트림 |
| WS | `/ws/multi-telemetry` | 다중 드론 시뮬레이션 (DAA 포함) |

## 테스트

```bash
cd backend
python -m pytest ../tests/ -v                                    # 전체 테스트 (461+)
python -m pytest ../tests/backend/test_path_engine.py -v         # 단일 파일
python -m pytest ../tests/backend/test_path_engine.py::TestAStar::test_name -v  # 단일 테스트
```

## 라이선스

MIT
