"""상황 브리핑 생성 LLM 프롬프트."""

BRIEFING_SYSTEM_PROMPT = """\
당신은 SkyMind UTM 시스템의 AI 관제사입니다.
현재 시스템 상태 데이터를 바탕으로 한국어 상황 브리핑을 생성합니다.

브리핑 형식:
1. 운항 현황: 활성 드론 수, 대기 드론 수
2. 충돌 상황: 감지된 충돌 위험 건수, 회피 기동 현황
3. 기상 상황: 현재 기상 조건, 비행 제한 영향
4. 비상 상황: 비상 드론 목록, 배터리/통신/GPS 이슈
5. 공역 제한: 활성 NOTAM 및 제한 구역
6. 권고 사항: 조치가 필요한 항목

스타일:
- 간결하고 전문적인 항공 관제 브리핑 톤
- 위험도 높은 항목을 먼저 언급
- 수치와 식별자를 정확히 포함
"""


def build_briefing_user_prompt(state: dict) -> str:
    """시스템 상태 dict로부터 브리핑 요청 프롬프트를 생성한다."""
    lines = ["현재 SkyMind 시스템 상태를 바탕으로 상황 브리핑을 생성해주세요.", ""]

    lines.append(f"활성 드론: {state.get('active_drones', 0)}대")
    lines.append(f"홀딩 드론: {state.get('holding_drones', 0)}대")

    emergency = state.get("emergency_drones", [])
    if emergency:
        lines.append(f"비상 드론: {', '.join(emergency)}")
    else:
        lines.append("비상 드론: 없음")

    conflicts = state.get("conflicts", [])
    lines.append(f"충돌 위험: {len(conflicts)}건")

    weather = state.get("weather")
    if weather:
        lines.append(f"기상: 풍속 {weather.get('wind_speed_ms', 0)} m/s, "
                      f"강수 {weather.get('rain_1h_mm', 0)} mm/h, "
                      f"시정 {weather.get('visibility_m', 10000)} m")
    else:
        lines.append("기상: 데이터 없음")

    restrictions = state.get("airspace_restrictions", [])
    if restrictions:
        lines.append(f"공역 제한: {', '.join(restrictions)}")
    else:
        lines.append("공역 제한: 없음")

    return "\n".join(lines)
