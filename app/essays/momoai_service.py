# -*- coding: utf-8 -*-
"""MOMOAI 첨삭 서비스 (SQLAlchemy 연동)"""
import anthropic
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from flask import current_app

from app.models import db, Essay, EssayVersion, EssayResult, EssayScore, EssayNote
from app.essays.score_parser import get_parser


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
                     is_revision_of_completed: bool = False) -> str:
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

        try:
            print(f"\n{'='*60}")
            print(f"[첨삭 시작] {student_name} 학생 - {grade}")
            print(f"System prompt 길이: {len(self.system_prompt):,} chars")
            print(f"User prompt 길이: {len(user_prompt):,} chars")
            print(f"{'='*60}\n")

            start_time = time.time()

            # Prompt Caching 적용: system prompt를 5분간 캐싱
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=16000,
                timeout=300.0,
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

            print(f"\n{'='*60}")
            print(f"[첨삭 완료] API 호출 시간: {elapsed_time:.2f}초")
            print(f"응답 길이: {len(response.content[0].text):,} chars")
            if cache_creation > 0:
                print(f"캐시 생성: {cache_creation:,} 토큰 (첫 요청)")
            if cache_read > 0:
                print(f"캐시 읽기: {cache_read:,} 토큰 (캐싱 활용!)")
                print(f"💰 비용 절감: 약 90% (캐싱된 토큰 무료)")
            print(f"{'='*60}\n")

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

        except Exception as e:
            raise Exception(f"첨삭 중 오류가 발생했습니다: {e}")

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
            # 주의사항 가져오기
            notes = None
            if essay.notes:
                notes = '\n'.join([note.content for note in essay.notes])

            # 첨삭 수행
            html_content = self.analyze_essay(
                student_name=student_name,
                grade=essay.grade,
                essay_text=essay.original_text,
                notes=notes,
                teacher_name=teacher_name
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
                is_revision_of_completed = False

            # 재생성
            html_content = self.analyze_essay(
                student_name=student_name,
                grade=essay.grade,
                essay_text=essay_text,
                notes=notes,
                revision_note=revision_note,
                teacher_name=teacher_name,
                is_revision_of_completed=is_revision_of_completed
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
