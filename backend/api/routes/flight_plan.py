"""비행계획 CRUD REST API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db import crud
from models.flight_plan import FlightPlan, FlightPlanCreate
from models.waypoint import WaypointCreate

router = APIRouter()


class StatusUpdate(BaseModel):
    """비행계획 상태 변경 요청."""
    status: str


@router.get("/", response_model=list[FlightPlan])
def list_flight_plans(
    status: str | None = Query(None, description="상태 필터 (예: DRAFT, APPROVED)"),
    drone_id: str | None = Query(None, description="드론 ID 필터"),
    db: Session = Depends(get_db),
):
    """모든 비행계획 조회."""
    return crud.list_flight_plans(db, status=status, drone_id=drone_id)


@router.post("/", response_model=FlightPlan, status_code=201)
def create_flight_plan(data: FlightPlanCreate, db: Session = Depends(get_db)):
    """새 비행계획 생성."""
    return crud.create_flight_plan(db, data)


@router.get("/{plan_id}", response_model=FlightPlan)
def get_flight_plan(plan_id: str, db: Session = Depends(get_db)):
    """특정 비행계획 조회."""
    plan = crud.get_flight_plan(db, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Flight plan {plan_id} not found")
    return plan


@router.patch("/{plan_id}/status", response_model=FlightPlan)
def update_flight_plan_status(
    plan_id: str, body: StatusUpdate, db: Session = Depends(get_db),
):
    """비행계획 상태 변경 (DRAFT → SUBMITTED → APPROVED → ACTIVE → COMPLETED)."""
    plan = crud.update_flight_plan_status(db, plan_id, body.status)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Flight plan {plan_id} not found")
    return plan


@router.post("/{plan_id}/waypoints", response_model=FlightPlan)
def add_waypoints(
    plan_id: str, waypoints: list[WaypointCreate], db: Session = Depends(get_db),
):
    """비행계획에 경유점 추가."""
    wp_dicts = [
        {
            "lat": wp.position.lat,
            "lon": wp.position.lon,
            "alt_m": wp.position.alt_m,
            "name": wp.name,
            "waypoint_type": wp.waypoint_type.value
            if hasattr(wp.waypoint_type, "value")
            else wp.waypoint_type,
        }
        for wp in waypoints
    ]
    plan = crud.add_waypoints_to_plan(db, plan_id, wp_dicts)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Flight plan {plan_id} not found")
    return plan


@router.delete("/{plan_id}", status_code=204)
def delete_flight_plan(plan_id: str, db: Session = Depends(get_db)):
    """비행계획 삭제."""
    if not crud.delete_flight_plan(db, plan_id):
        raise HTTPException(status_code=404, detail=f"Flight plan {plan_id} not found")
