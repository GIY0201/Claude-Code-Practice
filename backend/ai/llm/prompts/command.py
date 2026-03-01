"""관제 명령 인식 LLM 프롬프트 및 tool 스키마."""

COMMAND_SYSTEM_PROMPT = """\
당신은 SkyMind UTM 시스템의 AI 관제사입니다.
사용자의 자연어 관제 명령을 분석하여 의도(intent)와 파라미터를 추출합니다.

지원 명령:
1. FLIGHT_PLAN — 비행계획 생성 (출발지, 도착지, 드론 배송 등)
2. ALTITUDE_CHANGE — 고도 변경 ("드론 3번 고도 올려", "SKY-001 고도 150m로")
3. SPEED_CHANGE — 속도 변경 ("드론 2번 속도 줄여", "SKY-003 속도 15로")
4. HOLD — 홀딩 명령 ("전체 드론 홀딩", "드론 5번 대기")
5. RETURN_TO_BASE — 귀환 명령 ("드론 5번 귀환시켜", "SKY-002 RTL")
6. SET_NOTAM — 비행 제한/금지 구역 설정 ("A구역 비행금지 설정, 30분")
7. BRIEFING — 상황 브리핑 요청 ("현재 상황 브리핑해줘", "교통 상황 알려줘")
8. GENERAL_QUERY — 일반 질의 ("드론 몇 대 운항 중?", "배터리 상태는?")

규칙:
- 드론 식별: "드론 N번" → drone_id="D{N}", "SKY-NNN" → drone_id="SKY-NNN"
- "전체"/"모든 드론" → drone_id="ALL"
- 고도: "올려" → direction="UP", "내려" → direction="DOWN", 구체적 값 있으면 target_value
- 속도: "줄여"/"감속" → direction="DOWN", "올려"/"가속" → direction="UP"
"""

COMMAND_TOOL = {
    "name": "classify_command",
    "description": "자연어 관제 명령에서 의도와 파라미터를 추출합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "FLIGHT_PLAN", "ALTITUDE_CHANGE", "SPEED_CHANGE",
                    "HOLD", "RETURN_TO_BASE", "SET_NOTAM",
                    "BRIEFING", "GENERAL_QUERY",
                ],
                "description": "분류된 명령 의도.",
            },
            "drone_id": {
                "type": "string",
                "description": "대상 드론 ID (예: 'D1', 'SKY-001', 'ALL'). 해당 없으면 null.",
            },
            "parameters": {
                "type": "object",
                "description": "명령별 추가 파라미터.",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["UP", "DOWN"],
                        "description": "고도/속도 변경 방향.",
                    },
                    "target_value": {
                        "type": "number",
                        "description": "목표 값 (고도 m 또는 속도 m/s).",
                    },
                    "duration_minutes": {
                        "type": "number",
                        "description": "제한 시간 (분). NOTAM/HOLD에 사용.",
                    },
                    "zone_name": {
                        "type": "string",
                        "description": "NOTAM 적용 구역 이름.",
                    },
                    "radius_m": {
                        "type": "number",
                        "description": "NOTAM 반경 (미터).",
                    },
                },
            },
            "confirmation_message": {
                "type": "string",
                "description": "사용자에게 보여줄 확인 메시지 (한국어).",
            },
        },
        "required": ["intent", "confirmation_message"],
    },
}
