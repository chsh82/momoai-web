"""
점수 파서 테스트 스크립트
"""

import sys
import io

# Windows 콘솔 인코딩 문제 해결
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.essays.score_parser import get_parser

# 샘플 HTML (MOMOAI 3.3.0 format)
sample_html = """
<!DOCTYPE html>
<html lang="ko">
<head>
<title>MOMOAI Test</title>
</head>
<body>
<div class="first-page">
  <div class="info-grid">
    <div class="info-card">
      <div class="info-card-title">🎯 분석 결과</div>
      <div class="info-items">
        <div class="info-item"><span class="info-label">최종점수</span><span class="info-value">85.5점</span></div>
        <div class="info-item"><span class="info-label">등급</span><span class="info-value">B+</span></div>
      </div>
    </div>
  </div>

  <!-- 종합 평가 -->
  <div class="score-section grade-b-plus">
    <div class="score-title">종합 평가</div>
    <div class="score-display">
      <div class="score-box">
        <div class="score-number">85.5</div>
        <div class="score-label">최종 점수</div>
      </div>
      <div class="score-divider"></div>
      <div class="score-box">
        <div class="score-number">B+</div>
        <div class="score-label">등급</div>
      </div>
    </div>
  </div>

  <!-- 성취도 분석 차트 -->
  <div class="chart-grid">
    <!-- 사고유형 차트 -->
    <div class="chart-card">
      <div class="chart-title">📚 사고유형 분석</div>
      <div class="radar-chart">
        <svg class="radar-svg">
          <text class="radar-label" x="130" y="20">요약</text>
          <text class="radar-score thinking" x="130" y="25">8.5</text>

          <text class="radar-label" x="200" y="42">비교</text>
          <text class="radar-score thinking" x="200" y="47">7.0</text>

          <text class="radar-label" x="225" y="96">적용</text>
          <text class="radar-score thinking" x="225" y="101">8.0</text>

          <text class="radar-label" x="212" y="168">평가</text>
          <text class="radar-score thinking" x="212" y="173">9.0</text>

          <text class="radar-label" x="160" y="208">비판</text>
          <text class="radar-score thinking" x="160" y="213">7.5</text>

          <text class="radar-label" x="100" y="208">문제해결</text>
          <text class="radar-score thinking" x="100" y="213">8.5</text>

          <text class="radar-label" x="48" y="168">자료해석</text>
          <text class="radar-score thinking" x="48" y="173">7.0</text>

          <text class="radar-label" x="35" y="96">견해제시</text>
          <text class="radar-score thinking" x="35" y="101">8.0</text>

          <text class="radar-label" x="62" y="42">종합</text>
          <text class="radar-score thinking" x="62" y="47">9.0</text>
        </svg>
      </div>
    </div>

    <!-- 통합지표 차트 -->
    <div class="chart-card">
      <div class="chart-title">🔍 통합지표 분석</div>
      <div class="radar-chart">
        <svg class="radar-svg">
          <text class="radar-label" x="130" y="20">결론</text>
          <text class="radar-score integrated" x="130" y="25">8.0</text>

          <text class="radar-label" x="200" y="42">구조논리</text>
          <text class="radar-score integrated" x="200" y="47">7.5</text>

          <text class="radar-label" x="225" y="96">표현명료</text>
          <text class="radar-score integrated" x="225" y="101">8.5</text>

          <text class="radar-label" x="212" y="168">문제인식</text>
          <text class="radar-score integrated" x="212" y="173">9.0</text>

          <text class="radar-label" x="160" y="208">개념정보</text>
          <text class="radar-score integrated" x="160" y="213">8.0</text>

          <text class="radar-label" x="100" y="208">목적적절</text>
          <text class="radar-score integrated" x="100" y="213">7.5</text>

          <text class="radar-label" x="48" y="168">관점다각</text>
          <text class="radar-score integrated" x="48" y="173">8.5</text>

          <text class="radar-label" x="35" y="96">심층성</text>
          <text class="radar-score integrated" x="35" y="101">9.0</text>

          <text class="radar-label" x="62" y="42">완전성</text>
          <text class="radar-score integrated" x="62" y="47">8.0</text>
        </svg>
      </div>
    </div>
  </div>
</div>
</body>
</html>
"""

def main():
    print("=" * 60)
    print("🧪 MOMOAI 점수 파서 테스트")
    print("=" * 60)

    # 파서 가져오기
    parser = get_parser()

    # HTML 파싱
    print("\n📝 HTML 파싱 중...")
    result = parser.parse_html(sample_html)

    if result['success']:
        print("✅ 파싱 성공!\n")

        # 총점
        print(f"📊 총점: {result['total_score']}점")
        print(f"🏆 최종 등급: {result['final_grade']}")

        # 사고유형
        print("\n📚 사고유형 9개:")
        for name, score in result['thinking_types'].items():
            print(f"  - {name}: {score}")

        # 통합지표
        print("\n🔍 통합지표 9개:")
        for name, score in result['integrated_indicators'].items():
            print(f"  - {name}: {score}")

        # 저장용 리스트
        scores_list = parser.get_all_scores_list(result)
        print(f"\n💾 저장할 점수 개수: {len(scores_list)}개")

        # 평균 계산
        all_scores = [score for _, _, score in scores_list]
        if all_scores:
            avg_score = sum(all_scores) / len(all_scores)
            print(f"📈 18개 지표 평균: {avg_score:.2f}")

        print("\n" + "=" * 60)
        print("✅ 테스트 완료!")
        print("=" * 60)

    else:
        print(f"❌ 파싱 실패: {result.get('error')}")

if __name__ == '__main__':
    main()
