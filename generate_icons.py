"""
PWA 아이콘 생성 스크립트
간단한 임시 아이콘을 생성합니다. 나중에 실제 로고로 교체하세요.
"""

from PIL import Image, ImageDraw, ImageFont
import os

# 아이콘 크기 목록
SIZES = [72, 96, 128, 144, 152, 192, 384, 512]

# 아이콘 디렉토리
ICON_DIR = 'static/icons'
os.makedirs(ICON_DIR, exist_ok=True)

def create_icon(size):
    """간단한 그라디언트 아이콘 생성"""
    # 이미지 생성 (보라색 그라디언트)
    img = Image.new('RGB', (size, size), color='white')
    draw = ImageDraw.Draw(img)

    # 원형 배경 (보라색)
    margin = size // 10
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill='#6366f1',
        outline='#4f46e5',
        width=size // 20
    )

    # 텍스트 "M" 추가
    try:
        # 시스템 폰트 사용 시도
        font_size = size // 2
        try:
            # Windows 한글 폰트
            font = ImageFont.truetype("malgun.ttf", font_size)
        except:
            try:
                # 영문 폰트
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                # 기본 폰트
                font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()

    text = "M"

    # 텍스트 크기 계산
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except:
        # 구버전 Pillow
        text_width, text_height = draw.textsize(text, font=font)

    # 텍스트 중앙 배치
    x = (size - text_width) // 2
    y = (size - text_height) // 2 - size // 20

    draw.text((x, y), text, fill='white', font=font)

    return img

# 모든 크기의 아이콘 생성
print("PWA icon generation started...")
for size in SIZES:
    icon = create_icon(size)
    filename = f'{ICON_DIR}/icon-{size}x{size}.png'
    icon.save(filename, 'PNG')
    print(f"[OK] {filename} created")

print("\n[SUCCESS] All icons created!")
print(f"Location: {ICON_DIR}/")
print("\nTo replace with actual logo later:")
print("   1. Use online tool: https://realfavicongenerator.net/")
print("   2. Or https://www.pwabuilder.com/imageGenerator")
print("   3. Replace files in static/icons/ folder")
