# -*- coding: utf-8 -*-
"""학년 코드('초1'~'고3') <-> 도서 추천 레벨 코드('LV1'~'LV10') 매핑.
Book.grade_tags는 학년 코드가 아니라 이 LV 코드로 저장되는 것이 컨벤션임
(templates/library/admin/book_form.html의 체크박스 값 참고)."""

GRADE_TO_LV = {
    '초1': 'LV1', '초2': 'LV2', '초3': 'LV3',
    '초4': 'LV4', '초5': 'LV5', '초6': 'LV6',
    '중1': 'LV7', '중2': 'LV8', '중3': 'LV9',
    '고1': 'LV9', '고2': 'LV10', '고3': 'LV10',
}
