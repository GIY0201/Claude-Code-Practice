"""비행계획 파싱용 LLM 프롬프트 및 tool 스키마."""

FLIGHT_PLAN_SYSTEM_PROMPT = """\
당신은 SkyMind UTM(UAV Traffic Management) 시스템의 비행계획 파서입니다.
사용자의 자연어 입력에서 드론 비행계획 정보를 추출합니다.

규칙:
1. 출발지와 도착지를 반드시 추출합니다. 장소명이면 그대로 반환합니다.
2. 고도 미지정 시 기본값 100m를 사용합니다 (범위: 30~400m).
3. 속도 미지정 시 기본값 10 m/s를 사용합니다.
4. 우선순위 미지정 시 NORMAL을 사용합니다.
5. 미션 유형은 키워드로 판단합니다:
   - 배송/택배/운송 → DELIVERY
   - 감시/순찰/모니터링 → SURVEILLANCE
   - 점검/검사/촬영 → INSPECTION
   - 비상/긴급/응급 → EMERGENCY_RESPONSE
   기본값: DELIVERY
6. 기본 지역은 서울 수도권입니다.
7. 경유 조건(예: "한강 위로")은 notes에 포함합니다.
"""

FLIGHT_PLAN_TOOL = {
    "name": "extract_flight_plan",
    "description": "자연어에서 드론 비행계획 정보를 구조화하여 추출합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "departure": {
                "type": "string",
                "description": "출발지 장소명 또는 주소 (예: '홍대', '서울역', '37.5665,126.9780')",
            },
            "destination": {
                "type": "string",
                "description": "도착지 장소명 또는 주소",
            },
            "cruise_altitude_m": {
                "type": "number",
                "description": "순항 고도 (미터). 미지정 시 100.",
            },
            "cruise_speed_ms": {
                "type": "number",
                "description": "순항 속도 (m/s). 미지정 시 10.",
            },
            "priority": {
                "type": "string",
                "enum": ["LOW", "NORMAL", "HIGH", "EMERGENCY"],
                "description": "우선순위. 미지정 시 NORMAL.",
            },
            "mission_type": {
                "type": "string",
                "enum": ["DELIVERY", "SURVEILLANCE", "INSPECTION", "EMERGENCY_RESPONSE"],
                "description": "미션 유형.",
            },
            "notes": {
                "type": "string",
                "description": "경유 조건 등 추가 참고사항.",
            },
        },
        "required": ["departure", "destination"],
    },
}


def build_flight_plan_user_prompt(text: str) -> str:
    """사용자 입력 텍스트로부터 비행계획 파싱용 프롬프트를 생성한다."""
    return (
        f"다음 자연어 입력에서 드론 비행계획 정보를 추출해주세요.\n\n"
        f"입력: \"{text}\"\n\n"
        f"extract_flight_plan 도구를 사용하여 구조화된 정보를 반환해주세요."
    )
