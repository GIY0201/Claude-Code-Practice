# SkyMind — AI Drone Air Traffic Controller

AI-based UTM (UAV Traffic Management) system that implements real-world ATC concepts at drone scale. SkyMind autonomously generates flight paths, detects and resolves conflicts, responds to weather changes, and handles emergency procedures for multiple drones in real time.

## Features

- **Autonomous Path Planning** — A* and RRT* algorithms with path smoothing and shortcutting
- **Collision Avoidance (DAA)** — CPA-based conflict detection with tactical avoidance maneuvers (speed/altitude/lateral/hold)
- **Strategic Deconfliction** — Pre-flight 4D path conflict resolution with priority-based yielding
- **Airspace Management** — Zone-based airspace (RESTRICTED / CONTROLLED / FREE / EMERGENCY_ONLY) with altitude layer system
- **Weather Integration** — OpenWeatherMap API with dynamic rerouting based on wind, rain, and visibility
- **Emergency Management** — Battery/altitude/geofence monitoring, emergency landing zone search with obstacle-aware pathfinding
- **RL Path Optimization** — PPO agent (Stable-Baselines3) with curriculum reward shaping
- **LLM ATC Controller** — Natural language flight plan parsing, ATC chat, and situation briefing via Claude API
- **3D Visualization** — CesiumJS globe with real-time drone tracking, heading indicators, route rendering, airspace polygons, and weather overlay
- **Performance Metrics** — Real-time collision avoidance rate, route efficiency, energy efficiency, mission completion tracking
- **Scenario Simulator** — Pre-built scenarios (delivery, surveillance, emergency) with configurable multi-drone simulations
- **C++ Engine** — Optional high-performance A*/RRT*/CPA via pybind11 (auto-fallback to Python)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React 18 + CesiumJS + Zustand + TailwindCSS) │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────┐ │
│  │CesiumView│ │ Dashboard │ │SimPanel  │ │ ChatPanel │ │
│  │ Drones   │ │ Conflicts │ │ Scenarios│ │ LLM ATC   │ │
│  │ Routes   │ │ Weather   │ │ Controls │ │           │ │
│  │ Airspace │ │ Metrics   │ │          │ │           │ │
│  └────┬─────┘ └─────┬─────┘ └────┬─────┘ └─────┬─────┘ │
│       └──────────────┴───────────┬┴──────────────┘       │
│                     WebSocket + REST                     │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────┐
│              Backend (FastAPI + Python 3.11+)            │
│                                                          │
│  API Layer:  REST CRUD + WebSocket Telemetry             │
│  ┌───────────────────────────────────────────────┐       │
│  │ Path Engine │ DAA Engine │ Weather │ Emergency │       │
│  │ A* / RRT*   │ CPA+Avoid │ Fetch   │ Detect    │       │
│  │ Optimizer   │ Tactical  │ Analyze │ Handle    │       │
│  │             │ Strategic │ Reroute │ Landing   │       │
│  └───────────────────────────────────────────────┘       │
│  ┌─────────────┐ ┌─────────────┐ ┌──────────────┐       │
│  │ RL Agent    │ │ LLM Module  │ │ Simulator    │       │
│  │ PPO/SB3    │ │ Claude API  │ │ Multi-drone  │       │
│  │ Gymnasium  │ │ LangChain   │ │ Scenarios    │       │
│  └─────────────┘ └─────────────┘ └──────────────┘       │
│                                                          │
│  ┌────────────────┐  ┌────────────────────────┐          │
│  │ PostgreSQL     │  │ C++ Engine (optional)  │          │
│  │ + PostGIS      │  │ pybind11 bindings      │          │
│  └────────────────┘  └────────────────────────┘          │
└──────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16 with PostGIS (or Docker)

### Installation

```bash
# Clone
git clone <repo-url> && cd Drone_ATC

# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt

# Frontend
cd frontend && npm install && cd ..

# Environment
cp .env.example .env
# Edit .env with your API keys:
#   OPENWEATHER_API_KEY  (optional — mock mode if empty)
#   ANTHROPIC_API_KEY    (for LLM chat features)
#   CESIUM_ION_TOKEN     (for 3D map tiles)

# Database
cd backend && alembic upgrade head && cd ..
```

### Running

```bash
# Terminal 1 — Backend
source .venv/bin/activate
cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd frontend && npm run dev
# Open http://localhost:5173
```

### Docker

```bash
docker-compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, CesiumJS (Resium), Zustand, TailwindCSS, Vite |
| Backend | FastAPI, Python 3.11+, Pydantic, SQLAlchemy, WebSocket |
| AI/ML | PyTorch, Stable-Baselines3 (PPO), Gymnasium |
| LLM | Anthropic Claude API |
| Database | PostgreSQL 16 + PostGIS |
| C++ Engine | C++17, pybind11, CMake |
| Weather | OpenWeatherMap API |
| Container | Docker + Docker Compose |

## Project Structure

```
Drone_ATC/
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Environment configuration
│   ├── api/routes/              # REST endpoints (drone, flight_plan, airspace, weather, chat, scenario, metrics)
│   ├── api/websocket/           # WebSocket telemetry streaming
│   ├── core/path_engine/        # A*, RRT*, path optimizer
│   ├── core/deconfliction/      # CPA, avoidance, tactical DAA, strategic 4D
│   ├── core/weather/            # Fetcher, analyzer, dynamic rerouter
│   ├── core/emergency/          # Detector, handler, landing planner
│   ├── core/airspace/           # Zone manager, altitude layers
│   ├── core/metrics/            # Performance metrics collector
│   ├── ai/rl/                   # RL environment, PPO agent, reward shaping
│   ├── ai/llm/                  # LLM controller, parser, briefing
│   ├── simulator/               # Drone physics sim, multi-drone, scenarios
│   ├── models/                  # Pydantic data models
│   └── db/                      # ORM models, CRUD, migrations
├── frontend/src/
│   ├── components/              # CesiumViewer, DroneTracker, Dashboard, etc.
│   ├── hooks/                   # useDroneState, useSimulation, useMultiSimulation
│   └── types/                   # TypeScript interfaces
├── cpp_engine/                  # C++17 high-performance modules
├── tests/backend/               # 461+ pytest tests
└── docker-compose.yml
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/drones/` | List all drones |
| POST | `/api/drones/` | Register a drone |
| GET | `/api/flight-plans/` | List flight plans |
| POST | `/api/flight-plans/` | Create flight plan with A*/RRT* path |
| GET | `/api/airspaces/` | List airspace zones |
| POST | `/api/airspaces/` | Create airspace zone |
| GET | `/api/weather/current` | Current weather data |
| GET | `/api/scenarios/` | List available scenarios |
| GET | `/api/scenarios/{name}` | Get scenario details |
| GET | `/api/metrics/latest` | Latest simulation metrics |
| POST | `/api/chat/` | LLM ATC chat |
| WS | `/ws/telemetry` | Single drone telemetry stream |
| WS | `/ws/multi-telemetry` | Multi-drone simulation with DAA |

## Testing

```bash
cd backend
python -m pytest ../tests/ -v                 # All tests (461+)
python -m pytest ../tests/backend/test_path_engine.py -v   # Single file
```

## License

MIT
