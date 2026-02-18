"""
점수 파싱 모듈 (Phase 2)

Claude가 생성한 HTML에서 18개 지표 점수와 총점, 최종 등급을 추출합니다.
"""

from typing import Dict, Optional, List, Tuple
from bs4 import BeautifulSoup
import re


class ScoreParser:
    """HTML에서 점수를 파싱하는 클래스"""

    # 18개 지표 정의 (순서대로)
    THINKING_TYPES = [
        '요약', '비교', '적용', '평가', '비판',
        '문제해결', '자료해석', '견해제시', '종합'
    ]

    INTEGRATED_INDICATORS = [
        '결론', '구조논리', '표현명료', '문제인식', '개념정보',
        '목적적절', '관점다각', '심층성', '완전성'
    ]

    # 전체 18개 지표 (매핑용)
    INDICATOR_MAPPING = {
        # 사고유형
        '요약': '요약',
        '비교': '비교',
        '적용': '적용',
        '평가': '평가',
        '비판': '비판',
        '문제해결': '문제해결',
        '자료해석': '자료해석',
        '견해제시': '견해제시',
        '종합': '종합',
        # 통합지표
        '결론': '결론',
        '구조논리': '구조/논리성',
        '표현명료': '표현/명료성',
        '문제인식': '문제인식',
        '개념정보': '개념/정보',
        '목적적절': '목적/적절성',
        '관점다각': '관점/다각성',
        '심층성': '심층성',
        '완전성': '완전성'
    }

    def __init__(self):
        """초기화"""
        pass

    def parse_html(self, html_content: str) -> Dict:
        """
        HTML에서 점수 정보 추출

        Args:
            html_content: Claude가 생성한 HTML 문자열

        Returns:
            Dict with keys:
                - total_score: 총점 (float)
                - final_grade: 최종 등급 (str)
                - thinking_types: 사고유형 9개 점수 (Dict[str, float])
                - integrated_indicators: 통합지표 9개 점수 (Dict[str, float])
                - success: 파싱 성공 여부 (bool)
                - error: 에러 메시지 (str, optional)
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 1. 총점 추출
            total_score = self._extract_total_score(soup)

            # 2. 최종 등급 추출
            final_grade = self._extract_final_grade(soup)

            # 3. 사고유형 점수 추출
            thinking_scores = self._extract_thinking_scores(soup)

            # 4. 통합지표 점수 추출
            integrated_scores = self._extract_integrated_scores(soup)

            return {
                'success': True,
                'total_score': total_score,
                'final_grade': final_grade,
                'thinking_types': thinking_scores,
                'integrated_indicators': integrated_scores
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'total_score': None,
                'final_grade': None,
                'thinking_types': {},
                'integrated_indicators': {}
            }

    def _extract_total_score(self, soup: BeautifulSoup) -> Optional[float]:
        """
        총점 추출
        HTML에서 "최종점수" 또는 "최종 점수" 라벨 다음의 값을 찾습니다.
        """
        # 방법 1: info-label이 "최종점수"인 경우
        labels = soup.find_all(class_='info-label')
        for label in labels:
            if '최종점수' in label.get_text() or '최종 점수' in label.get_text():
                value_elem = label.find_next_sibling(class_='info-value')
                if value_elem:
                    score_text = value_elem.get_text()
                    # "XX.X점" 형식에서 숫자만 추출
                    match = re.search(r'(\d+\.?\d*)', score_text)
                    if match:
                        return float(match.group(1))

        # 방법 2: score-section 내의 score-number 찾기
        score_section = soup.find(class_='score-section')
        if score_section:
            score_numbers = score_section.find_all(class_='score-number')
            if score_numbers:
                # 첫 번째 score-number가 점수
                score_text = score_numbers[0].get_text()
                match = re.search(r'(\d+\.?\d*)', score_text)
                if match:
                    return float(match.group(1))

        return None

    def _extract_final_grade(self, soup: BeautifulSoup) -> Optional[str]:
        """
        최종 등급 추출
        HTML에서 "등급" 라벨 다음의 값을 찾습니다.
        """
        # 방법 1: info-label이 "등급"인 경우
        labels = soup.find_all(class_='info-label')
        for label in labels:
            if label.get_text().strip() == '등급':
                value_elem = label.find_next_sibling(class_='info-value')
                if value_elem:
                    grade = value_elem.get_text().strip()
                    return grade

        # 방법 2: score-section 내의 두 번째 score-number
        score_section = soup.find(class_='score-section')
        if score_section:
            score_numbers = score_section.find_all(class_='score-number')
            if len(score_numbers) >= 2:
                grade = score_numbers[1].get_text().strip()
                return grade

        return None

    def _extract_thinking_scores(self, soup: BeautifulSoup) -> Dict[str, float]:
        """
        사고유형 9개 점수 추출
        SVG radar chart에서 텍스트 라벨과 점수를 매칭합니다.
        """
        scores = {}

        # 사고유형 차트 찾기 (첫 번째 chart-card with "사고유형")
        chart_cards = soup.find_all(class_='chart-card')
        for card in chart_cards:
            title = card.find(class_='chart-title')
            if title and '사고유형' in title.get_text():
                # SVG 내의 모든 text 요소 찾기
                svg = card.find('svg', class_='radar-svg')
                if svg:
                    scores = self._extract_scores_from_svg(svg, self.THINKING_TYPES)
                break

        return scores

    def _extract_integrated_scores(self, soup: BeautifulSoup) -> Dict[str, float]:
        """
        통합지표 9개 점수 추출
        SVG radar chart에서 텍스트 라벨과 점수를 매칭합니다.
        """
        scores = {}

        # 통합지표 차트 찾기 (두 번째 chart-card with "통합지표")
        chart_cards = soup.find_all(class_='chart-card')
        for card in chart_cards:
            title = card.find(class_='chart-title')
            if title and '통합지표' in title.get_text():
                # SVG 내의 모든 text 요소 찾기
                svg = card.find('svg', class_='radar-svg')
                if svg:
                    # 통합지표 짧은 이름 목록
                    short_names = ['결론', '구조논리', '표현명료', '문제인식', '개념정보',
                                   '목적적절', '관점다각', '심층성', '완전성']
                    scores = self._extract_scores_from_svg(svg, short_names)
                break

        return scores

    def _extract_scores_from_svg(self, svg, expected_labels: List[str]) -> Dict[str, float]:
        """
        SVG에서 라벨과 점수 추출

        Args:
            svg: BeautifulSoup SVG element
            expected_labels: 예상되는 라벨 목록 (순서대로)

        Returns:
            Dict[label, score]
        """
        scores = {}

        # 모든 text 요소 찾기
        texts = svg.find_all('text')

        # radar-label과 radar-score를 분리
        labels = []
        score_values = []

        for text in texts:
            class_attr = text.get('class', [])
            text_content = text.get_text().strip()

            if 'radar-label' in class_attr:
                # 라벨 텍스트
                labels.append(text_content)
            elif 'radar-score' in class_attr:
                # 점수 텍스트 (숫자만)
                try:
                    score = float(text_content)
                    score_values.append(score)
                except ValueError:
                    continue

        # 라벨과 점수 매칭
        for i, label in enumerate(labels):
            if i < len(score_values):
                # 짧은 이름을 전체 이름으로 매핑
                if label in self.INDICATOR_MAPPING:
                    full_name = self.INDICATOR_MAPPING[label]
                    scores[full_name] = score_values[i]
                else:
                    scores[label] = score_values[i]

        return scores

    def get_all_scores_list(self, parsed_data: Dict) -> List[Tuple[str, str, float]]:
        """
        파싱된 데이터를 EssayScore 저장용 리스트로 변환

        Args:
            parsed_data: parse_html() 결과

        Returns:
            List of (category, indicator_name, score) tuples
        """
        result = []

        if not parsed_data.get('success'):
            return result

        # 사고유형
        for name, score in parsed_data.get('thinking_types', {}).items():
            result.append(('사고유형', name, score))

        # 통합지표
        for name, score in parsed_data.get('integrated_indicators', {}).items():
            result.append(('통합지표', name, score))

        return result


# 싱글톤 인스턴스
_parser_instance = None

def get_parser() -> ScoreParser:
    """ScoreParser 싱글톤 인스턴스 반환"""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = ScoreParser()
    return _parser_instance
