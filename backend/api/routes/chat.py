"""LLM 관제사 채팅 REST API.

자연어 명령 처리, 상황 브리핑, 대화 이력 조회를 제공한다.
"""

from fastapi import APIRouter, HTTPException

from config import settings
from models.chat import ChatRequest, ChatResponse, ChatMessage, CommandHistory
from ai.llm.controller import ATCController
from ai.llm.briefing import SystemState

router = APIRouter()

# 싱글턴 컨트롤러 (앱 수명 동안 유지)
_controller = ATCController(api_key=settings.ANTHROPIC_API_KEY)


def get_controller() -> ATCController:
    """ATCController 인스턴스를 반환한다 (테스트에서 교체 가능)."""
    return _controller


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest) -> ChatResponse:
    """LLM 관제사에게 자연어 메시지를 전송한다.

    지원 명령:
    - 비행계획 생성: "홍대에서 강남역까지 드론 배송, 고도 120m"
    - 고도 변경: "드론 3번 고도 올려"
    - 속도 변경: "드론 5번 속도 줄여"
    - 홀딩: "전체 드론 홀딩"
    - 귀환: "드론 2번 귀환시켜"
    - NOTAM 설정: "A구역 비행금지 설정, 30분"
    - 브리핑: "현재 상황 브리핑해줘"
    """
    ctrl = get_controller()
    return ctrl.process(request)


@router.post("/briefing")
async def get_briefing(
    active_drones: int = 0,
    holding_drones: int = 0,
) -> dict:
    """현재 시스템 상황 브리핑을 생성한다.

    Query params로 현재 상태를 전달하면 해당 상태 기반 브리핑을 생성.
    미전달 시 컨트롤러의 내부 상태를 사용.
    """
    ctrl = get_controller()

    if active_drones or holding_drones:
        state = SystemState(
            active_drones=active_drones,
            holding_drones=holding_drones,
        )
        ctrl.set_system_state(state)

    from models.chat import ChatRequest
    req = ChatRequest(message="상황 브리핑")
    resp = ctrl.process(req)
    return {"briefing": resp.message}


@router.get("/history/{session_id}", response_model=CommandHistory)
async def get_history(session_id: str) -> CommandHistory:
    """세션별 대화 이력을 조회한다."""
    ctrl = get_controller()
    messages = ctrl.get_history(session_id)
    return CommandHistory(session_id=session_id, messages=messages)
