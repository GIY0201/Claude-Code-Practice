"""성능 메트릭 수집기 + REST API 테스트."""

import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from core.metrics.collector import MetricsCollector, _haversine_m
from models.common import Position3D, Velocity3D
from models.telemetry import Telemetry
from models.metrics import MetricsSummary, DroneMetrics


# ── 헬퍼 ──────────────────────────────────────────────────────────────

def _make_telemetry(
    drone_id: str,
    lat: float = 37.5665,
    lon: float = 126.9780,
    alt_m: float = 100.0,
    battery: float = 100.0,
) -> Telemetry:
    return Telemetry(
        drone_id=drone_id,
        timestamp=datetime.now(timezone.utc),
        position=Position3D(lat=lat, lon=lon, alt_m=alt_m),
        velocity=Velocity3D(vx=0, vy=0, vz=0),
        heading=0.0,
        battery_percent=battery,
    )


# ── Haversine 테스트 ──────────────────────────────────────────────────

class TestHaversine:
    """Haversine 거리 계산 테스트."""

    def test_same_point(self):
        """동일 지점 거리 = 0."""
        p = Position3D(lat=37.5665, lon=126.9780, alt_m=100)
        assert _haversine_m(p, p) == 0.0

    def test_known_distance(self):
        """서울시청 → 강남역 약 8~9km."""
        p1 = Position3D(lat=37.5665, lon=126.9780, alt_m=0)
        p2 = Position3D(lat=37.4979, lon=127.0276, alt_m=0)
        d = _haversine_m(p1, p2)
        assert 8000 < d < 10000

    def test_short_distance(self):
        """작은 거리도 계산 가능."""
        p1 = Position3D(lat=37.5665, lon=126.9780, alt_m=0)
        p2 = Position3D(lat=37.5666, lon=126.9781, alt_m=0)
        d = _haversine_m(p1, p2)
        assert 0 < d < 20


# ── MetricsCollector 유닛 테스트 ──────────────────────────────────────

class TestMetricsCollector:
    """MetricsCollector 단위 테스트."""

    def test_empty_summary(self):
        """빈 수집기에서 기본 MetricsSummary 반환."""
        mc = MetricsCollector()
        s = mc.get_summary()
        assert isinstance(s, MetricsSummary)
        assert s.collision_avoidance_rate == 1.0
        assert s.total_distance_m == 0.0
        assert s.drone_metrics == {}

    def test_single_drone_single_tick(self):
        """단일 드론 단일 틱 기록."""
        mc = MetricsCollector()
        t = _make_telemetry("D1")
        mc.record_tick([t])
        s = mc.get_summary()
        assert len(s.drone_metrics) == 1
        assert "D1" in s.drone_metrics
        assert s.drone_metrics["D1"].total_distance_m == 0.0  # 첫 틱은 거리 0

    def test_distance_accumulation(self):
        """여러 틱에서 거리가 누적된다."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1", lat=37.5665, lon=126.9780)])
        mc.record_tick([_make_telemetry("D1", lat=37.5675, lon=126.9790)])
        mc.record_tick([_make_telemetry("D1", lat=37.5685, lon=126.9800)])
        s = mc.get_summary()
        assert s.drone_metrics["D1"].total_distance_m > 0
        assert s.total_distance_m > 0

    def test_battery_tracking(self):
        """배터리 소모 추적."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1", battery=100)])
        mc.record_tick([_make_telemetry("D1", battery=95)])
        mc.record_tick([_make_telemetry("D1", battery=90)])
        s = mc.get_summary()
        assert s.drone_metrics["D1"].battery_consumed == 10.0

    def test_conflict_recording(self):
        """충돌/회피 기록."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1")], conflict_count=2, avoidance_count=2)
        mc.record_tick([_make_telemetry("D1")], conflict_count=1, avoidance_count=1)
        s = mc.get_summary()
        assert s.total_conflicts_detected == 3
        assert s.total_avoidance_maneuvers == 3
        assert s.collision_avoidance_rate == 1.0

    def test_partial_avoidance(self):
        """부분 회피 시 회피율 < 1."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1")], conflict_count=4, avoidance_count=2)
        s = mc.get_summary()
        assert s.collision_avoidance_rate == 0.5

    def test_mission_completion(self):
        """미션 완료율 추적."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1"), _make_telemetry("D2")])
        mc.record_completion("D1")
        s = mc.get_summary()
        assert s.mission_completion_rate == 0.5
        assert s.drone_metrics["D1"].completed is True
        assert s.drone_metrics["D2"].completed is False

    def test_full_completion(self):
        """전체 미션 완료."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1"), _make_telemetry("D2")])
        mc.record_completion("D1")
        mc.record_completion("D2")
        s = mc.get_summary()
        assert s.mission_completion_rate == 1.0

    def test_duplicate_completion_ignored(self):
        """중복 완료 무시."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1")])
        mc.record_completion("D1")
        mc.record_completion("D1")  # 중복
        s = mc.get_summary()
        assert s.mission_completion_rate == 1.0

    def test_multi_drone(self):
        """다중 드론 메트릭."""
        mc = MetricsCollector()
        mc.record_tick([
            _make_telemetry("D1", lat=37.56, lon=126.97),
            _make_telemetry("D2", lat=37.57, lon=126.98),
        ])
        mc.record_tick([
            _make_telemetry("D1", lat=37.57, lon=126.98),
            _make_telemetry("D2", lat=37.58, lon=126.99),
        ])
        s = mc.get_summary()
        assert len(s.drone_metrics) == 2
        assert s.total_distance_m > 0

    def test_energy_efficiency(self):
        """에너지 효율 계산."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1", lat=37.5665, lon=126.978, battery=100)])
        mc.record_tick([_make_telemetry("D1", lat=37.5765, lon=126.988, battery=90)])
        s = mc.get_summary()
        # 배터리 10% 소모, 약 1.3km 이동 → ~130 m/%
        assert s.energy_efficiency > 0
        assert s.drone_metrics["D1"].battery_consumed == 10.0

    def test_route_efficiency(self):
        """경로 효율 계산 (직선 대비)."""
        mc = MetricsCollector()
        # 직선 이동: 효율 ≈ 1.0
        mc.record_tick([_make_telemetry("D1", lat=37.56, lon=126.97)])
        mc.record_tick([_make_telemetry("D1", lat=37.57, lon=126.98)])
        s = mc.get_summary()
        assert 0.9 <= s.route_efficiency <= 1.0  # 거의 직선

    def test_route_efficiency_detour(self):
        """우회 경로의 효율은 < 1."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1", lat=37.56, lon=126.97)])
        mc.record_tick([_make_telemetry("D1", lat=37.58, lon=126.97)])  # 북쪽으로 우회
        mc.record_tick([_make_telemetry("D1", lat=37.57, lon=126.98)])  # 목표 도달
        s = mc.get_summary()
        assert s.route_efficiency < 1.0

    def test_reset(self):
        """reset 후 초기 상태."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1")], conflict_count=5, avoidance_count=3)
        mc.record_completion("D1")
        mc.reset()
        s = mc.get_summary()
        assert s.total_distance_m == 0.0
        assert s.total_conflicts_detected == 0
        assert s.drone_metrics == {}

    def test_no_conflict_avoidance_rate_is_one(self):
        """충돌이 없으면 회피율 = 1.0."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1")])
        s = mc.get_summary()
        assert s.collision_avoidance_rate == 1.0

    def test_flight_time_tracking(self):
        """비행 시간 추적."""
        mc = MetricsCollector()
        mc.record_tick([_make_telemetry("D1")])
        mc.record_tick([_make_telemetry("D1")])
        s = mc.get_summary()
        assert s.avg_flight_time_sec >= 0

    def test_completion_nonexistent_drone(self):
        """존재하지 않는 드론 완료 → 무시."""
        mc = MetricsCollector()
        mc.record_completion("GHOST")
        s = mc.get_summary()
        assert s.mission_completion_rate == 0.0


# ── MetricsSummary 모델 테스트 ────────────────────────────────────────

class TestMetricsModels:
    """Pydantic 모델 테스트."""

    def test_metrics_summary_defaults(self):
        s = MetricsSummary()
        assert s.collision_avoidance_rate == 1.0
        assert s.route_efficiency == 1.0
        assert s.total_distance_m == 0.0
        assert s.drone_metrics == {}

    def test_drone_metrics_model(self):
        dm = DroneMetrics(
            drone_id="D1",
            total_distance_m=1234.5,
            ideal_distance_m=1000.0,
            route_efficiency=0.81,
            battery_consumed=15.5,
            flight_time_sec=120.0,
            completed=True,
        )
        assert dm.drone_id == "D1"
        assert dm.completed is True

    def test_summary_serialization(self):
        s = MetricsSummary(
            drone_metrics={"D1": DroneMetrics(drone_id="D1")}
        )
        data = s.model_dump(mode="json")
        assert "D1" in data["drone_metrics"]


# ── REST API 테스트 ───────────────────────────────────────────────────

class TestMetricsAPI:
    """메트릭 REST API 테스트."""

    @pytest.fixture(autouse=True)
    def client(self):
        from main import app
        self._client = TestClient(app)

    def test_no_metrics_yet(self):
        """메트릭 없을 때 404."""
        from api.routes.metrics import set_latest_metrics, _latest_metrics
        import api.routes.metrics as m
        original = m._latest_metrics
        m._latest_metrics = None
        try:
            resp = self._client.get("/api/metrics/latest")
            assert resp.status_code == 404
        finally:
            m._latest_metrics = original

    def test_latest_metrics(self):
        """메트릭 설정 후 조회."""
        from api.routes.metrics import set_latest_metrics
        summary = MetricsSummary(
            collision_avoidance_rate=0.95,
            route_efficiency=0.88,
            total_distance_m=5000.0,
        )
        set_latest_metrics(summary)
        try:
            resp = self._client.get("/api/metrics/latest")
            assert resp.status_code == 200
            data = resp.json()
            assert data["collision_avoidance_rate"] == 0.95
            assert data["route_efficiency"] == 0.88
            assert data["total_distance_m"] == 5000.0
        finally:
            import api.routes.metrics as m
            m._latest_metrics = None
