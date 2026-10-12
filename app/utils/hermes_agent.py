# -*- coding: utf-8 -*-
"""헤르메스(관리자 전용 자연어 명령 에이전트) - 자연어 명령을 구조화된
필드로만 추출한다. student_id/course_id/session_id 같은 실제 엔티티는 여기서
절대 확정하지 않는다(그건 app/utils/hermes_resolver.py의 결정적 코드 몫) -
CLAUDE.md의 "LLM이 값을 임의 확정하지 않는다" 원칙을 이 경계에서 지킨다.

app/chat_widget/routes.py의 classify_intent와 완전히 같은 패턴(수동 프롬프트
조립 + call_claude_text + extract_json_block) - 이 저장소에 Claude
tool-use/function-calling 사례가 없어 기존 관례를 그대로 따른다.

2026-10-12 실사용 1건에서 "결석 후 보강" 같은 복합 지시가 들어와, 단일 액션
대신 액션 리스트(actions)를 반환하도록 확장했다(사용자 확인 후 채택) - 흔한
문장 하나가 서로 다른 두 작업을 의미하는 경우가 실제로 있었다."""
from datetime import date, timedelta

from app.utils.llm_assist import call_claude_text, extract_json_block

_ACTION_TYPES = ('schedule_makeup', 'mark_absence')
_ABSENCE_STATUSES = ('absent', 'late', 'excused')

_WEEKDAY_KO = ['월', '화', '수', '목', '금', '토', '일']


def _empty_action(reason):
    return {
        'action_type': 'unrecognized',
        'confidence': 'low',
        'unclear_reason': reason,
        'student_name': None,
        'course_hint': None,
        'teacher_name': None,
        'date': None,
        'time': None,
        'status': None,
        'reason': None,
    }


def _fallback(reason):
    return {'actions': [_empty_action(reason)], '_usage': None}


def _build_prompt(text, today):
    weekday_ko = _WEEKDAY_KO[today.weekday()]
    tomorrow = today + timedelta(days=1)
    return f"""당신은 국어 학원 관리자가 입력한 한 줄 지시를 해석하는 보조 도구입니다.
이미 확정된 결정을 문자로 받아쓰는 것이므로, 아래 두 가지 액션 중 하나 이상으로
필드만 뽑아내세요 - 학생/수업/세션을 실제로 어떤 DB 레코드와 연결할지는
당신이 정하지 않습니다. 애매하면 추측하지 말고 confidence를 low로, 무엇이
불확실한지 unclear_reason에 적으세요.

**중요**: 한 문장에 서로 다른 작업이 여러 개 들어있으면("결석 후 보강 진행"
같은 경우) actions 배열에 각각 별도 항목으로 담으세요. 학생 이름이 한 번만
언급돼도 그 문장의 모든 액션에 적용되는 거면 각 액션 항목마다 student_name을
반복해서 채우세요(생략하지 마세요).

오늘 날짜: {today.isoformat()}({weekday_ko}요일). "내일"은 {tomorrow.isoformat()},
"다음주 OO요일"/"이번주 OO요일" 같은 표현도 이 날짜를 기준으로 실제
YYYY-MM-DD로 환산하세요. "이번주 수업"처럼 구체적 요일이 없으면 날짜를
추측하지 말고 date를 null로 두고 unclear_reason에 이유를 적으세요. 연도를
안 쓰면 {today.year}년으로 간주합니다.

## 액션 1: schedule_makeup (보강 일정 확정)
예: "김민준 학생 10월 20일 금요일 5시로 보강 잡아줘", "최선우 학생 다음주
화요일 저녁 8시에 최성호 강사와 보강 진행"
필드: student_name(학생 이름), course_hint(수업 이름/과목 단서, 없으면 null),
date(YYYY-MM-DD), time(HH:MM, 24시간제, 없으면 null),
teacher_name(원래 담당 강사가 아닌 다른 강사를 지정했으면 그 이름, 아니면 null)

## 액션 2: mark_absence (결석/지각/인정결석 처리)
예: "이정기 학생 내일 결석 처리", "오늘 박서연 지각으로 체크해줘"
필드: student_name, course_hint(없으면 null), date(YYYY-MM-DD),
status(absent 또는 late 또는 excused 중 하나), reason(사유 언급 있으면 그대로, 없으면 null)

관리자 지시: "{text}"

다음 JSON 형식으로만 답하세요. 다른 설명은 절대 붙이지 마세요. actions는
항상 배열이며, 액션이 하나뿐이어도 배열 안에 1개만 넣으세요.
{{"actions": [
  {{"action_type": "schedule_makeup 또는 mark_absence 또는 unrecognized",
  "confidence": "high 또는 low",
  "unclear_reason": "모호하거나 해석 불가한 이유(명확하면 null)",
  "student_name": "...또는 null",
  "course_hint": "...또는 null",
  "teacher_name": "...또는 null",
  "date": "YYYY-MM-DD 또는 null",
  "time": "HH:MM 또는 null",
  "status": "absent/late/excused 또는 null",
  "reason": "...또는 null"}}
]}}"""


def _normalize_action(raw_action):
    action_type = raw_action.get('action_type')
    if action_type not in _ACTION_TYPES:
        return _empty_action(raw_action.get('unclear_reason') or '무엇을 해야 할지 이해하지 못했습니다.')
    status = raw_action.get('status')
    return {
        'action_type': action_type,
        'confidence': raw_action.get('confidence') if raw_action.get('confidence') in ('high', 'low') else 'low',
        'unclear_reason': raw_action.get('unclear_reason'),
        'student_name': raw_action.get('student_name'),
        'course_hint': raw_action.get('course_hint'),
        'teacher_name': raw_action.get('teacher_name'),
        'date': raw_action.get('date'),
        'time': raw_action.get('time'),
        'status': status if status in _ABSENCE_STATUSES else None,
        'reason': raw_action.get('reason'),
    }


def parse_hermes_command(text, today=None):
    """자연어 명령을 파싱한다. {'actions': [...], '_usage': {...}} 형태로
    반환한다 - 액션이 하나뿐이어도 항상 리스트. 예외를 던지지 않고 실패 시
    actions=[단일 unrecognized 액션]을 반환한다(호출부가 그대로 사용자에게
    재질문하면 됨)."""
    today = today or date.today()
    text = (text or '').strip()
    if not text:
        return _fallback('빈 메시지입니다.')

    prompt = _build_prompt(text[:500], today)

    try:
        raw, usage = call_claude_text(prompt, max_tokens=500)
    except Exception as e:
        result = _fallback(f'명령 해석 중 오류가 발생했습니다: {e}')
        result['_usage'] = None
        return result

    parsed = extract_json_block(raw) or {}
    raw_actions = parsed.get('actions')
    if not isinstance(raw_actions, list) or not raw_actions:
        actions = [_empty_action('무엇을 해야 할지 이해하지 못했습니다.')]
    else:
        actions = [_normalize_action(a) for a in raw_actions if isinstance(a, dict)]
        if not actions:
            actions = [_empty_action('무엇을 해야 할지 이해하지 못했습니다.')]

    return {'actions': actions, '_usage': usage}
