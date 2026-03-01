# CLAUDE.md

이 파일은 Claude Code (claude.ai/code)가 이 저장소에서 작업할 때 참고하는 가이드입니다.

## 프로젝트 개요

SkyMind는 실제 항공 ATC 개념을 드론 스케일로 구현한 AI 기반 UTM(UAV Traffic Management) 시스템입니다. 자율 경로 생성, 충돌 회피(DAA), 우선순위 관리, 기상 대응, 비상 처리 등을 다수 드론에 대해 수행합니다.

전체 프로젝트 스펙: `SKYMIND_PROJECT.md`. **현재 상태:** Phase 5 완료. 전체 5단계 구현 완료. 461 테스트 통과 (3개 스킵).

## 빌드 및 실행 명령어

```bash
# 모든 명령어는 프로젝트 루트 기준: /home/kiyong/mini_project/Drone_ATC/

# ── Python 백엔드 ──
source .venv/bin/activate
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# ── 프론트엔드 ──
cd frontend
npm run dev          # Vite 개발 서버 (:5173), /api→:8000, /ws→ws://:8000 프록시
npm run build        # tsc -b && vite build
npm run lint         # ESLint

# ── Docker (풀 스택) ──
docker-compose up --build   # db(:5432) + backend(:8000) + frontend(:5173)

# ── 데이터베이스 마이그레이션 ──
cd backend && alembic upgrade head

# ── 테스트 (중요: backend/ 디렉토리에서 실행) ──
cd backend
python -m pytest ../tests/ -v                                    # 전체 (461 통과, 3 스킵)
python -m pytest ../tests/backend/test_path_engine.py -v         # 단일 파일
python -m pytest ../tests/backend/test_path_engine.py::TestAStar::test_name -v  # 단일 테스트

# ── C++ 엔진 (선택사항, g++ 필요) ──
cd cpp_engine && mkdir -p build && cd build && cmake .. && make -j4
# g++ 미설치 시 ai/cpp_bridge.py가 자동으로 Python 구현으로 폴백
```

## 아키텍처

### 백엔드 (`backend/`)

`main.py`의 FastAPI 앱이 7개 REST 라우터 + 1개 WebSocket 라우터를 마운트. `config.py`에서 pydantic-settings로 설정 (`.env` 자동 로드).

**계층 구조:**

```
API 계층           api/routes/*.py (REST CRUD)  +  api/websocket/telemetry.py (WS 스트리밍)
                   ↓                                ↓
도메인 로직        core/path_engine/     A*, RRT*, 최적화
                   core/deconfliction/   CPA, 회피, 전술적 DAA, 전략적 4D
                   core/weather/         수집 (OWM API + mock), 분석, 재경로
                   core/emergency/       감지, 처리, 착륙 경로
                   core/airspace/        관리 (GeoJSON 폴리곤), 고도 레이어
                   core/metrics/         MetricsCollector (성능 추적)
                   ↓                                ↓
시뮬레이션         simulator/drone_sim.py          단일 드론 물리 (Haversine WGS84)
                   simulator/multi_drone.py        N대 드론 + DAA 통합
                   simulator/scenario.py           ScenarioManager (JSON 시나리오 로더)
                   ↓                                ↓
AI/ML              ai/rl/environment.py            Gymnasium 환경 (24D 관측, 3D 행동)
                   ai/rl/{reward,agent,train}.py   PPO (SB3) + 커리큘럼 보상
                   ai/cpp_bridge.py                C++ 엔진 래퍼 (Python 폴백)
                   ai/llm/controller.py            LLM 관제사 (자연어 → 명령)
                   ai/llm/parser.py                자연어 → FlightPlanCreate (Claude tool_use)
                   ai/llm/briefing.py              시스템 상태 → 한국어 브리핑
                   ai/llm/client.py                Anthropic API 래퍼 (mock 모드)
                   ↓
데이터             models/*.py (Pydantic)  ↔  db/orm_models.py (SQLAlchemy ORM)
                   db/crud.py (변환: _*_orm_to_pydantic())
```

**주요 설계 결정:**
- Pydantic 모델(API 계약)과 ORM 모델(DB)은 **분리**. `crud.py`에서 변환.
- WebSocket `/ws/multi-telemetry`가 전체 시뮬레이션 루프 실행: `MultiDroneSim.tick_with_daa()` → 텔레메트리 + CPA + 회피 + 비상 감지 + 기상 (10초 주기) + 메트릭 수집. 완료 시 `{"event": "metrics"}` 전송.
- `WeatherFetcher`는 `OPENWEATHER_API_KEY` 미설정 시 자동으로 mock 모드 전환.
- `EmergencyDetector`는 드론별 상태를 추적하여 중복 알림 방지. `.update(telemetry)` 호출 (`.check()` 아님).
- `LLMClient` / 모든 LLM 모듈은 `ANTHROPIC_API_KEY` 비어있으면 mock 모드 전환 (`WeatherFetcher`와 동일 패턴).
- `NOTAMParser`는 자연어를 원형 폴리곤 geometry의 `AirspaceZoneCreate`로 변환.

### 프론트엔드 (`frontend/src/`)

React 18 + TypeScript + CesiumJS (resium) + Zustand + TailwindCSS, Vite로 빌드.

**상태 흐름:**
```
SimulationPanel → useSimulation / useMultiSimulation (WebSocket 훅)
                  → useDroneState (Zustand 스토어: drones, trails, conflicts, weather, alerts)
                  → CesiumViewer (DroneTracker, RouteRenderer, WeatherOverlay, LandingZoneRenderer, AirspaceLayer)
                  → Dashboard (WeatherPanel, ConflictPanel, EmergencyAlertPanel, MetricsPanel, DroneCards)
ChatPanel (플로팅, 좌측 하단) → REST /api/chat/message → ATCController → 응답 표시
```

**Vite 프록시** (`vite.config.ts`): `/api` → `http://localhost:8000`, `/ws` → `ws://localhost:8000`.

### C++ 엔진 (`cpp_engine/`)

A*, RRT*, 경로 최적화의 C++17 포팅 + pybind11 바인딩 (`skymind_cpp` 모듈). `cmake` + `g++` 필요. 네이티브 모듈 미사용 시 `ai/cpp_bridge.py`가 Python으로 자동 폴백.

### 테스트 (`tests/backend/`)

- `conftest.py`: SQLite 인메모리 DB, FastAPI `TestClient`, 테스트별 자동 테이블 생성/삭제 (`app.dependency_overrides[get_db]`).
- 테스트가 `backend/`를 `sys.path`에 추가 — **반드시 `backend/` 디렉토리에서 실행**.
- RL 에이전트 테스트 (PPO 학습)는 CPU 부하가 큼. 테스트 설정에서 작은 `total_timesteps`와 `max_steps` 사용.

## 도메인 규칙

- **좌표계:** WGS84 (EPSG:4326). 거리 계산은 Haversine. 미터 변환: `111320 * cos(lat)`.
- **기본 지역:** 서울 (37.5665°N, 126.9780°E).
- **분리 최소값:** 수평 100m, 수직 30m.
- **고도 레이어:** 동향 (0°–180°) → 홀수 레이어, 서향 (180°–360°) → 짝수 레이어. 범위 30m–400m, 10m 단위.
- **회피 우선순위:** 속도 감소 → 고도 변경 → 수평 오프셋 → 정지.
- **드론 우선순위:** EMERGENCY > HIGH > NORMAL > LOW (낮은 우선순위가 양보).
- **공역 구역:** RESTRICTED / CONTROLLED / FREE / EMERGENCY_ONLY.
- **기상 제한:** 풍속 >20 m/s, 강수 >15 mm/h, 시정 <500m → GROUNDED.

## 개발 규칙

- 단계적 개발: Phase N 완료 후 Phase N+1 진행 (`SKYMIND_PROJECT.md` 참조).
- 커밋: Conventional Commits (`feat:`, `fix:`, `refactor:`).
- 언어: 소스 코드 주석은 한국어, API/타입은 영어.

## 주의사항

- **WebSocket 핸들러에서 `asyncio.to_thread` 사용 금지** — Starlette TestClient에서 데드락 발생. 동기 함수 직접 호출 (기상 수집기는 테스트에서 mock/캐시 사용하므로 문제 없음).
- **테스트는 반드시 `backend/` 디렉토리에서 실행**: `cd backend && python -m pytest ../tests/ -v`. `conftest.py`가 `backend/`를 `sys.path`에 추가함.
- **3개 테스트 스킵은 정상** (C++ 엔진 미컴파일) — g++ 미설치 시 나타나는 정상 동작.

## 환경 변수

`.env.example` 참조. 주요 설정:
- `DATABASE_URL` — PostgreSQL 연결 문자열
- `OPENWEATHER_API_KEY` — 비어있으면 mock 모드 (개발/테스트에 안전)
- `VITE_CESIUM_ION_TOKEN` — CesiumJS Ion 접근 토큰 (프론트엔드 `.env`)
- `SIM_TICK_RATE_HZ` (기본값 10) — 시뮬레이션 틱 속도
- `SEPARATION_HORIZONTAL_M` (100), `SEPARATION_VERTICAL_M` (30) — DAA 임계값
- `ANTHROPIC_API_KEY` — 비어있으면 mock 모드 (개발/테스트에 안전)
