"""성능 메트릭 데이터 모델."""

from pydantic import BaseModel, Field


class DroneMetrics(BaseModel):
    """개별 드론 성능 메트릭."""
    drone_id: str
    total_distance_m: float = 0.0
    ideal_distance_m: float = 0.0
    route_efficiency: float = 0.0
    battery_consumed: float = 0.0
    flight_time_sec: float = 0.0
    completed: bool = False


class MetricsSummary(BaseModel):
    """시뮬레이션 전체 성능 메트릭 요약."""
    collision_avoidance_rate: float = Field(1.0, ge=0, le=1, description="충돌 회피율 (0~1)")
    route_efficiency: float = Field(1.0, ge=0, description="경로 효율 (actual/ideal, 1=직선)")
    avg_response_time_ms: float = Field(0.0, ge=0, description="평균 응답 시간 (ms)")
    energy_efficiency: float = Field(0.0, ge=0, description="에너지 효율 (m/%)")
    mission_completion_rate: float = Field(0.0, ge=0, le=1, description="미션 완료율 (0~1)")
    avg_flight_time_sec: float = Field(0.0, ge=0, description="평균 비행 시간 (초)")
    total_conflicts_detected: int = Field(0, ge=0, description="총 충돌 감지 수")
    total_avoidance_maneuvers: int = Field(0, ge=0, description="총 회피 기동 수")
    total_distance_m: float = Field(0.0, ge=0, description="총 비행 거리 (m)")
    drone_metrics: dict[str, DroneMetrics] = Field(default_factory=dict)
