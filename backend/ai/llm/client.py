"""Anthropic Claude API 래퍼.

ANTHROPIC_API_KEY가 비어있으면 mock 모드로 동작하여
테스트 환경에서 API 호출 없이 결정론적 응답을 반환한다.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class LLMClient:
    """Claude API 클라이언트 (mock 모드 지원)."""

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._mock = not bool(api_key)
        self._client: Any = None

        if not self._mock:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
            except Exception:
                logger.warning("Anthropic SDK 초기화 실패 — mock 모드로 전환")
                self._mock = True

        if self._mock:
            logger.info("LLMClient: mock 모드 (ANTHROPIC_API_KEY 미설정)")

    @property
    def is_mock(self) -> bool:
        return self._mock

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        system: str = "",
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
    ) -> dict:
        """Claude API 호출 또는 mock 응답 반환.

        Returns:
            {"type": "text", "text": "..."} 또는
            {"type": "tool_use", "name": "...", "input": {...}}
        """
        if self._mock:
            return self._mock_response(messages, tools)

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        response = self._client.messages.create(**kwargs)

        # tool_use 블록 우선 반환
        for block in response.content:
            if block.type == "tool_use":
                return {
                    "type": "tool_use",
                    "name": block.name,
                    "input": block.input,
                }

        # 텍스트 블록 반환
        for block in response.content:
            if block.type == "text":
                return {"type": "text", "text": block.text}

        return {"type": "text", "text": ""}

    # ── Mock 응답 ──────────────────────────────────────────

    def _mock_response(
        self, messages: list[dict], tools: list[dict] | None,
    ) -> dict:
        """키워드 기반 mock 응답을 반환한다."""
        user_text = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    # content가 블록 리스트인 경우
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            user_text = block["text"]
                            break
                else:
                    user_text = content
                break

        user_lower = user_text.lower()

        if tools:
            tool_names = [t["name"] for t in tools]

            # 비행계획 파싱 요청
            if "extract_flight_plan" in tool_names:
                return self._mock_flight_plan_extraction(user_text)

            # 명령 분류 요청
            if "classify_command" in tool_names:
                return self._mock_command_classification(user_text)

        # 브리핑 요청
        if any(kw in user_lower for kw in ["브리핑", "상황", "현황"]):
            return self._mock_briefing_text(user_text)

        return {"type": "text", "text": "명령을 이해했습니다. 처리하겠습니다."}

    def _mock_flight_plan_extraction(self, text: str) -> dict:
        """비행계획 파싱 mock — 키워드에서 출발/도착지 추출."""
        # 프롬프트 래핑에서 원본 텍스트 추출 시도
        input_match = re.search(r'입력:\s*"(.+?)"', text)
        if input_match:
            text = input_match.group(1)

        # 간단한 패턴: "A에서 B까지" 또는 "A → B"
        departure = "서울역"
        destination = "강남역"

        # "에서 ... 까지" 패턴
        match = re.search(r"(\S+?)에서\s+(\S+?)까지", text)
        if match:
            departure = match.group(1)
            destination = match.group(2)

        # 고도 추출
        altitude = 100.0
        alt_match = re.search(r"고도\s*(\d+)", text)
        if alt_match:
            altitude = float(alt_match.group(1))

        # 속도 추출
        speed = 10.0
        spd_match = re.search(r"속도\s*(\d+)", text)
        if spd_match:
            speed = float(spd_match.group(1))

        # 미션 타입 추출
        mission = "DELIVERY"
        if any(kw in text for kw in ["감시", "순찰", "모니터링"]):
            mission = "SURVEILLANCE"
        elif any(kw in text for kw in ["점검", "검사", "촬영"]):
            mission = "INSPECTION"
        elif any(kw in text for kw in ["비상", "긴급", "응급"]):
            mission = "EMERGENCY_RESPONSE"

        # 우선순위
        priority = "NORMAL"
        if any(kw in text for kw in ["긴급", "비상"]):
            priority = "EMERGENCY"
        elif any(kw in text for kw in ["높은 우선", "우선"]):
            priority = "HIGH"

        # notes
        notes = ""
        note_match = re.search(r"(한강|위로|경유|통해)", text)
        if note_match:
            notes = text

        result: dict[str, Any] = {
            "departure": departure,
            "destination": destination,
            "cruise_altitude_m": altitude,
            "cruise_speed_ms": speed,
            "priority": priority,
            "mission_type": mission,
        }
        if notes:
            result["notes"] = notes

        return {"type": "tool_use", "name": "extract_flight_plan", "input": result}

    def _mock_command_classification(self, text: str) -> dict:
        """관제 명령 분류 mock."""
        text_lower = text.lower()

        # 의도 판별
        intent = "GENERAL_QUERY"
        drone_id = None
        params: dict[str, Any] = {}
        confirmation = "명령을 처리하겠습니다."

        # 드론 ID 추출
        id_match = re.search(r"드론\s*(\d+)번", text)
        if id_match:
            drone_id = f"D{id_match.group(1)}"
        sky_match = re.search(r"(SKY-\d+)", text, re.IGNORECASE)
        if sky_match:
            drone_id = sky_match.group(1).upper()
        if any(kw in text_lower for kw in ["전체", "모든"]):
            drone_id = "ALL"

        if any(kw in text_lower for kw in ["비행계획", "배송", "보내"]):
            intent = "FLIGHT_PLAN"
            confirmation = "비행계획 생성을 시작합니다."
        elif any(kw in text_lower for kw in ["고도"]):
            intent = "ALTITUDE_CHANGE"
            if any(kw in text_lower for kw in ["올려", "상승", "높"]):
                params["direction"] = "UP"
            else:
                params["direction"] = "DOWN"
            val_match = re.search(r"(\d+)\s*m", text)
            if val_match:
                params["target_value"] = float(val_match.group(1))
            confirmation = f"{'드론 ' + drone_id if drone_id else '드론'} 고도 변경을 실행합니다."
        elif any(kw in text_lower for kw in ["속도"]):
            intent = "SPEED_CHANGE"
            if any(kw in text_lower for kw in ["줄여", "감속", "낮"]):
                params["direction"] = "DOWN"
            else:
                params["direction"] = "UP"
            val_match = re.search(r"(\d+)", text)
            if val_match:
                params["target_value"] = float(val_match.group(1))
            confirmation = f"{'드론 ' + drone_id if drone_id else '드론'} 속도 변경을 실행합니다."
        elif any(kw in text_lower for kw in ["홀딩", "대기", "정지"]):
            intent = "HOLD"
            confirmation = f"{'드론 ' + drone_id if drone_id else '전체 드론'} 홀딩 명령을 실행합니다."
        elif any(kw in text_lower for kw in ["귀환", "복귀", "rtl"]):
            intent = "RETURN_TO_BASE"
            confirmation = f"{'드론 ' + drone_id if drone_id else '드론'} 귀환 명령을 실행합니다."
        elif any(kw in text_lower for kw in ["비행금지", "notam", "제한구역"]):
            intent = "SET_NOTAM"
            dur_match = re.search(r"(\d+)\s*분", text)
            if dur_match:
                params["duration_minutes"] = float(dur_match.group(1))
            zone_match = re.search(r"([A-Z가-힣]+구역)", text)
            if zone_match:
                params["zone_name"] = zone_match.group(1)
            confirmation = "비행금지구역 설정을 실행합니다."
        elif any(kw in text_lower for kw in ["브리핑", "상황", "현황", "요약"]):
            intent = "BRIEFING"
            confirmation = "현재 상황 브리핑을 생성합니다."

        result: dict[str, Any] = {
            "intent": intent,
            "confirmation_message": confirmation,
        }
        if drone_id:
            result["drone_id"] = drone_id
        if params:
            result["parameters"] = params

        return {"type": "tool_use", "name": "classify_command", "input": result}

    def _mock_briefing_text(self, text: str) -> dict:
        """브리핑 텍스트 mock."""
        return {
            "type": "text",
            "text": (
                "현재 SkyMind 시스템 상황 브리핑입니다.\n"
                "전체적으로 정상 운항 중이며, 특이사항 없습니다."
            ),
        }
