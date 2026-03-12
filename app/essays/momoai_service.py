# -*- coding: utf-8 -*-
"""MOMOAI 첨삭 서비스 (SQLAlchemy 연동)"""
import anthropic
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from flask import current_app

from app.models import db, Essay, EssayVersion, EssayResult, EssayScore, EssayNote
from app.essays.score_parser import get_parser

# 동시 API 호출 제한 (최대 2개 동시 처리, 나머지는 큐 대기)
_api_semaphore = threading.Semaphore(2)


class MOMOAIService:
    """MOMOAI 첨삭 서비스 클래스"""

    def __init__(self, api_key: str):
        """
        Initialize MOMOAI Service

        Args:
            api_key: Anthropic API key
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.system_prompt = self.load_momoai_document()

    def load_momoai_document(self) -> str:
        """MOMOAI 규칙 문서 로드"""
        try:
            doc_path = current_app.config.get('MOMOAI_DOC_PATH')
            with open(doc_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"MOMOAI 문서를 로드할 수 없습니다: {e}")

    def create_analysis_prompt(self, student_name: str, grade: str,
                              essay_text: str, notes: Optional[str] = None,
                              revision_note: Optional[str] = None,
                              teacher_name: Optional[str] = None,
                              is_revision_of_completed: bool = False) -> str:
        """분석 프롬프트 생성"""
        if is_revision_of_completed:
            prompt = f"""학생 정보:
- 이름: {student_name}
- 학년: {grade}

이전 첨삭본:
{essay_text}

수정 요청 사항:
{revision_note}

위 첨삭본을 기반으로 수정 요청 사항을 반영하여 개선된 첨삭본을 생성해주세요.
MOMOAI v3.3.0 규칙을 준수하고, 반드시 HTML 완전 템플릿 형식으로 출력해주세요.
"""
        else:
            prompt = f"""학생 정보:
- 이름: {student_name}
- 학년: {grade}

논술문:
{essay_text}
"""

            if notes:
                prompt += f"\n주의사항:\n{notes}\n"

            if revision_note:
                prompt += f"\n수정 요청 사항:\n{revision_note}\n"

            prompt += """
위 논술문을 MOMOAI v3.3.0 규칙에 따라 첨삭해주세요.
반드시 HTML 완전 템플릿 형식으로 출력하고, 모든 규칙을 준수해주세요.

v3.3.0 필수 포함 사항:
1. 윤문 완성본 (원문 대비 1.3~2배 분량, 통계+사례 필수)
2. 💭 생각해볼 쟁점 세 가지 (내용첨삭과 비중복되는 심화 질문)
3. 교사 종합 제언
4. 푸터까지 완전한 HTML 문서

특히 "생각해볼 쟁점 세 가지" 섹션은 필수입니다. 내용 첨삭에서 지적한 문제가 아닌, 글을 넘어서는 심화 토론 주제 3가지를 제시해주세요.
"""

        # 첨삭자 사인 추가
        if teacher_name:
            prompt += f"\n\n중요: HTML 문서의 맨 마지막 </body> 태그 직전에 다음 형식의 첨삭자 사인을 추가해주세요:\n"
            prompt += f'<div style="text-align: right; margin-top: 50px; padding: 20px; color: #666; font-style: italic;">\n'
            prompt += f'    첨삭: {teacher_name}\n'
            prompt += f'</div>\n'

        return prompt

    def analyze_essay(self, student_name: str, grade: str, essay_text: str,
                     notes: Optional[str] = None,
                     revision_note: Optional[str] = None,
                     teacher_name: Optional[str] = None,
                     is_revision_of_completed: bool = False,
                     user_id: Optional[str] = None,
                     essay_id: Optional[str] = None,
                     usage_type: str = 'correction') -> str:
        """
        논술문 분석 및 HTML 리포트 생성

        Args:
            student_name: 학생 이름
            grade: 학년 (초등/중등/고등)
            essay_text: 논술문 텍스트
            notes: 주의사항 (선택)
            revision_note: 수정 요청 내용 (재생성 시)
            teacher_name: 첨삭자 이름 (사인용)
            is_revision_of_completed: 완료된 첨삭의 수정 여부

        Returns:
            HTML 형식의 첨삭 리포트
        """
        import time

        user_prompt = self.create_analysis_prompt(
            student_name, grade, essay_text, notes, revision_note,
            teacher_name, is_revision_of_completed
        )

        print(f"\n{'='*60}")
        print(f"[첨삭 대기] {student_name} 학생 - {grade} (슬롯 획득 시도)")
        print(f"{'='*60}\n")

        with _api_semaphore:  # 동시 2개 제한 — 나머지는 여기서 대기
            return self._call_api_with_retry(
                student_name, grade, user_prompt,
                user_id=user_id,
                essay_id=essay_id,
                usage_type=usage_type,
            )

    def _call_api_with_retry(self, student_name: str, grade: str, user_prompt: str,
                              user_id=None, essay_id=None, usage_type='correction') -> str:
        """Rate Limit 에러 시 최대 3회 재시도 (30초 간격)"""
        max_retries = 3
        retry_delays = [30, 60, 120]  # 초

        for attempt in range(max_retries + 1):
            try:
                print(f"\n{'='*60}")
                print(f"[첨삭 시작] {student_name} 학생 - {grade}"
                      + (f" (재시도 {attempt}/{max_retries})" if attempt > 0 else ""))
                print(f"System prompt 길이: {len(self.system_prompt):,} chars")
                print(f"User prompt 길이: {len(user_prompt):,} chars")
                print(f"{'='*60}\n")

                start_time = time.time()

                # Prompt Caching 적용: system prompt를 5분간 캐싱
                response = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=32000,
                    timeout=600.0,
                    system=[
                        {
                            "type": "text",
                            "text": self.system_prompt,
                            "cache_control": {"type": "ephemeral"}  # 5분간 캐싱
                        }
                    ],
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )

                elapsed_time = time.time() - start_time

                # 캐싱 정보 출력
                usage = response.usage
                cache_creation = getattr(usage, 'cache_creation_input_tokens', 0)
                cache_read = getattr(usage, 'cache_read_input_tokens', 0)
                output_tokens = getattr(usage, 'output_tokens', 0)
                stop_reason = response.stop_reason

                print(f"\n{'='*60}")
                print(f"[첨삭 완료] API 호출 시간: {elapsed_time:.2f}초")
                print(f"응답 길이: {len(response.content[0].text):,} chars")
                print(f"출력 토큰: {output_tokens:,} / 32000")
                print(f"Stop reason: {stop_reason}")
                if stop_reason == 'max_tokens':
                    print(f"⚠️ 경고: max_tokens 초과로 응답이 잘렸습니다!")
                if cache_creation > 0:
                    print(f"캐시 생성: {cache_creation:,} 토큰 (첫 요청)")
                if cache_read > 0:
                    print(f"캐시 읽기: {cache_read:,} 토큰 (캐싱 활용!)")
                    print(f"💰 비용 절감: 약 90% (캐싱된 토큰 무료)")
                print(f"{'='*60}\n")

                # 사용량 로그 저장
                try:
                    from app.models.api_usage_log import ApiUsageLog
                    input_tok = getattr(usage, 'input_tokens', 0)
                    cost = ApiUsageLog.calc_claude_cost(
                        input_tok, output_tokens, cache_read, cache_creation)
                    log = ApiUsageLog(
                        user_id=user_id,
                        api_type='claude',
                        model_name='claude-sonnet-4-6',
                        usage_type=usage_type,
                        essay_id=essay_id,
                        input_tokens=input_tok,
                        output_tokens=output_tokens,
                        cache_read_tokens=cache_read,
                        cache_write_tokens=cache_creation,
                        cost_usd=cost,
                    )
                    db.session.add(log)
                    db.session.commit()
                except Exception as log_err:
                    print(f"[사용량 로그 저장 실패] {log_err}")

                # Extract HTML from response
                html_content = response.content[0].text

                # Remove markdown code blocks if present
                if '```html' in html_content:
                    start = html_content.find('```html') + 7
                    end = html_content.find('```', start)
                    if end != -1:
                        html_content = html_content[start:end].strip()
                elif '```' in html_content:
                    start = html_content.find('```') + 3
                    end = html_content.find('```', start)
                    if end != -1:
                        html_content = html_content[start:end].strip()

                # Find DOCTYPE or <html tag
                if '<!DOCTYPE' in html_content or '<html' in html_content:
                    if '<!DOCTYPE' in html_content:
                        html_start = html_content.find('<!DOCTYPE')
                        html_content = html_content[html_start:]
                    elif '<html' in html_content:
                        html_start = html_content.find('<html')
                        html_content = html_content[html_start:]
                    return html_content
                else:
                    raise Exception("API 응답에서 HTML을 찾을 수 없습니다.")

            except anthropic.RateLimitError as e:
                # Rate Limit: 재시도
                if attempt < max_retries:
                    wait = retry_delays[attempt]
                    print(f"⚠️ [Rate Limit] {wait}초 후 재시도 ({attempt+1}/{max_retries})...")
                    time.sleep(wait)
                    continue
                raise Exception(f"API 요청 한도 초과 (재시도 {max_retries}회 실패): {e}")

            except anthropic.APIStatusError as e:
                # 5xx 서버 에러: 재시도
                if e.status_code >= 500 and attempt < max_retries:
                    wait = retry_delays[attempt]
                    print(f"⚠️ [서버 에러 {e.status_code}] {wait}초 후 재시도 ({attempt+1}/{max_retries})...")
                    time.sleep(wait)
                    continue
                raise Exception(f"첨삭 중 API 오류가 발생했습니다: {e}")

            except Exception as e:
                raise Exception(f"첨삭 중 오류가 발생했습니다: {e}")

    # ------------------------------------------------------------------ #
    #  스탠다드 모델 (3단계 체인 호출)                                     #
    # ------------------------------------------------------------------ #

    def _load_standard_document(self) -> str:
        """스탠다드 모델 규칙 문서 로드"""
        try:
            doc_path = current_app.config.get('MOMOAI_STANDARD_DOC_PATH')
            with open(doc_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"스탠다드 모델 문서를 로드할 수 없습니다: {e}")

    def _load_elem_document(self) -> str:
        """초등 모델 규칙 문서 로드"""
        try:
            doc_path = current_app.config.get('MOMOAI_ELEM_DOC_PATH')
            with open(doc_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"초등 모델 문서를 로드할 수 없습니다: {e}")

    def _extract_html_block(self, text: str) -> str:
        """응답에서 ```html 코드블록 내용 추출"""
        if '```html' in text:
            start = text.find('```html') + 7
            end = text.find('```', start)
            if end != -1:
                return text[start:end].strip()
        if '```' in text:
            start = text.find('```') + 3
            end = text.find('```', start)
            if end != -1:
                return text[start:end].strip()
        return text.strip()

    def _call_standard_step(self, standard_system: str, messages: list,
                             step_name: str, student_name: str,
                             user_id=None, essay_id=None) -> str:
        """스탠다드 모델 단계별 API 호출 (retry 포함)"""
        import time
        max_retries = 3
        retry_delays = [30, 60, 120]

        for attempt in range(max_retries + 1):
            try:
                print(f"\n[스탠다드 {step_name}] {student_name} 학생 시작"
                      + (f" (재시도 {attempt})" if attempt > 0 else ""))
                start_time = time.time()

                response = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=12000,
                    timeout=300.0,
                    system=[
                        {
                            "type": "text",
                            "text": standard_system,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ],
                    messages=messages,
                )

                elapsed = time.time() - start_time
                usage = response.usage
                output_tokens = getattr(usage, 'output_tokens', 0)
                print(f"[스탠다드 {step_name}] 완료 {elapsed:.1f}초 / {output_tokens}tok")

                # 사용량 로그
                try:
                    from app.models.api_usage_log import ApiUsageLog
                    input_tok = getattr(usage, 'input_tokens', 0)
                    cache_read = getattr(usage, 'cache_read_input_tokens', 0)
                    cache_write = getattr(usage, 'cache_creation_input_tokens', 0)
                    cost = ApiUsageLog.calc_claude_cost(input_tok, output_tokens, cache_read, cache_write)
                    log = ApiUsageLog(
                        user_id=user_id,
                        api_type='claude',
                        model_name='claude-sonnet-4-6',
                        usage_type=f'standard_{step_name}',
                        essay_id=essay_id,
                        input_tokens=input_tok,
                        output_tokens=output_tokens,
                        cache_read_tokens=cache_read,
                        cache_write_tokens=cache_write,
                        cost_usd=cost,
                    )
                    db.session.add(log)
                    db.session.commit()
                except Exception as log_err:
                    print(f"[사용량 로그 저장 실패] {log_err}")

                return response.content[0].text

            except anthropic.RateLimitError:
                if attempt < max_retries:
                    time.sleep(retry_delays[attempt])
                    continue
                raise
            except anthropic.APIStatusError as e:
                if e.status_code >= 500 and attempt < max_retries:
                    time.sleep(retry_delays[attempt])
                    continue
                raise

    def analyze_essay_standard(self, student_name: str, grade: str, essay_text: str,
                                notes: Optional[str] = None,
                                teacher_name: Optional[str] = None,
                                user_id: Optional[str] = None,
                                essay_id: Optional[str] = None) -> str:
        """
        스탠다드 모델: 3단계 체인 API 호출 후 HTML 결합

        Returns:
            합쳐진 완성 HTML 문서
        """
        standard_system = self._load_standard_document()

        # 1차 프롬프트 구성
        step1_content = f"[학생 원문]\n{essay_text}"
        if notes:
            step1_content += f"\n\n[교사 지시]\n{notes}"
        step1_content += "\n\n1차 작업을 수행하세요."

        with _api_semaphore:
            # 1차 호출
            step1_resp = self._call_standard_step(
                standard_system,
                [{"role": "user", "content": step1_content}],
                "1차", student_name, user_id=user_id, essay_id=essay_id,
            )

            # 2차 호출
            step2_resp = self._call_standard_step(
                standard_system,
                [
                    {"role": "user", "content": step1_content},
                    {"role": "assistant", "content": step1_resp},
                    {"role": "user", "content": "계속"},
                ],
                "2차", student_name, user_id=user_id, essay_id=essay_id,
            )

            # 3차 호출
            step3_resp = self._call_standard_step(
                standard_system,
                [
                    {"role": "user", "content": step1_content},
                    {"role": "assistant", "content": step1_resp},
                    {"role": "user", "content": "계속"},
                    {"role": "assistant", "content": step2_resp},
                    {"role": "user", "content": "계속"},
                ],
                "3차", student_name, user_id=user_id, essay_id=essay_id,
            )

        # HTML 블록 추출 후 결합
        html1 = self._extract_html_block(step1_resp)
        html2 = self._extract_html_block(step2_resp)
        html3 = self._extract_html_block(step3_resp)
        combined = html1 + "\n" + html2 + "\n" + html3

        # 강사 사인 삽입
        if teacher_name and '</body>' in combined:
            sign = (
                f'\n<div style="text-align:right;margin-top:50px;padding:20px;'
                f'color:#666;font-style:italic;">첨삭: {teacher_name}</div>\n'
            )
            combined = combined.replace('</body>', sign + '</body>', 1)

        return combined

    def analyze_essay_elementary(self, student_name: str, grade: str, essay_text: str,
                                  notes: Optional[str] = None,
                                  teacher_name: Optional[str] = None,
                                  user_id: Optional[str] = None,
                                  essay_id: Optional[str] = None) -> str:
        """
        초등 모델: 3단계 체인 API 호출 후 HTML 결합 (max_tokens=4096)

        Returns:
            합쳐진 완성 HTML 문서
        """
        elem_system = self._load_elem_document()

        # 1차 프롬프트 구성
        step1_content = f"[학생 원문]\n{essay_text}"
        if notes:
            step1_content += f"\n\n[교사 지시]\n{notes}"
        step1_content += "\n\n1차 작업을 수행하세요."

        with _api_semaphore:
            # 1차 호출
            step1_resp = self._call_elem_step(
                elem_system,
                [{"role": "user", "content": step1_content}],
                "1차", student_name, user_id=user_id, essay_id=essay_id,
            )

            # 2차 호출
            step2_resp = self._call_elem_step(
                elem_system,
                [
                    {"role": "user", "content": step1_content},
                    {"role": "assistant", "content": step1_resp},
                    {"role": "user", "content": "계속"},
                ],
                "2차", student_name, user_id=user_id, essay_id=essay_id,
            )

            # 3차 호출
            step3_resp = self._call_elem_step(
                elem_system,
                [
                    {"role": "user", "content": step1_content},
                    {"role": "assistant", "content": step1_resp},
                    {"role": "user", "content": "계속"},
                    {"role": "assistant", "content": step2_resp},
                    {"role": "user", "content": "계속"},
                ],
                "3차", student_name, user_id=user_id, essay_id=essay_id,
            )

        # HTML 블록 추출 후 결합
        html1 = self._extract_html_block(step1_resp)
        html2 = self._extract_html_block(step2_resp)
        html3 = self._extract_html_block(step3_resp)
        combined = html1 + "\n" + html2 + "\n" + html3

        # 강사 사인 삽입
        if teacher_name and '</body>' in combined:
            sign = (
                f'\n<div style="text-align:right;margin-top:50px;padding:20px;'
                f'color:#666;font-style:italic;">첨삭: {teacher_name}</div>\n'
            )
            combined = combined.replace('</body>', sign + '</body>', 1)

        return combined

    def _call_elem_step(self, elem_system: str, messages: list,
                        step_name: str, student_name: str,
                        user_id=None, essay_id=None) -> str:
        """초등 모델 단계별 API 호출 (max_tokens=12000, retry 포함)"""
        import time
        max_retries = 3
        retry_delays = [30, 60, 120]

        for attempt in range(max_retries + 1):
            try:
                print(f"\n[초등 {step_name}] {student_name} 학생 시작"
                      + (f" (재시도 {attempt})" if attempt > 0 else ""))
                start_time = time.time()

                response = self.client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=12000,
                    timeout=300.0,
                    system=[
                        {
                            "type": "text",
                            "text": elem_system,
                            "cache_control": {"type": "ephemeral"}
                        }
                    ],
                    messages=messages,
                )

                elapsed = time.time() - start_time
                usage = response.usage
                output_tokens = getattr(usage, 'output_tokens', 0)
                print(f"[초등 {step_name}] 완료 {elapsed:.1f}초 / {output_tokens}tok")

                # 사용량 로그
                try:
                    from app.models.api_usage_log import ApiUsageLog
                    input_tok = getattr(usage, 'input_tokens', 0)
                    cache_read = getattr(usage, 'cache_read_input_tokens', 0)
                    cache_write = getattr(usage, 'cache_creation_input_tokens', 0)
                    cost = ApiUsageLog.calc_claude_cost(input_tok, output_tokens, cache_read, cache_write)
                    log = ApiUsageLog(
                        user_id=user_id,
                        api_type='claude',
                        model_name='claude-sonnet-4-6',
                        usage_type=f'elementary_{step_name}',
                        essay_id=essay_id,
                        input_tokens=input_tok,
                        output_tokens=output_tokens,
                        cache_read_tokens=cache_read,
                        cache_write_tokens=cache_write,
                        cost_usd=cost,
                    )
                    db.session.add(log)
                    db.session.commit()
                except Exception as log_err:
                    print(f"[사용량 로그 저장 실패] {log_err}")

                return response.content[0].text

            except anthropic.RateLimitError:
                if attempt < max_retries:
                    time.sleep(retry_delays[attempt])
                    continue
                raise
            except anthropic.APIStatusError as e:
                if e.status_code >= 500 and attempt < max_retries:
                    time.sleep(retry_delays[attempt])
                    continue
                raise

    def save_html(self, html_content: str, filename: str) -> str:
        """
        HTML 파일 저장

        Args:
            html_content: HTML 콘텐츠
            filename: 파일명

        Returns:
            저장된 파일의 전체 경로
        """
        try:
            html_folder = Path(current_app.config['HTML_FOLDER'])
            file_path = html_folder / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            return str(file_path)
        except Exception as e:
            raise Exception(f"HTML 파일 저장 중 오류가 발생했습니다: {e}")

    def generate_filename(self, student_name: str, grade: str,
                         version: int = 1, extension: str = 'html') -> str:
        """
        파일명 생성

        Args:
            student_name: 학생 이름
            grade: 학년
            version: 버전 번호
            extension: 파일 확장자

        Returns:
            생성된 파일명
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{student_name}_{grade}_v{version}_{timestamp}.{extension}"

    def create_essay(self, student_id: str, user_id: str, title: Optional[str],
                    original_text: str, grade: str, notes: Optional[str] = None) -> Essay:
        """
        새 첨삭 작업 생성

        Args:
            student_id: 학생 ID
            user_id: 사용자 (강사) ID
            title: 제목
            original_text: 원문
            grade: 학년
            notes: 주의사항

        Returns:
            생성된 Essay 객체
        """
        essay = Essay(
            student_id=student_id,
            user_id=user_id,
            title=title,
            original_text=original_text,
            grade=grade,
            status='draft'
        )

        db.session.add(essay)

        # 주의사항이 있으면 저장
        if notes:
            essay_note = EssayNote(
                essay_id=essay.essay_id,
                note_type='주의사항',
                content=notes
            )
            db.session.add(essay_note)

        db.session.commit()
        return essay

    def process_essay(self, essay: Essay, student_name: str, teacher_name: Optional[str] = None) -> Tuple[EssayVersion, str]:
        """
        첨삭 처리 (새 버전 생성)

        Args:
            essay: Essay 객체
            student_name: 학생 이름
            teacher_name: 첨삭자 이름

        Returns:
            (EssayVersion, html_path) 튜플
        """
        # 상태 업데이트
        essay.status = 'processing'
        db.session.commit()

        try:
            # 주의사항 + 강사 가이드 합산
            parts = []
            if essay.notes:
                parts.append('\n'.join([note.content for note in essay.notes]))
            if getattr(essay, 'teacher_guide', None):
                parts.append(f'[강사 가이드]\n{essay.teacher_guide}')
            notes = '\n\n'.join(parts) if parts else None

            # 모델에 따라 첨삭 수행
            model = getattr(essay, 'correction_model', 'standard') or 'standard'

            if model == 'harkness':
                html_content = self.analyze_essay(
                    student_name=student_name,
                    grade=essay.grade,
                    essay_text=essay.original_text,
                    notes=notes,
                    teacher_name=teacher_name,
                    user_id=essay.user_id,
                    essay_id=essay.essay_id,
                    usage_type='correction',
                )
            elif model == 'elementary':
                html_content = self.analyze_essay_elementary(
                    student_name=student_name,
                    grade=essay.grade,
                    essay_text=essay.original_text,
                    notes=notes,
                    teacher_name=teacher_name,
                    user_id=essay.user_id,
                    essay_id=essay.essay_id,
                )
            else:  # standard
                html_content = self.analyze_essay_standard(
                    student_name=student_name,
                    grade=essay.grade,
                    essay_text=essay.original_text,
                    notes=notes,
                    teacher_name=teacher_name,
                    user_id=essay.user_id,
                    essay_id=essay.essay_id,
                )

            # HTML 저장
            filename = self.generate_filename(
                student_name=student_name,
                grade=essay.grade,
                version=essay.current_version
            )
            html_path = self.save_html(html_content, filename)

            # 버전 생성
            version = EssayVersion(
                essay_id=essay.essay_id,
                version_number=essay.current_version,
                html_content=html_content,
                html_path=html_path
            )
            db.session.add(version)

            # 결과 생성
            result = EssayResult(
                essay_id=essay.essay_id,
                version_id=version.version_id,
                html_path=html_path
            )
            db.session.add(result)

            # 상태 업데이트
            essay.status = 'reviewing'
            essay.completed_at = datetime.utcnow()

            db.session.commit()

            # Phase 2: 점수 파싱 및 저장
            self.parse_and_save_scores(
                html_content=html_content,
                essay_id=essay.essay_id,
                version_id=version.version_id
            )

            return version, html_path

        except Exception as e:
            essay.status = 'failed'
            db.session.commit()
            raise e

    def regenerate_essay(self, essay: Essay, student_name: str,
                        revision_note: str, teacher_name: Optional[str] = None) -> Tuple[EssayVersion, str]:
        """
        첨삭 재생성 (새 버전 생성)

        Args:
            essay: Essay 객체
            student_name: 학생 이름
            revision_note: 수정 요청 내용
            teacher_name: 첨삭자 이름

        Returns:
            (EssayVersion, html_path) 튜플
        """
        # 버전 증가
        essay.current_version += 1
        essay.status = 'processing'

        # 완료된 첨삭인지 확인
        is_finalized = essay.is_finalized

        # 완료된 첨삭의 경우 is_finalized를 False로 변경 (재작업)
        if is_finalized:
            essay.is_finalized = False
            essay.finalized_at = None

        db.session.commit()

        try:
            model = getattr(essay, 'correction_model', 'standard') or 'standard'

            # 초등 모델은 항상 원문 기반으로 재생성 (HTML 입력 불가)
            if model == 'elementary':
                notes_parts = []
                if essay.notes:
                    notes_parts.append('\n'.join([note.content for note in essay.notes]))
                if getattr(essay, 'teacher_guide', None):
                    notes_parts.append(f'[강사 가이드]\n{essay.teacher_guide}')
                if revision_note:
                    notes_parts.append(f'[수정 요청]\n{revision_note}')
                notes_combined = '\n\n'.join(notes_parts) if notes_parts else None

                html_content = self.analyze_essay_elementary(
                    student_name=student_name,
                    grade=essay.grade,
                    essay_text=essay.original_text,
                    notes=notes_combined,
                    teacher_name=teacher_name,
                    user_id=essay.user_id,
                    essay_id=essay.essay_id,
                )
            else:
                # 완료된 첨삭의 경우 이전 버전의 HTML 내용을 기반으로 수정
                if is_finalized and essay.latest_version:
                    essay_text = essay.latest_version.html_content
                    notes = None
                    is_revision_of_completed = True
                else:
                    # 미완료 첨삭은 원문 기반
                    essay_text = essay.original_text
                    notes = None
                    if essay.notes:
                        notes = '\n'.join([note.content for note in essay.notes])
                    if getattr(essay, 'teacher_guide', None):
                        teacher_guide_text = f'[강사 가이드]\n{essay.teacher_guide}'
                        notes = (notes + '\n\n' + teacher_guide_text) if notes else teacher_guide_text
                    is_revision_of_completed = False

                if model == 'standard':
                    html_content = self.analyze_essay_standard(
                        student_name=student_name,
                        grade=essay.grade,
                        essay_text=essay_text,
                        notes=notes,
                        teacher_name=teacher_name,
                        user_id=essay.user_id,
                        essay_id=essay.essay_id,
                    )
                else:  # harkness
                    html_content = self.analyze_essay(
                        student_name=student_name,
                        grade=essay.grade,
                        essay_text=essay_text,
                        notes=notes,
                        revision_note=revision_note,
                        teacher_name=teacher_name,
                        is_revision_of_completed=is_revision_of_completed,
                        user_id=essay.user_id,
                        essay_id=essay.essay_id,
                        usage_type='regeneration',
                    )

            # HTML 저장
            filename = self.generate_filename(
                student_name=student_name,
                grade=essay.grade,
                version=essay.current_version
            )
            html_path = self.save_html(html_content, filename)

            # 새 버전 생성
            version = EssayVersion(
                essay_id=essay.essay_id,
                version_number=essay.current_version,
                html_content=html_content,
                html_path=html_path,
                revision_note=revision_note
            )
            db.session.add(version)

            # 결과 업데이트
            essay.result.version_id = version.version_id
            essay.result.html_path = html_path

            # 상태 업데이트
            essay.status = 'reviewing'
            db.session.commit()

            # Phase 2: 점수 파싱 및 저장
            self.parse_and_save_scores(
                html_content=html_content,
                essay_id=essay.essay_id,
                version_id=version.version_id
            )

            return version, html_path

        except Exception as e:
            essay.status = 'failed'
            db.session.commit()
            raise e

    def parse_and_save_scores(self, html_content: str, essay_id: str,
                              version_id: str) -> bool:
        """
        HTML에서 점수를 파싱하여 데이터베이스에 저장 (Phase 2)

        Args:
            html_content: HTML 콘텐츠
            essay_id: Essay ID
            version_id: EssayVersion ID

        Returns:
            성공 여부 (bool)
        """
        try:
            # 파서 가져오기
            parser = get_parser()

            # HTML 파싱
            parsed_data = parser.parse_html(html_content)

            if not parsed_data.get('success'):
                # 파싱 실패 시 로그만 남기고 계속 진행
                print(f"⚠️ 점수 파싱 실패: {parsed_data.get('error', 'Unknown error')}")
                return False

            # EssayResult 업데이트 (총점, 최종 등급)
            result = EssayResult.query.filter_by(
                essay_id=essay_id,
                version_id=version_id
            ).first()

            if result:
                result.total_score = parsed_data.get('total_score')
                result.final_grade = parsed_data.get('final_grade')

            # 기존 점수 삭제 (해당 버전의)
            EssayScore.query.filter_by(version_id=version_id).delete()

            # 새 점수 저장
            scores_list = parser.get_all_scores_list(parsed_data)
            for category, indicator_name, score in scores_list:
                essay_score = EssayScore(
                    essay_id=essay_id,
                    version_id=version_id,
                    category=category,
                    indicator_name=indicator_name,
                    score=score
                )
                db.session.add(essay_score)

            db.session.commit()
            print(f"✅ 점수 파싱 완료: 총 {len(scores_list)}개 지표 저장")
            return True

        except Exception as e:
            print(f"❌ 점수 저장 중 오류: {e}")
            db.session.rollback()
            return False

    def finalize_essay(self, essay: Essay) -> None:
        """
        첨삭 완료 처리

        Args:
            essay: Essay 객체
        """
        essay.is_finalized = True
        essay.finalized_at = datetime.utcnow()
        essay.status = 'completed'
        db.session.commit()
