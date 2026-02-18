#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HTML 파일에서 27개 유형 데이터 추출"""
import sys
import io
import re
import json

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

html_file = r'C:\Users\aproa\Downloads\MOMO-논술-MBTI-프리미엄.html'

print("HTML 파일에서 TYPE_DATA 추출 중...")

with open(html_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Find TYPE_DATA object
match = re.search(r'const TYPE_DATA = ({.*?});', content, re.DOTALL)

if not match:
    print("TYPE_DATA를 찾을 수 없습니다.")
    sys.exit(1)

type_data_str = match.group(1)

# JavaScript 객체를 Python으로 변환 (간단한 방법)
# 실제로는 더 정교한 파싱이 필요하지만, 구조가 단순하므로 정규식 사용

# Extract all type entries
type_pattern = r"'([^']+)':\s*{([^}]+(?:{[^}]*}[^}]*)*?)},?"

types = {}
for match in re.finditer(type_pattern, type_data_str):
    key = match.group(1)
    value_str = match.group(2)

    # Parse individual fields
    type_obj = {}

    # code
    code_match = re.search(r"code:\s*'([^']+)'", value_str)
    if code_match:
        type_obj['code'] = code_match.group(1)

    # name
    name_match = re.search(r"name:\s*'([^']+)'", value_str)
    if name_match:
        type_obj['name'] = name_match.group(1)

    # combo
    combo_match = re.search(r"combo:\s*'([^']+)'", value_str)
    if combo_match:
        type_obj['combo'] = combo_match.group(1)

    # desc
    desc_match = re.search(r"desc:\s*'([^']+)'", value_str)
    if desc_match:
        type_obj['desc'] = desc_match.group(1)

    # reading
    reading_match = re.search(r"reading:\s*'([^']+)'", value_str)
    if reading_match:
        type_obj['reading'] = reading_match.group(1)

    # speaking
    speaking_match = re.search(r"speaking:\s*'([^']+)'", value_str)
    if speaking_match:
        type_obj['speaking'] = speaking_match.group(1)

    # writing
    writing_match = re.search(r"writing:\s*'([^']+)'", value_str)
    if writing_match:
        type_obj['writing'] = writing_match.group(1)

    # strengths (array)
    strengths_match = re.search(r"strengths:\s*\[([^\]]+)\]", value_str)
    if strengths_match:
        strengths_str = strengths_match.group(1)
        type_obj['strengths'] = [s.strip().strip("'") for s in strengths_str.split("',")]

    # weaknesses (array)
    weaknesses_match = re.search(r"weaknesses:\s*\[([^\]]+)\]", value_str)
    if weaknesses_match:
        weaknesses_str = weaknesses_match.group(1)
        type_obj['weaknesses'] = [s.strip().strip("'") for s in weaknesses_str.split("',")]

    # tips (array)
    tips_match = re.search(r"tips:\s*\[([^\]]+)\]", value_str)
    if tips_match:
        tips_str = tips_match.group(1)
        type_obj['tips'] = [s.strip().strip("'") for s in tips_str.split("',")]

    types[key] = type_obj

print(f"✅ {len(types)}개 유형 추출 완료")

# Save to JSON file
output_file = 'reading_mbti_types.json'
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(types, f, ensure_ascii=False, indent=2)

print(f"✅ {output_file}에 저장 완료")

# Print summary
for key, type_data in list(types.items())[:3]:
    print(f"\n📖 {key}:")
    print(f"   Code: {type_data.get('code')}")
    print(f"   Name: {type_data.get('name')}")
    print(f"   Combo: {type_data.get('combo')}")
