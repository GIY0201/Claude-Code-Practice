"""시나리오 REST API."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from simulator.scenario import ScenarioManager

router = APIRouter()
_manager = ScenarioManager()


class ScenarioInfoResponse(BaseModel):
    name: str
    description: str
    drone_count: int


@router.get("/", response_model=list[ScenarioInfoResponse])
async def list_scenarios():
    """사용 가능한 시나리오 목록을 반환한다."""
    scenarios = _manager.list_scenarios()
    return [
        ScenarioInfoResponse(
            name=s.name,
            description=s.description,
            drone_count=s.drone_count,
        )
        for s in scenarios
    ]


@router.get("/{name}")
async def get_scenario(name: str):
    """시나리오 상세 정보를 반환한다."""
    try:
        return _manager.get_scenario_raw(name)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {name}")
