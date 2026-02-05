import pandas as pd
from pathlib import Path
from typing import Dict
import traceback
from momoai_core import MOMOAICore
import database


class BatchProcessor:
    """일괄 처리 클래스"""

    def __init__(self, batch_id: str, dataframe: pd.DataFrame, api_key: str):
        """
        Initialize Batch Processor

        Args:
            batch_id: 일괄 작업 ID
            dataframe: 학생 데이터 DataFrame
            api_key: Anthropic API key
        """
        self.batch_id = batch_id
        self.dataframe = dataframe
        self.momoai = MOMOAICore(api_key)
        self.total = len(dataframe)

    def validate_dataframe(self) -> Dict[str, str]:
        """
        DataFrame 유효성 검사

        Returns:
            에러 정보 딕셔너리 (에러 없으면 빈 딕셔너리)
        """
        required_columns = ['학생명', '학년', '논술문']

        missing_columns = [col for col in required_columns if col not in self.dataframe.columns]

        if missing_columns:
            return {
                'error': 'missing_columns',
                'message': f"필수 열이 누락되었습니다: {', '.join(missing_columns)}"
            }

        # 빈 값 체크
        for col in required_columns:
            if self.dataframe[col].isnull().any():
                return {
                    'error': 'null_values',
                    'message': f"'{col}' 열에 빈 값이 있습니다."
                }

        return {}

    def process_batch(self):
        """일괄 처리 수행"""
        try:
            # 유효성 검사
            validation_error = self.validate_dataframe()
            if validation_error:
                database.fail_batch_task(self.batch_id)
                return

            # 각 행 처리
            for idx, row in self.dataframe.iterrows():
                student_name = str(row['학생명'])
                grade = str(row['학년'])
                essay_text = str(row['논술문'])

                # 진행 상황 업데이트
                database.update_batch_status(
                    self.batch_id,
                    current=idx + 1,
                    current_student=student_name
                )

                try:
                    # 첨삭 수행
                    html_content = self.momoai.analyze_essay(
                        student_name=student_name,
                        grade=grade,
                        essay_text=essay_text
                    )

                    # HTML 저장
                    filename = self.momoai.generate_filename(student_name, grade)
                    html_path = self.momoai.save_html(html_content, filename)

                    # 결과 저장
                    database.save_batch_result(
                        batch_id=self.batch_id,
                        index=idx,
                        student_name=student_name,
                        grade=grade,
                        html_path=html_path
                    )

                except Exception as e:
                    print(f"학생 '{student_name}' 처리 중 오류: {e}")
                    traceback.print_exc()
                    # 개별 오류는 로깅만 하고 계속 진행

            # 완료 처리
            database.complete_batch_task(self.batch_id)

        except Exception as e:
            print(f"일괄 처리 중 오류 발생: {e}")
            traceback.print_exc()
            database.fail_batch_task(self.batch_id)


def read_excel_file(file_path: str) -> pd.DataFrame:
    """
    엑셀 파일 읽기

    Args:
        file_path: 엑셀 파일 경로

    Returns:
        DataFrame
    """
    try:
        return pd.read_excel(file_path)
    except Exception as e:
        raise Exception(f"엑셀 파일을 읽을 수 없습니다: {e}")


def read_csv_file(file_path: str) -> pd.DataFrame:
    """
    CSV 파일 읽기

    Args:
        file_path: CSV 파일 경로

    Returns:
        DataFrame
    """
    try:
        # 여러 인코딩 시도
        for encoding in ['utf-8', 'cp949', 'euc-kr']:
            try:
                return pd.read_csv(file_path, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise Exception("지원하는 인코딩으로 파일을 읽을 수 없습니다.")
    except Exception as e:
        raise Exception(f"CSV 파일을 읽을 수 없습니다: {e}")
