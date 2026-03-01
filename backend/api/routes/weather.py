from fastapi import APIRouter

router = APIRouter()


@router.get("/current")
async def get_current_weather():
    """현재 기상 데이터 조회."""
    return {"message": "Not implemented"}
