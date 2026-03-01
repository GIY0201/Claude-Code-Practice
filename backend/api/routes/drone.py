"""드론 상태/제어 REST API."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import get_db
from db import crud
from models.drone import Drone, DroneCreate, DroneUpdate

router = APIRouter()


@router.get("/", response_model=list[Drone])
def list_drones(
    status: str | None = Query(None, description="상태 필터 (예: IDLE, AIRBORNE)"),
    db: Session = Depends(get_db),
):
    """모든 드론 상태 조회."""
    return crud.list_drones(db, status=status)


@router.post("/", response_model=Drone, status_code=201)
def create_drone(data: DroneCreate, db: Session = Depends(get_db)):
    """새 드론 등록."""
    return crud.create_drone(db, data)


@router.get("/{drone_id}", response_model=Drone)
def get_drone(drone_id: str, db: Session = Depends(get_db)):
    """특정 드론 상태 조회."""
    drone = crud.get_drone(db, drone_id)
    if drone is None:
        raise HTTPException(status_code=404, detail=f"Drone {drone_id} not found")
    return drone


@router.put("/{drone_id}", response_model=Drone)
def update_drone(drone_id: str, data: DroneUpdate, db: Session = Depends(get_db)):
    """드론 상태 업데이트."""
    drone = crud.update_drone(db, drone_id, data)
    if drone is None:
        raise HTTPException(status_code=404, detail=f"Drone {drone_id} not found")
    return drone


@router.delete("/{drone_id}", status_code=204)
def delete_drone(drone_id: str, db: Session = Depends(get_db)):
    """드론 삭제."""
    if not crud.delete_drone(db, drone_id):
        raise HTTPException(status_code=404, detail=f"Drone {drone_id} not found")
