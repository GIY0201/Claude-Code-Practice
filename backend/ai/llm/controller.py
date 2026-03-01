"""LLM 기반 ATC(Air Traffic Controller) 관제사.

자연어 입력을 분석하여 의도를 분류하고, 적절한 핸들러로 디스패치한다.
비행계획 생성, 관제 명령, 상황 브리핑, NOTAM 설정 등을 처리.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

from models.chat import ChatIntent, ChatMessage, ChatRequest, ChatResponse
from ai.llm.client import LLMClient
from ai.llm.parser import FlightPlanParser
from ai.llm.briefing import BriefingGenerator, SystemState
from ai.llm.prompts.command import COMMAND_SYSTEM_PROMPT, COMMAND_TOOL
from core.airspace.notam import NOTAMParser

logger = logging.getLogger(__name__)


class ATCController:
    """AI 관제사 — 자연어 명령 디스패처."""

    def __init__(self, api_key: str = "") -> None:
        self._llm = LLMClient(api_key)
        self._parser = FlightPlanParser(api_key)
        self._briefing = BriefingGenerator(api_key)
        self._notam = NOTAMParser()
        self._history: dict[str, list[ChatMessage]] = {}
        self._system_state = SystemState()  # 외부에서 업데이트 가능

    @property
    def is_mock(self) -> bool:
        return self._llm.is_mock

    def set_system_state(self, state: SystemState) -> None:
        """브리핑용 시스템 상태 업데이트."""
        self._system_state = state

    def process(self, request: ChatRequest) -> ChatResponse:
        """사용자 메시지를 처리하고 응답을 반환한다.

        Args:
            request: 채팅 요청 (message, session_id)

        Returns:
            ChatResponse (intent, message, action, flight_plan, requires_confirmation)
        """
        session_id = request.session_id or str(uuid.uuid4())[:8]
        message = request.message.strip()

        # 이력 기록
        self._add_to_history(session_id, "user", message)

        # 의도 분류
        intent, classified = self._classify_intent(message)

        # 의도별 핸들러 디스패치
        if intent == ChatIntent.FLIGHT_PLAN:
            response = self._handle_flight_plan(message, session_id)
        elif intent == ChatIntent.BRIEFING:
            response = self._handle_briefing(session_id)
        elif intent == ChatIntent.SET_NOTAM:
            response = self._handle_notam(message, session_id, classified)
        elif intent in (
            ChatIntent.ALTITUDE_CHANGE,
            ChatIntent.SPEED_CHANGE,
            ChatIntent.HOLD,
            ChatIntent.RETURN_TO_BASE,
        ):
            response = self._handle_command(message, intent, session_id, classified)
        else:
            response = self._handle_general_query(message, session_id)

        # 응답 이력 기록
        self._add_to_history(session_id, "assistant", response.message)

        return response

    def get_history(self, session_id: str) -> list[ChatMessage]:
        """세션별 대화 이력을 반환한다."""
        return self._history.get(session_id, [])

    # ── 의도 분류 ──────────────────────────────────────

    def _classify_intent(self, message: str) -> tuple[ChatIntent, dict]:
        """메시지의 의도를 분류한다.

        Returns:
            (ChatIntent, 분류 결과 dict)
        """
        messages = [{"role": "user", "content": message}]
        result = self._llm.chat(
            messages=messages,
            tools=[COMMAND_TOOL],
            system=COMMAND_SYSTEM_PROMPT,
        )

        if result.get("type") == "tool_use" and result.get("name") == "classify_command":
            data = result.get("input", {})
            intent_str = data.get("intent", "GENERAL_QUERY")
            try:
                intent = ChatIntent(intent_str)
            except ValueError:
                intent = ChatIntent.GENERAL_QUERY
            return intent, data

        return ChatIntent.GENERAL_QUERY, {}

    # ── 핸들러 ────────────────────────────────────────

    def _handle_flight_plan(self, message: str, session_id: str) -> ChatResponse:
        """비행계획 생성 핸들링."""
        try:
            flight_plan = self._parser.parse(message)
            response_msg = (
                f"비행계획을 생성했습니다.\n"
                f"  출발: ({flight_plan.departure_position.lat:.4f}, "
                f"{flight_plan.departure_position.lon:.4f})\n"
                f"  도착: ({flight_plan.destination_position.lat:.4f}, "
                f"{flight_plan.destination_position.lon:.4f})\n"
                f"  고도: {flight_plan.cruise_altitude_m}m, "
                f"속도: {flight_plan.cruise_speed_ms}m/s\n"
                f"  드론: {flight_plan.drone_id}\n"
                f"비행계획을 승인하시겠습니까?"
            )
            return ChatResponse(
                intent=ChatIntent.FLIGHT_PLAN,
                message=response_msg,
                flight_plan=flight_plan,
                requires_confirmation=True,
                session_id=session_id,
            )
        except Exception as e:
            logger.error("비행계획 생성 실패: %s", e)
            return ChatResponse(
                intent=ChatIntent.FLIGHT_PLAN,
                message=f"비행계획 생성에 실패했습니다: {e}",
                session_id=session_id,
            )

    def _handle_briefing(self, session_id: str) -> ChatResponse:
        """상황 브리핑 핸들링."""
        briefing_text = self._briefing.generate(self._system_state)
        return ChatResponse(
            intent=ChatIntent.BRIEFING,
            message=briefing_text,
            session_id=session_id,
        )

    def _handle_notam(
        self, message: str, session_id: str, classified: dict,
    ) -> ChatResponse:
        """NOTAM 설정 핸들링."""
        try:
            zone = self._notam.parse_text(message)
            params = classified.get("parameters", {})
            action = {
                "type": "SET_NOTAM",
                "zone_name": zone.name,
                "zone_type": zone.zone_type.value,
                "restrictions": zone.restrictions,
            }
            if params.get("duration_minutes"):
                action["duration_minutes"] = params["duration_minutes"]

            response_msg = (
                f"NOTAM을 설정합니다.\n"
                f"  구역: {zone.name}\n"
                f"  유형: {zone.zone_type.value}\n"
                f"설정을 진행하시겠습니까?"
            )
            return ChatResponse(
                intent=ChatIntent.SET_NOTAM,
                message=response_msg,
                action=action,
                requires_confirmation=True,
                session_id=session_id,
            )
        except Exception as e:
            logger.error("NOTAM 설정 실패: %s", e)
            return ChatResponse(
                intent=ChatIntent.SET_NOTAM,
                message=f"NOTAM 설정에 실패했습니다: {e}",
                session_id=session_id,
            )

    def _handle_command(
        self, message: str, intent: ChatIntent, session_id: str, classified: dict,
    ) -> ChatResponse:
        """관제 명령 (고도/속도/홀딩/귀환) 핸들링."""
        drone_id = classified.get("drone_id")
        params = classified.get("parameters", {})
        confirmation = classified.get(
            "confirmation_message", "명령을 실행하시겠습니까?",
        )

        action = {
            "type": intent.value,
            "drone_id": drone_id,
            **params,
        }

        return ChatResponse(
            intent=intent,
            message=confirmation,
            action=action,
            requires_confirmation=True,
            session_id=session_id,
        )

    def _handle_general_query(self, message: str, session_id: str) -> ChatResponse:
        """일반 질의 핸들링."""
        # mock 모드에서는 간단한 응답
        response_text = (
            "질문을 이해했습니다. "
            "현재 시스템 상태를 확인하려면 '브리핑' 명령을 사용해주세요."
        )
        return ChatResponse(
            intent=ChatIntent.GENERAL_QUERY,
            message=response_text,
            session_id=session_id,
        )

    # ── 이력 관리 ─────────────────────────────────────

    def _add_to_history(self, session_id: str, role: str, content: str) -> None:
        """대화 이력에 메시지를 추가한다."""
        if session_id not in self._history:
            self._history[session_id] = []

        self._history[session_id].append(
            ChatMessage(
                role=role,
                content=content,
                timestamp=datetime.now(timezone.utc),
            )
        )
