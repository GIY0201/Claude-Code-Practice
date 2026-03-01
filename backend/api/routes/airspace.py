"""공역 관리 REST API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from db import crud
from models.airspace import AirspaceZone, AirspaceZoneCreate

router = APIRouter()


class ActiveUpdate(BaseModel):
    """공역 활성/비활성 변경 요청."""
    active: bool


@router.get("/", response_model=list[AirspaceZone])
def list_airspaces(
    active_only: bool = Query(True, description="활성 구역만 조회"),
    db: Session = Depends(get_db),
):
    """모든 공역 구역 조회."""
    return crud.list_airspace_zones(db, active_only=active_only)


@router.post("/", response_model=AirspaceZone, status_code=201)
def create_airspace(data: AirspaceZoneCreate, db: Session = Depends(get_db)):
    """공역 구역 생성."""
    return crud.create_airspace_zone(db, data)


@router.get("/{zone_id}", response_model=AirspaceZone)
def get_airspace(zone_id: str, db: Session = Depends(get_db)):
    """특정 공역 구역 조회."""
    zone = crud.get_airspace_zone(db, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Airspace zone {zone_id} not found")
    return zone


@router.patch("/{zone_id}/active", response_model=AirspaceZone)
def update_airspace_active(
    zone_id: str, body: ActiveUpdate, db: Session = Depends(get_db),
):
    """공역 구역 활성/비활성 전환."""
    zone = crud.update_airspace_zone_active(db, zone_id, body.active)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Airspace zone {zone_id} not found")
    return zone


@router.delete("/{zone_id}", status_code=204)
def delete_airspace(zone_id: str, db: Session = Depends(get_db)):
    """공역 구역 삭제."""
    if not crud.delete_airspace_zone(db, zone_id):
        raise HTTPException(status_code=404, detail=f"Airspace zone {zone_id} not found")
