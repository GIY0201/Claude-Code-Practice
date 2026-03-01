"""성능 메트릭 REST API."""

from fastapi import APIRouter, HTTPException

from models.metrics import MetricsSummary

router = APIRouter()

# 최근 시뮬레이션 메트릭 (WebSocket 핸들러에서 갱신)
_latest_metrics: MetricsSummary | None = None


def set_latest_metrics(metrics: MetricsSummary) -> None:
    """최근 메트릭을 갱신한다 (WebSocket 핸들러에서 호출)."""
    global _latest_metrics
    _latest_metrics = metrics


def get_latest_metrics() -> MetricsSummary | None:
    """최근 메트릭을 반환한다."""
    return _latest_metrics


@router.get("/latest", response_model=MetricsSummary)
async def latest_metrics():
    """마지막 시뮬레이션의 성능 메트릭을 반환한다."""
    if _latest_metrics is None:
        raise HTTPException(status_code=404, detail="No metrics available yet")
    return _latest_metrics
