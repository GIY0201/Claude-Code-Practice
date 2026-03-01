"""LLM 채팅 관련 데이터 모델."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .flight_plan import FlightPlanCreate


class ChatIntent(str, Enum):
    """LLM이 판별하는 사용자 의도 유형."""
    FLIGHT_PLAN = "FLIGHT_PLAN"
    ALTITUDE_CHANGE = "ALTITUDE_CHANGE"
    SPEED_CHANGE = "SPEED_CHANGE"
    HOLD = "HOLD"
    RETURN_TO_BASE = "RETURN_TO_BASE"
    SET_NOTAM = "SET_NOTAM"
    BRIEFING = "BRIEFING"
    GENERAL_QUERY = "GENERAL_QUERY"


class ChatMessage(BaseModel):
    """단일 채팅 메시지."""
    role: str = Field(..., description="user / assistant / system")
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """채팅 요청."""
    message: str = Field(..., min_length=1, description="사용자 입력 메시지")
    session_id: str | None = Field(None, description="세션 ID (없으면 자동 생성)")


class ChatResponse(BaseModel):
    """채팅 응답."""
    intent: ChatIntent
    message: str = Field(..., description="관제사 응답 메시지 (한국어)")
    action: dict | None = Field(None, description="실행된 또는 제안된 액션 상세")
    flight_plan: FlightPlanCreate | None = Field(None, description="생성된 비행계획 (FLIGHT_PLAN intent)")
    requires_confirmation: bool = Field(False, description="사용자 확인 필요 여부")
    session_id: str = Field(..., description="세션 ID")


class CommandHistory(BaseModel):
    """세션별 명령 이력."""
    session_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
