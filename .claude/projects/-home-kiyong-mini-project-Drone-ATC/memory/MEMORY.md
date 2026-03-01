# SkyMind Project Memory

## 진행 상황
- **Phase 1 완료** (Sprint 0~3)
  - Sprint 0~1: 인프라 + 데이터 모델 + A* 경로 엔진 + 공역 관리 + DB/ORM/CRUD
  - Sprint 2 T2-1: REST API 3개 라우터 CRUD 연동 (28개 테스트)
  - Sprint 2 T2-2: DroneSim 단일 드론 시뮬레이터 (16개 테스트)
  - Sprint 2 T2-3: WebSocket 텔레메트리 스트리밍 (8개 테스트)
  - Sprint 3 T3-1~3: 프론트엔드 CesiumJS 연동 (DroneTracker, RouteRenderer, SimulationPanel, useSimulation 훅)
  - 총 75개 백엔드 테스트 통과, 프론트엔드 TypeScript + Vite 빌드 통과
- **Phase 1 완료 기준 충족:** 웹에서 3D 지도 위에 드론이 출발지→경유점→도착지로 비행하는 애니메이션
- **다음:** Phase 2 (다중 드론 + DAA 충돌 회피)

## 핵심 파일 위치
- 라우트: `backend/api/routes/{drone,flight_plan,airspace}.py`
- WebSocket: `backend/api/websocket/telemetry.py`
- CRUD: `backend/db/crud.py` (17개 함수)
- 시뮬레이터: `backend/simulator/drone_sim.py`
- 프론트 컴포넌트: `frontend/src/components/{CesiumViewer,DroneTracker,RouteRenderer,SimulationPanel}.tsx`
- 프론트 훅: `frontend/src/hooks/{useDroneState,useSimulation}.ts`
- 테스트 conftest: `tests/backend/conftest.py`

## 기술 패턴
- 백엔드 테스트: FastAPI TestClient + SQLite in-memory, conftest.py에서 DB 오버라이드
- 라우트: sync 핸들러, `Depends(get_db)` 주입
- WebSocket: asyncio.Task로 시뮬레이션 루프 실행, JSON 프로토콜 (start/stop/telemetry/completed)
- 프론트엔드: Zustand 스토어 → CesiumJS Entity 실시간 바인딩
- 시나리오: 한강/배송/단거리 3개 사전정의
