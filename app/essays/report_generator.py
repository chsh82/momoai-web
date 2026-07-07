# -*- coding: utf-8 -*-
"""
분기별 모모아이 리포트 생성 엔진

흐름:
  1. PaymentPeriod 기간 내 모모아이 첨삭 수집
  2. 주 모델(가장 많이 사용된 correction_model) 결정
  3. 통계 집계 (점수, 지표 평균, 월별)
  4. HTML 파싱 → 형식/내용 첨삭 항목 추출
  5. Claude API 1회 호출 → AI 총평 + 반복 패턴 분석
  6. EssayReport 레코드 생성/갱신
"""
import json
import os
import re
from collections import Counter
from datetime import datetime

from bs4 import BeautifulSoup

from app.models import db
from app.models.essay import Essay, EssayResult, EssayVersion
from app.models.essay_score import EssayScore
from app.models.essay_report import EssayReport
from app.models.payment_period import PaymentPeriod


# ────────────────────────────────────────────────
# 1. 메인 진입점
# ────────────────────────────────────────────────

def generate_report(student, period: PaymentPeriod) -> EssayReport:
    """
    단일 학생 + 분기 리포트 생성(또는 갱신).
    이미 draft/reviewing 상태 리포트가 있으면 재생성.
    published 상태면 건드리지 않고 반환.
    """
    # 기존 리포트 확인
    existing = EssayReport.query.filter_by(
        student_id=student.student_id,
        period_id=period.period_id
    ).first()
    if existing and existing.status == 'published':
        return existing

    # 해당 분기의 모모아이 완료 첨삭 수집
    essays_in_period = _get_momoai_essays(student.student_id, period)

    if not essays_in_period:
        return None  # 첨삭 없으면 리포트 생성 불가

    # 주 모델 결정 (가장 많이 사용된 모델)
    dominant_model = _dominant_model(essays_in_period)

    # 주 모델 기준 첨삭만 필터
    primary_essays = [e for e in essays_in_period
                      if e.correction_model == dominant_model]

    # 통계 집계
    stats = _compute_stats(primary_essays, period, dominant_model)

    # 첨삭 항목 추출
    format_items, content_items = _extract_correction_items(primary_essays)

    # AI 분석 (총평 + 패턴)
    ai_result = _call_ai(
        student_name=student.name,
        period_label=period.label,
        correction_model=dominant_model,
        stats=stats,
        format_items=format_items,
        content_items=content_items,
    )

    # 저장
    report = existing or EssayReport(
        student_id=student.student_id,
        period_id=period.period_id,
    )
    report.correction_model = dominant_model
    report.status = 'reviewing'
    report.stats_json = json.dumps(stats, ensure_ascii=False)
    report.format_patterns_json = json.dumps(
        ai_result.get('format_patterns', []), ensure_ascii=False)
    report.content_patterns_json = json.dumps(
        ai_result.get('content_patterns', []), ensure_ascii=False)
    report.ai_summary = ai_result.get('ai_summary', '')
    report.created_at = datetime.utcnow()

    if not existing:
        db.session.add(report)
    db.session.commit()
    return report


def generate_reports_for_period(period: PaymentPeriod) -> dict:
    """분기 내 첨삭이 있는 학생 전원 리포트 일괄 생성"""
    from app.models.student import Student

    # 해당 분기에 모모아이 첨삭이 있는 학생 ID 목록
    student_ids = db.session.query(Essay.student_id.distinct())\
        .filter(
            Essay.correction_model.in_(['standard', 'harkness', 'elementary']),
            Essay.status == 'completed',
            Essay.completed_at >= datetime.combine(period.start_date, datetime.min.time()),
            Essay.completed_at <= datetime.combine(period.end_date, datetime.max.time()),
        ).all()
    student_ids = [r[0] for r in student_ids]

    results = {'created': 0, 'skipped': 0, 'errors': []}
    for sid in student_ids:
        student = Student.query.get(sid)
        if not student:
            continue
        try:
            report = generate_report(student, period)
            if report:
                results['created'] += 1
            else:
                results['skipped'] += 1
        except Exception as e:
            results['errors'].append(f"{student.name}: {e}")

    return results


# ────────────────────────────────────────────────
# 2. 데이터 수집 헬퍼
# ────────────────────────────────────────────────

def _get_momoai_essays(student_id: int, period: PaymentPeriod):
    start_dt = datetime.combine(period.start_date, datetime.min.time())
    end_dt = datetime.combine(period.end_date, datetime.max.time())
    return Essay.query.filter(
        Essay.student_id == student_id,
        Essay.correction_model.in_(['standard', 'harkness', 'elementary']),
        Essay.status == 'completed',
        Essay.completed_at >= start_dt,
        Essay.completed_at <= end_dt,
    ).order_by(Essay.completed_at.asc()).all()


def _dominant_model(essays) -> str:
    counts = Counter(e.correction_model for e in essays)
    return counts.most_common(1)[0][0]


# ────────────────────────────────────────────────
# 3. 통계 집계
# ────────────────────────────────────────────────

def _compute_stats(essays, period: PaymentPeriod, model: str) -> dict:
    from app.models.essay_score import EssayScore

    total = len(essays)
    scores = []
    monthly_map = {}   # "YYYY-MM" → [scores]
    indicator_map = {}  # indicator_name → [scores]
    growth_stage_counts = {}

    for essay in essays:
        result = essay.result
        if not result:
            continue

        month_key = essay.completed_at.strftime('%Y-%m') if essay.completed_at else None

        if result.total_score is not None:
            s = float(result.total_score)
            scores.append(s)
            if month_key:
                monthly_map.setdefault(month_key, []).append(s)

        if result.final_grade and model == 'elementary':
            growth_stage_counts[result.final_grade] = \
                growth_stage_counts.get(result.final_grade, 0) + 1

        # 개별 지표 수집
        version_id = result.version_id
        if version_id:
            essay_scores = EssayScore.query.filter_by(
                essay_id=essay.essay_id,
                version_id=version_id
            ).all()
            for es in essay_scores:
                indicator_map.setdefault(
                    (es.category, es.indicator_name), []
                ).append(float(es.score))

    # 지표 평균 계산
    indicators_by_category = {'사고유형': {}, '통합지표': {}}
    for (cat, name), vals in indicator_map.items():
        if cat in indicators_by_category:
            indicators_by_category[cat][name] = round(sum(vals) / len(vals), 2)

    # TOP3 / BOTTOM3
    all_indicator_avgs = {}
    for cat_dict in indicators_by_category.values():
        all_indicator_avgs.update(cat_dict)
    sorted_indicators = sorted(all_indicator_avgs.items(), key=lambda x: x[1], reverse=True)
    top3 = [name for name, _ in sorted_indicators[:3]]
    bottom3 = [name for name, _ in sorted_indicators[-3:]] if len(sorted_indicators) >= 3 else []

    # 월별 통계
    monthly = []
    for key in sorted(monthly_map.keys()):
        vals = monthly_map[key]
        y, m = key.split('-')
        monthly.append({
            'month': f"{int(m)}월",
            'count': len(vals),
            'avg_score': round(sum(vals) / len(vals), 1) if vals else None,
        })

    avg_score = round(sum(scores) / len(scores), 1) if scores else None

    return {
        'period': {
            'label': period.label,
            'start_date': period.start_date.strftime('%Y-%m-%d'),
            'end_date': period.end_date.strftime('%Y-%m-%d'),
            'weeks': period.weeks_count,
        },
        'essays': {
            'total': total,
            'correction_model': model,
        },
        'scores': {
            'avg': avg_score,
            'min': round(min(scores), 1) if scores else None,
            'max': round(max(scores), 1) if scores else None,
            'count': len(scores),
        },
        'growth_stages': growth_stage_counts,   # elementary 전용
        'monthly': monthly,
        'indicators': {
            **indicators_by_category,
            'top3': top3,
            'bottom3': bottom3,
        },
    }


# ────────────────────────────────────────────────
# 4. HTML 파싱 - 첨삭 항목 추출
# ────────────────────────────────────────────────

def _extract_correction_items(essays) -> tuple:
    """형식첨삭 + 내용첨삭 항목 리스트 반환"""
    format_items = []
    content_items = []

    for essay in essays:
        result = essay.result
        if not result or not result.version_id:
            continue
        version = EssayVersion.query.get(result.version_id)
        if not version or not version.html_content:
            continue
        f, c = _parse_correction_tables(version.html_content)
        format_items.extend(f)
        content_items.extend(c)

    return format_items, content_items


def _parse_correction_tables(html: str) -> tuple:
    soup = BeautifulSoup(html, 'html.parser')
    format_items = []
    content_items = []

    FORMAT_CLASSES = {'fc', 'format-correction'}
    CONTENT_CLASSES = {'ctc', 'content-correction'}

    for table in soup.find_all('table', class_=True):
        classes = table.get('class', [])
        if FORMAT_CLASSES & set(classes):
            target = format_items
        elif CONTENT_CLASSES & set(classes):
            target = content_items
        else:
            continue

        for row in table.find_all('tr')[1:]:  # 헤더 제외
            cells = row.find_all('td')
            if len(cells) < 3:
                continue
            # 3번째 셀: eb div(수정문) 제외 후 설명 텍스트
            cell3 = cells[2]
            for eb in cell3.find_all(class_='eb'):
                eb.decompose()
            text = cell3.get_text(separator=' ', strip=True)
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                target.append(text)

    return format_items, content_items


# ────────────────────────────────────────────────
# 5. Claude API 호출
# ────────────────────────────────────────────────

def _call_ai(student_name, period_label, correction_model,
             stats, format_items, content_items) -> dict:
    """
    Claude API로 총평 + 반복 패턴 분석.
    API 키 없거나 오류 시 빈 결과 반환.
    """
    try:
        import anthropic
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            return _fallback_result(stats, format_items, content_items)

        client = anthropic.Anthropic(api_key=api_key)

        is_elementary = correction_model == 'elementary'
        tone_guide = (
            "초등학생 자녀를 둔 학부모를 대상으로 친근하고 따뜻한 문체로 작성하세요."
            if is_elementary else
            "학부모를 대상으로 전문적이고 신뢰감 있는 문체로 작성하세요."
        )

        score_section = ""
        if is_elementary:
            stages = stats.get('growth_stages', {})
            if stages:
                stage_str = ', '.join(f"{k} {v}회" for k, v in stages.items())
                score_section = f"- 성장단계 분포: {stage_str}"
        else:
            s = stats.get('scores', {})
            if s.get('avg'):
                score_section = (
                    f"- 분기 평균 점수: {s['avg']}점\n"
                    f"- 최고 {s['max']}점 / 최저 {s['min']}점"
                )

        top3 = ', '.join(stats.get('indicators', {}).get('top3', []))
        bottom3 = ', '.join(stats.get('indicators', {}).get('bottom3', []))

        fmt_sample = '\n'.join(f"- {t}" for t in format_items[:30])
        cnt_sample = '\n'.join(f"- {t}" for t in content_items[:30])

        prompt = f"""다음은 {student_name} 학생의 {period_label} 모모아이 첨삭 데이터입니다.

[통계]
- 총 완료 첨삭: {stats['essays']['total']}건
{score_section}
- 강점 지표 TOP3: {top3}
- 보완 필요 지표 BOTTOM3: {bottom3}

[형식첨삭 지적 항목 (전체 {len(format_items)}건 중 샘플)]
{fmt_sample if fmt_sample else '(없음)'}

[내용첨삭 지적 항목 (전체 {len(content_items)}건 중 샘플)]
{cnt_sample if cnt_sample else '(없음)'}

위 데이터를 바탕으로 아래 JSON을 반환하세요. JSON만 출력하고 다른 텍스트는 없애세요.

{{
  "ai_summary": "학부모 대상 분기 총평 (250자 내외). {tone_guide}",
  "format_patterns": [
    {{"rank": 1, "pattern": "반복된 형식 지적 패턴 (20자 이내)", "count_hint": "여러 번 / 자주 등"}},
    ...최대 5개
  ],
  "content_patterns": [
    {{"rank": 1, "pattern": "반복된 내용 지적 패턴 (20자 이내)", "count_hint": "여러 번 / 자주 등"}},
    ...최대 5개
  ]
}}"""

        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1024,
            messages=[{'role': 'user', 'content': prompt}]
        )
        raw = response.content[0].text.strip()

        # JSON 블록 추출
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            return json.loads(m.group(0))
        return json.loads(raw)

    except Exception:
        return _fallback_result(stats, format_items, content_items)


def _fallback_result(stats, format_items, content_items) -> dict:
    """AI 호출 실패 시 기본 결과"""
    from collections import Counter
    fmt_common = Counter(format_items).most_common(5)
    cnt_common = Counter(content_items).most_common(5)
    return {
        'ai_summary': '',
        'format_patterns': [
            {'rank': i + 1, 'pattern': p, 'count_hint': f'{c}회'}
            for i, (p, c) in enumerate(fmt_common)
        ],
        'content_patterns': [
            {'rank': i + 1, 'pattern': p, 'count_hint': f'{c}회'}
            for i, (p, c) in enumerate(cnt_common)
        ],
    }
