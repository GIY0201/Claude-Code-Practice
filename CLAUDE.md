# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SkyMind is an AI-based UTM (UAV Traffic Management) system implementing real-world ATC concepts at drone scale. It handles autonomous path generation, collision avoidance (DAA), priority management, weather response, and emergency procedures for multiple drones.

Full project spec: `SKYMIND_PROJECT.md`. **Current status:** Phase 5 complete. All 5 phases implemented. 461 tests pass (3 skip).

## Build & Run Commands

```bash
# All commands assume project root: /home/kiyong/mini_project/Drone_ATC/

# ── Python backend ──
source .venv/bin/activate
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# ── Frontend ──
cd frontend
npm run dev          # Vite dev server (:5173), proxies /api→:8000, /ws→ws://:8000
npm run build        # tsc -b && vite build
npm run lint         # ESLint

# ── Docker (full stack) ──
docker-compose up --build   # db(:5432) + backend(:8000) + frontend(:5173)

# ── Database migrations ──
cd backend && alembic upgrade head

# ── Tests (IMPORTANT: run from backend/ directory) ──
cd backend
python -m pytest ../tests/ -v                                    # All (461 pass, 3 skip)
python -m pytest ../tests/backend/test_path_engine.py -v         # Single file
python -m pytest ../tests/backend/test_path_engine.py::TestAStar::test_name -v  # Single test

# ── C++ engine (optional, requires g++) ──
cd cpp_engine && mkdir -p build && cd build && cmake .. && make -j4
# If g++ unavailable, ai/cpp_bridge.py auto-falls back to Python implementations
```

## Architecture

### Backend (`backend/`)

FastAPI app in `main.py` mounts 7 REST routers + 1 WebSocket router. Configuration via pydantic-settings in `config.py` (auto-loads `.env`).

**Layer structure:**

```
API Layer          api/routes/*.py (REST CRUD)  +  api/websocket/telemetry.py (WS streaming)
                   ↓                                ↓
Domain Logic       core/path_engine/     A*, RRT*, optimizer
                   core/deconfliction/   CPA, avoidance, tactical DAA, strategic 4D
                   core/weather/         fetcher (OWM API + mock), analyzer, rerouter
                   core/emergency/       detector, handler, landing planner
                   core/airspace/        manager (GeoJSON polygon), altitude layers
                   core/metrics/         MetricsCollector (performance tracking)
                   ↓                                ↓
Simulation         simulator/drone_sim.py          single drone physics (Haversine WGS84)
                   simulator/multi_drone.py        N-drone + DAA integration
                   simulator/scenario.py           ScenarioManager (JSON scenario loader)
                   ↓                                ↓
AI/ML              ai/rl/environment.py            Gymnasium env (24D obs, 3D action)
                   ai/rl/{reward,agent,train}.py   PPO via SB3 + curriculum reward
                   ai/cpp_bridge.py                C++ engine wrapper with Python fallback
                   ai/llm/controller.py            LLM ATC controller (NL → commands)
                   ai/llm/parser.py                NL → FlightPlanCreate (Claude tool_use)
                   ai/llm/briefing.py              System state → Korean briefing
                   ai/llm/client.py                Anthropic API wrapper (mock mode)
                   ↓
Data               models/*.py (Pydantic)  ↔  db/orm_models.py (SQLAlchemy ORM)
                   db/crud.py (conversion: _*_orm_to_pydantic())
```

**Key design decisions:**
- Pydantic models (API contracts) are **separate** from ORM models (DB). Conversion in `crud.py`.
- WebSocket `/ws/multi-telemetry` runs the full simulation loop: `MultiDroneSim.tick_with_daa()` → telemetry + CPA + avoidance + emergency detection + weather (10s interval) + metrics collection. Sends `{"event": "metrics"}` on completion.
- `WeatherFetcher` auto-switches to mock mode when no `OPENWEATHER_API_KEY` is set.
- `EmergencyDetector` tracks per-drone state to prevent duplicate alerts; call `.update(telemetry)` (not `.check()`).
- `LLMClient` / all LLM modules auto-switch to mock mode when `ANTHROPIC_API_KEY` is empty (same pattern as `WeatherFetcher`).
- `NOTAMParser` converts natural language to `AirspaceZoneCreate` with circle polygon geometry.

### Frontend (`frontend/src/`)

React 18 + TypeScript + CesiumJS (resium) + Zustand + TailwindCSS, built with Vite.

**State flow:**
```
SimulationPanel → useSimulation / useMultiSimulation (WebSocket hooks)
                  → useDroneState (Zustand store: drones, trails, conflicts, weather, alerts)
                  → CesiumViewer (DroneTracker, RouteRenderer, WeatherOverlay, LandingZoneRenderer)
                  → Dashboard (WeatherPanel, ConflictPanel, EmergencyAlertPanel, DroneCards)
ChatPanel (floating, bottom-left) → REST /api/chat/message → ATCController → response display
```

**Vite proxy** (`vite.config.ts`): `/api` → `http://localhost:8000`, `/ws` → `ws://localhost:8000`.

### C++ Engine (`cpp_engine/`)

C++17 ports of A*, RRT*, path optimizer with pybind11 bindings (`skymind_cpp` module). Build requires `cmake` + `g++`. Python fallback via `ai/cpp_bridge.py` when the native module is unavailable.

### Tests (`tests/backend/`)

- `conftest.py`: SQLite in-memory DB, FastAPI `TestClient`, auto create/drop tables per test via `app.dependency_overrides[get_db]`.
- Tests add `backend/` to `sys.path` — must run from `backend/` directory.
- RL agent tests (PPO training) are CPU-intensive; use small `total_timesteps` and `max_steps` in test configs.

## Domain Rules

- **Coordinates:** WGS84 (EPSG:4326). Distances via Haversine. Meter conversion: `111320 * cos(lat)`.
- **Default region:** Seoul (37.5665°N, 126.9780°E).
- **Separation minimums:** horizontal 100m, vertical 30m.
- **Altitude layers:** East-bound (0°–180°) → odd layers, West-bound (180°–360°) → even layers. Range 30m–400m, 10m step.
- **Avoidance priority:** speed reduction → altitude change → lateral offset → hold.
- **Drone priority:** EMERGENCY > HIGH > NORMAL > LOW (lower priority yields).
- **Airspace zones:** RESTRICTED / CONTROLLED / FREE / EMERGENCY_ONLY.
- **Weather limits:** wind >20 m/s, rain >15 mm/h, visibility <500m → GROUNDED.

## Development Conventions

- Phased development: Phase N complete before Phase N+1 (see `SKYMIND_PROJECT.md`).
- Commits: Conventional Commits (`feat:`, `fix:`, `refactor:`).
- Language: Korean comments in source code, English API/types.

## Known Gotchas

- **Do NOT use `asyncio.to_thread` inside WebSocket handlers** — it deadlocks in Starlette's TestClient. Call sync functions directly (acceptable since weather fetcher uses mock/cache in tests).
- **Tests must run from `backend/`** directory: `cd backend && python -m pytest ../tests/ -v`. The `conftest.py` adds `backend/` to `sys.path`.
- **3 tests are expected to skip** (C++ engine not compiled) — this is normal when g++ is not installed.

## Environment Variables

See `.env.example`. Key settings:
- `DATABASE_URL` — PostgreSQL connection string
- `OPENWEATHER_API_KEY` — empty = mock mode (safe for dev/test)
- `VITE_CESIUM_ION_TOKEN` — CesiumJS Ion access token (frontend `.env`)
- `SIM_TICK_RATE_HZ` (default 10) — simulation ticks per second
- `SEPARATION_HORIZONTAL_M` (100), `SEPARATION_VERTICAL_M` (30) — DAA thresholds
- `ANTHROPIC_API_KEY` — empty = mock mode (safe for dev/test)
