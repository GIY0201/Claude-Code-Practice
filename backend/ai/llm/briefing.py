"""상황 브리핑 생성기.

현재 시스템 상태(운항 드론, 충돌, 기상, 비상, 공역 제한)를
Claude API (또는 mock)로 분석하여 한국어 자연어 브리핑을 생성한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ai.llm.client import LLMClient
from ai.llm.prompts.briefing import BRIEFING_SYSTEM_PROMPT, build_briefing_user_prompt

logger = logging.getLogger(__name__)


@dataclass
class SystemState:
    """브리핑 생성에 필요한 시스템 상태 스냅샷."""
    active_drones: int = 0
    holding_drones: int = 0
    emergency_drones: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    weather: dict | None = None
    airspace_restrictions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """프롬프트 빌드용 dict 변환."""
        return {
            "active_drones": self.active_drones,
            "holding_drones": self.holding_drones,
            "emergency_drones": self.emergency_drones,
            "conflicts": self.conflicts,
            "weather": self.weather,
            "airspace_restrictions": self.airspace_restrictions,
        }


class BriefingGenerator:
    """시스템 상태 → 한국어 상황 브리핑 생성."""

    def __init__(self, api_key: str = "") -> None:
        self._llm = LLMClient(api_key)

    @property
    def is_mock(self) -> bool:
        return self._llm.is_mock

    def generate(self, state: SystemState) -> str:
        """시스템 상태를 한국어 브리핑 텍스트로 변환한다.

        Args:
            state: 현재 시스템 상태 스냅샷

        Returns:
            한국어 상황 브리핑 문자열
        """
        if self._llm.is_mock:
            return self._mock_briefing(state)

        user_prompt = build_briefing_user_prompt(state.to_dict())
        messages = [{"role": "user", "content": user_prompt}]

        result = self._llm.chat(
            messages=messages,
            system=BRIEFING_SYSTEM_PROMPT,
        )

        return result.get("text", "브리핑 생성에 실패했습니다.")

    def _mock_briefing(self, state: SystemState) -> str:
        """Mock 모드: 템플릿 기반 브리핑 생성."""
        lines: list[str] = []
        lines.append("=== SkyMind 상황 브리핑 ===")
        lines.append("")

        # 운항 현황
        total = state.active_drones + state.holding_drones
        lines.append(f"■ 운항 현황: 총 {total}대")
        lines.append(f"  - 비행 중: {state.active_drones}대")
        lines.append(f"  - 홀딩 대기: {state.holding_drones}대")

        # 비상 상황
        if state.emergency_drones:
            lines.append(f"■ 비상 상황: {len(state.emergency_drones)}건")
            for drone_id in state.emergency_drones:
                lines.append(f"  - {drone_id}: 비상 상태")
        else:
            lines.append("■ 비상 상황: 없음")

        # 충돌 위험
        if state.conflicts:
            lines.append(f"■ 충돌 위험: {len(state.conflicts)}건 감지")
            for conflict in state.conflicts[:3]:  # 최대 3건
                pair = conflict.get("pair", "N/A")
                dist = conflict.get("distance_m", 0)
                lines.append(f"  - {pair}: 이격거리 {dist:.0f}m")
        else:
            lines.append("■ 충돌 위험: 없음")

        # 기상
        if state.weather:
            wind = state.weather.get("wind_speed_ms", 0)
            rain = state.weather.get("rain_1h_mm", 0)
            vis = state.weather.get("visibility_m", 10000)
            lines.append(f"■ 기상: 풍속 {wind} m/s, 강수 {rain} mm/h, 시정 {vis}m")

            # 기상 경고
            if wind > 15:
                lines.append("  ⚠ 강풍 경고: 경로 우회 권고")
            if rain > 5:
                lines.append("  ⚠ 강수 경고: 속도 제한 적용")
            if vis < 1000:
                lines.append("  ⚠ 시정 불량: 이격거리 확대 적용")
        else:
            lines.append("■ 기상: 데이터 없음")

        # 공역 제한
        if state.airspace_restrictions:
            lines.append(f"■ 공역 제한: {len(state.airspace_restrictions)}건")
            for restriction in state.airspace_restrictions:
                lines.append(f"  - {restriction}")
        else:
            lines.append("■ 공역 제한: 없음")

        # 권고 사항
        recommendations: list[str] = []
        if state.emergency_drones:
            recommendations.append("비상 드론 우선 처리 필요")
        if state.conflicts:
            recommendations.append("충돌 위험 구간 모니터링 강화")
        if state.weather and state.weather.get("wind_speed_ms", 0) > 20:
            recommendations.append("강풍으로 인한 비행 중지 검토")

        if recommendations:
            lines.append("■ 권고 사항:")
            for rec in recommendations:
                lines.append(f"  - {rec}")
        else:
            lines.append("■ 권고 사항: 특이사항 없음. 정상 운항 유지.")

        return "\n".join(lines)
