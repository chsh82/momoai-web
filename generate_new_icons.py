"""
MOMOAI PWA 아이콘 생성 - 새로운 디자인
5가지 컬러 버전의 그라데이션 아이콘 생성
"""
from PIL import Image, ImageDraw, ImageFont
import os

# 아이콘 저장 경로
ICONS_DIR = 'static/icons'
os.makedirs(ICONS_DIR, exist_ok=True)

# 5가지 컬러 테마 (HTML 파일의 그라데이션 색상)
COLOR_THEMES = {
    'blue': {
        'name': '블루',
        'colors': [(74, 144, 226), (53, 122, 189)],  # #4A90E2 → #357ABD
        'desc': '신뢰감 있는 교육 플랫폼 (추천)'
    },
    'green': {
        'name': '그린',
        'colors': [(80, 200, 120), (61, 163, 93)],  # #50C878 → #3DA35D
        'desc': '성장과 발전'
    },
    'purple': {
        'name': '퍼플',
        'colors': [(155, 89, 182), (142, 68, 173)],  # #9B59B6 → #8E44AD
        'desc': '창의적이고 프리미엄'
    },
    'orange': {
        'name': '오렌지',
        'colors': [(255, 107, 53), (247, 147, 30)],  # #FF6B35 → #F7931E
        'desc': '활기차고 긍정적'
    },
    'navy': {
        'name': '네이비',
        'colors': [(44, 62, 80), (52, 73, 94)],  # #2C3E50 → #34495E
        'desc': '권위 있고 전문적'
    }
}

# PWA에서 요구하는 아이콘 크기
SIZES = [72, 96, 128, 144, 152, 192, 384, 512]

def create_gradient(width, height, color1, color2):
    """대각선 그라데이션 생성 (좌상단→우하단)"""
    base = Image.new('RGB', (width, height), color1)
    top = Image.new('RGB', (width, height), color2)
    mask = Image.new('L', (width, height))

    mask_data = []
    for y in range(height):
        for x in range(width):
            # 대각선 그라데이션 (135도)
            distance = (x + y) / (width + height)
            mask_data.append(int(255 * distance))

    mask.putdata(mask_data)
    base.paste(top, (0, 0), mask)
    return base

def create_icon(size, color_theme_name, color1, color2):
    """아이콘 생성"""
    # 그라데이션 배경 생성
    img = create_gradient(size, size, color1, color2)
    draw = ImageDraw.Draw(img)

    # 둥근 모서리 마스크 생성 (22% 반지름)
    mask = Image.new('L', (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    radius = int(size * 0.22)  # iOS 스타일 둥근 모서리
    mask_draw.rounded_rectangle(
        [(0, 0), (size, size)],
        radius=radius,
        fill=255
    )

    # 그라데이션에 마스크 적용
    rounded = Image.new('RGB', (size, size), (255, 255, 255))
    rounded.paste(img, (0, 0), mask)

    # "M" 글자 추가
    try:
        # 시스템 폰트 사용 (Arial Black 또는 대체 폰트)
        font_size = int(size * 0.65)  # 아이콘 크기의 65%
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)  # Arial Bold
        except:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()

    draw = ImageDraw.Draw(rounded)

    # "M" 글자 중앙 정렬
    text = "M"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = (size - text_width) // 2 - bbox[0]
    y = (size - text_height) // 2 - bbox[1]

    # 텍스트 그림자 효과 (검은색, 약간 아래로)
    shadow_offset = max(2, size // 100)
    draw.text((x + shadow_offset, y + shadow_offset), text,
              fill=(0, 0, 0, 100), font=font)

    # 흰색 "M" 글자
    draw.text((x, y), text, fill=(255, 255, 255), font=font)

    return rounded

def generate_all_icons():
    """모든 크기의 아이콘 생성"""
    print("=" * 60)
    print("MOMOAI PWA 아이콘 생성 시작")
    print("=" * 60)

    # 기본 테마로 블루 사용
    default_theme = 'blue'
    theme = COLOR_THEMES[default_theme]
    color1, color2 = theme['colors']

    print(f"\n선택된 테마: {theme['name']} - {theme['desc']}")
    print(f"색상: RGB{color1} → RGB{color2}")
    print("-" * 60)

    for size in SIZES:
        icon = create_icon(size, default_theme, color1, color2)
        filename = f'icon-{size}x{size}.png'
        filepath = os.path.join(ICONS_DIR, filename)
        icon.save(filepath, 'PNG')
        print(f"[OK] {filename} 생성 완료")

    print("-" * 60)
    print(f"\n[SUCCESS] 총 {len(SIZES)}개의 아이콘 생성 완료!")
    print(f"저장 위치: {ICONS_DIR}/")

    # 다른 테마로 샘플 생성
    print("\n" + "=" * 60)
    print("다른 컬러 테마 샘플 (192x192)")
    print("=" * 60)

    for theme_name, theme_data in COLOR_THEMES.items():
        if theme_name != default_theme:
            color1, color2 = theme_data['colors']
            icon = create_icon(192, theme_name, color1, color2)
            filename = f'icon-{theme_name}-192x192.png'
            filepath = os.path.join(ICONS_DIR, filename)
            icon.save(filepath, 'PNG')
            print(f"[OK] {theme_data['name']}: {filename}")

    print("\n" + "=" * 60)
    print("다른 컬러로 변경하려면:")
    print("   1. 이 스크립트에서 default_theme 값을 변경")
    print("   2. 옵션: 'blue', 'green', 'purple', 'orange', 'navy'")
    print("   3. 다시 실행: python generate_new_icons.py")
    print("=" * 60)

if __name__ == '__main__':
    generate_all_icons()
